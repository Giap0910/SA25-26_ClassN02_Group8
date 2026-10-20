"""Kiểm tra đặc tả, sinh mã và đối chiếu C sinh ra với oracle độc lập."""
import copy
import ast
import ctypes
import json
import os
import random
from pathlib import Path
import subprocess
import unittest
import uuid
from unittest.mock import patch

import fuzz_runner as runner
import generate_simulator as generator


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = generator.load_spec()
        cls.directory = runner.OUTPUT / ('generator-tests-' + uuid.uuid4().hex[:8])
        cls.directory.mkdir(parents=True)
        cls.gcc = Path(target_compiler())
        os.environ['PATH'] = str(cls.gcc.parent) + os.pathsep + os.environ.get('PATH', '')

    def compile_spec(self, spec, label):
        directory = self.directory / label
        directory.mkdir()
        source = directory / 'generated.c'
        source.write_text(generator.generate(spec), encoding='utf-8')
        return runner.compile_target(directory, str(self.gcc), source), directory

    def test_backend_fingerprint(self):
        self.assertEqual(len(self.spec['backend_sha256']), 2)

    def test_reject_arbitrary_code(self):
        for text in ('__import__("os")', 'q.__class__', 'q * q', 'unknown', '2147483648'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                generator.translate(text)

    def test_generation_is_deterministic(self):
        self.assertEqual(generator.generate(self.spec), generator.generate(copy.deepcopy(self.spec)))

    def test_generated_regressions(self):
        binary, directory = self.compile_spec(self.spec, 'regression')
        self.assertEqual(runner.regressions(binary, directory), 25)

    def test_spec_changes_executed_behavior(self):
        changed = copy.deepcopy(self.spec)
        changed['operations']['reserve'][0]['when'] = 'q < 1 or q > 50'
        binary, directory = self.compile_spec(changed, 'changed-limit')
        data = directory / 'quantity-51.bin'
        data.write_bytes(runner.pack(100, 0, 100, 0, 51, 0))
        process = subprocess.run([str(binary), str(data)], capture_output=True, text=True, timeout=2)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(json.loads(process.stdout)['status'], 'rejected')
        self.assertEqual(runner.oracle(data.read_bytes())[0], 'accepted')

    def test_operation_sets_are_present(self):
        source = generator.generate(self.spec)
        self.assertIn('static int reserve(', source)
        self.assertIn('static int settle(', source)
        self.assertNotEqual(source, runner.SOURCE.read_text(encoding='utf-8'))

    def test_handwritten_business_rules_are_not_copied(self):
        expected = generator.generate(self.spec)
        adapter = runner.SOURCE.read_text(encoding='utf-8').replace('q > 100', 'q > 3')
        with patch.object(Path, 'read_text', return_value=adapter):
            self.assertEqual(generator.generate(self.spec), expected)

    def test_backend_change_stops_generation(self):
        changed = copy.deepcopy(self.spec)
        changed['backend_sha256']['OrderService.java'] = '0' * 64
        path = self.directory / 'stale-spec.json'
        path.write_text(json.dumps(changed), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'đã đổi'):
            generator.load_spec(path)

    def test_requirement_traceability(self):
        tables = self.spec['teacher_tables']
        requirements = {row[0] for row in tables['YeuCauChucNang'][1:]}
        cases = {row[0]: row[1] for row in tables['TestCase'][1:]}
        self.assertEqual(len(tables), 10)
        self.assertEqual({row['requirement'] for row in self.spec['traceability']}, requirements)
        for row in self.spec['traceability']:
            self.assertEqual(cases[row['cases']], row['requirement'])

    def test_json_adapter_and_wrap(self):
        import stock_json_fuzz as target
        directory = self.directory / 'json'; directory.mkdir()
        source = directory / 'generated-json.c'
        source.write_text(generator.generate_json(self.spec), encoding='utf-8')
        binary = runner.compile_target(directory, str(self.gcc), source, 'stock_json_target')
        self.assertEqual(target.regressions(binary, directory), len(target.golden_cases()))
        self.assertEqual(target.shared_check(source, directory, str(self.gcc)), len(target.golden_cases()) - 1)

    def test_json_spec_changes_c_behavior(self):
        import stock_json_fuzz as target
        changed = copy.deepcopy(self.spec)
        changed['operations']['reserve'][0]['when'] = 'q < 1 or q > 50'
        directory = self.directory / 'json-changed'; directory.mkdir()
        source = directory / 'changed.c'
        source.write_text(generator.generate_json(changed), encoding='utf-8')
        binary = runner.compile_target(directory, str(self.gcc), source, 'stock_json_target')
        value = dict(target.fixture(51), available=100)
        outcome, actual, _ = target.execute(binary, target.encode(value), directory, 0)
        self.assertEqual(outcome, 'oracle_mismatch')
        self.assertEqual(actual['code'], 1)

    def test_json_bounds_cannot_silently_drift(self):
        changed = copy.deepcopy(self.spec)
        changed['json_transport']['max_records'] = 1000
        with self.assertRaisesRegex(ValueError, 'Giới hạn JSON'):
            generator.generate_json(changed)

    def json_library(self, source, label):
        directory = self.directory / label; directory.mkdir()
        path = directory / 'target.c'; path.write_text(source,encoding='utf-8')
        library = directory / 'target.dll'
        process = subprocess.run([str(self.gcc),'-std=c11','-Wall','-Wextra','-Werror','-shared',str(path),'-o',str(library)],
                                 capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        target = ctypes.CDLL(str(library))
        target.stock_json.argtypes, target.stock_json.restype = [ctypes.c_char_p], ctypes.c_int
        return target

    def test_json_allocation_failure(self):
        import stock_json_fuzz as target
        source = generator.generate_json(self.spec,library=True)
        source = source.replace('calloc(STOCK_JSON_MAX_RECORDS, sizeof(int32_t))','NULL')
        library = self.json_library(source,'alloc-failure')
        self.assertEqual(library.stock_json(target.encode(target.fixture())),105)

    def test_json_allocation_balance(self):
        import stock_json_fuzz as target
        source = generator.generate_json(self.spec,library=True)
        tracking = ('static int liveBlocks;\n'
                    'static void *trackedCalloc(size_t n,size_t s) { void *p=calloc(n,s); if(p)++liveBlocks; return p; }\n'
                    'static void trackedFree(void *p) { if(p)--liveBlocks; free(p); }\n'
                    'int stock_live_blocks(void) { return liveBlocks; }\n')
        source = source.replace('fixture.quantities = calloc(', 'fixture.quantities = trackedCalloc(')
        source = source.replace('free(fixture.quantities);','trackedFree(fixture.quantities);')
        source = source.replace('#define STOCK_JSON_MAX_BYTES',tracking+'#define STOCK_JSON_MAX_BYTES',1)
        library = self.json_library(source,'alloc-balance')
        library.stock_live_blocks.restype = ctypes.c_int
        for _, data, _ in target.golden_cases():
            library.stock_json(data)
            self.assertEqual(library.stock_live_blocks(),0)

    def test_json_excel_traceability(self):
        import stock_json_fuzz as target
        tables = target.spec_tables()
        self.assertEqual(len(tables),10)
        self.assertEqual(len(tables['TestCase'])-1,55)
        requirements = {row[0] for row in tables['YeuCauChucNang'][1:]}
        covered = {key.strip() for row in tables['TestCase'][1:] for key in row[1].split(',')}
        self.assertEqual(covered,requirements)
        self.assertEqual(len(tables['LoaiTruLanNhau']),2)

    def test_json_launcher_does_not_change_parent_path(self):
        import stock_json_fuzz as target
        before = os.environ.get('PATH','')
        with patch.object(target.subprocess,'Popen') as launch, patch.object(Path,'exists',return_value=True), patch('builtins.print'):
            self.assertEqual(target.open_lab(),0)
            environment = launch.call_args.kwargs['env']
            self.assertTrue(environment['PATH'].startswith(str(self.gcc.parent)))
            self.assertEqual(os.environ.get('PATH',''),before)

    def test_standalone_paths_stay_inside_project(self):
        self.assertEqual(runner.ROOT,generator.HERE)
        self.assertEqual(runner.OUTPUT,generator.HERE/'results')
        self.assertEqual(runner.BACKEND,generator.HERE/'reference_backend')
        self.assertEqual(generator.REFERENCE_BACKEND,runner.BACKEND)

    def test_submission_c_matches_generator(self):
        source = (generator.HERE/'stock_json_seclab.c').read_text(encoding='utf-8')
        self.assertEqual(source,generator.generate_json(self.spec,library=True))

    def test_seclab_numeric_entry_uses_json_pipeline(self):
        import stock_json_fuzz as target
        library = self.json_library(generator.generate_json(self.spec,library=True),'seclab-entry')
        entry = library.stock_json_case
        entry.argtypes, entry.restype = [ctypes.c_int] * 4, ctypes.c_int
        cases = [(10,0,2,action) for action in range(16)]
        cases += [(0,0,1,0),(10,2147483647,1,0),(10,0,0,0),
                  (10,0,101,0),(-1,0,1,0),(10,-1,1,0),(10,0,2,-1)]
        rng = random.Random(42)
        edges = [-2147483648,-1,0,1,2,10,99,100,101,2147483647]
        cases += [tuple(rng.choice(edges) for _ in range(4)) for _ in range(500)]
        for available, reserved, quantity, action in cases:
            value = dict(target.fixture(quantity,action),available=available,reserved=reserved,
                         variant_available=available,variant_reserved=reserved)
            with self.subTest(input=(available,reserved,quantity,action)):
                expected = target.oracle(target.encode(value))['code']
                self.assertEqual(entry(available,reserved,quantity,action),expected)

    def test_seclab_entry_follows_generated_rules(self):
        changed = copy.deepcopy(self.spec)
        changed['operations']['reserve'][0]['when'] = 'q < 1 or q > 50'
        library = self.json_library(generator.generate_json(changed,library=True),'seclab-changed')
        entry = library.stock_json_case
        entry.argtypes, entry.restype = [ctypes.c_int] * 4, ctypes.c_int
        self.assertEqual(entry(100,0,51,0),1)
        self.assertEqual(entry(100,0,50,0),0)

    def test_sanitizer_diagnostics_are_failures(self):
        import stock_json_fuzz as target
        for marker in ('ERROR: AddressSanitizer: heap-use-after-free','runtime error: signed integer overflow'):
            process = subprocess.CompletedProcess([],1,b'',marker.encode())
            with patch.object(target.subprocess,'run',return_value=process):
                outcome, _, log = target.execute(Path('unused.exe'),b'{}',self.directory,9000)
            self.assertEqual(outcome,'sanitizer_failure')
            self.assertIn(marker,log)

    def test_sanitizer_detects_known_errors(self):
        import stock_json_fuzz as target
        try:
            compiler = target.sanitizer_compiler()
        except RuntimeError as error:
            self.skipTest(str(error))
        probes = {'use-after-free':'#include <stdlib.h>\nint main(void) { int *p=malloc(4); if(!p)return 2; free(p); return *(volatile int *)p; }',
                  'overflow':'#include <limits.h>\nint main(void) { volatile int x=INT_MAX; return x+1; }'}
        for name, code in probes.items():
            directory = self.directory/name; directory.mkdir()
            source = directory/'probe.c'; source.write_text(code,encoding='utf-8')
            binary, _ = target.compile_sanitized(source,directory,compiler)
            outcome, _, log = target.execute(binary,b'{}',directory,0)
            (directory/'diagnostic.log').write_text(log,encoding='utf-8')
            self.assertEqual(outcome,'sanitizer_failure',log)

    def test_smt_guard_matches_reserve(self):
        source = generator.generate_json(self.spec,library=True)
        source += ('\nint reference_reserve(int a,int r,int q,int v,int va,int vr) {'
                   'Stock s={a,r,va,vr,0,v}; return reserve(&s,q); }\n')
        library = self.json_library(source,'smt-guard')
        guard, reference = library.stock_reserve_guard, library.reference_reserve
        for function in (guard,reference):
            function.argtypes, function.restype = [ctypes.c_int]*6, ctypes.c_int
        edges = [-2147483648,-1,0,1,2,99,100,101,2147483646,2147483647]
        rng = random.Random(42)
        cases = [(100,0,1,0,100,0),(0,0,1,0,0,0),(100,2147483647,1,0,100,0),
                 (100,0,1,1,0,0),(100,0,1,1,100,2147483647),(100,0,0,0,100,0)]
        cases += [tuple(rng.choice(edges) for _ in range(6)) for _ in range(10000)]
        for values in cases:
            with self.subTest(input=values):
                self.assertEqual(guard(*values),reference(*values))

    def test_gui_cases_match_independent_oracle(self):
        import stock_json_fuzz as target
        cases = [(1,1,1,1,0),(0,1,1,1,2),(100,1,1,1,0),(-2147483648,1,1,1,104),
                 (-254551521,102,31,43,100),(2147483647,10,-2811,2,103),
                 (129,190,45,3,0),(119,91,48,14,0),(3,1,1,13,0),
                 (2,2147483647,1,1,3),(2,-31,1,1,104),(0,1,0,1,103),
                 (1,1,2,-1,100),(1,0,105,1,103),(-1,1,1,1,104)]
        library = self.json_library(generator.generate_json(self.spec,library=True),'gui-replay')
        function = library.stock_json_case
        function.argtypes, function.restype = [ctypes.c_int]*4, ctypes.c_int
        for available,reserved,quantity,action,observed in cases:
            value = dict(target.fixture(quantity,action),available=available,reserved=reserved,
                         variant_available=available,variant_reserved=reserved)
            with self.subTest(input=(available,reserved,quantity,action)):
                self.assertEqual(target.oracle(target.encode(value))['code'],observed)
                self.assertEqual(function(available,reserved,quantity,action),observed)

    def test_smt_guard_changes_with_specification(self):
        changed = copy.deepcopy(self.spec)
        changed['operations']['reserve'][0]['when'] = 'q < 1 or q > 50'
        library = self.json_library(generator.generate_json(changed,library=True),'smt-changed')
        function = library.stock_reserve_guard
        function.argtypes, function.restype = [ctypes.c_int]*6, ctypes.c_int
        self.assertEqual(function(100,0,51,0,100,0),1)
        self.assertEqual(function(100,0,50,0,100,0),0)

    def test_smt_guard_rejects_unsafe_projection(self):
        changed = copy.deepcopy(self.spec)
        changed['operations']['reserve'][0]['when'] = 'q < 0 or q > 100'
        with self.assertRaises(ValueError):
            generator.generate_guard(changed)
        changed = copy.deepcopy(self.spec)
        changed['operations']['reserve'].append({'when':'available < q','return':2})
        with self.assertRaises(ValueError):
            generator.generate_guard(changed)

    def test_smt_guard_has_no_arrays_pointers_or_calls(self):
        source = generator.generate_guard(self.spec)
        self.assertNotIn('*',source)
        self.assertNotIn('[',source)
        self.assertNotIn('INT64_C',source)
        self.assertNotIn('stock_json',source)
        self.assertEqual(source.count('('),source.count(')'))

    def test_smt_logical_operands_are_explicit_booleans(self):
        source = generator.generate_guard(self.spec)
        self.assertIn('(variant != 0)',source)
        self.assertNotIn('(variant &&',source)
        self.assertEqual(generator.guard_boolean(ast.parse('not variant',mode='eval').body),
                         '(!(variant != 0))')
        self.assertEqual(generator.guard_boolean(ast.parse('1',mode='eval').body),'(1 != 0)')


class ComparisonTests(unittest.TestCase):
    def test_smt_paths_match_independent_guard(self):
        import compare_fuzz as comparison
        spec = generator.load_spec()
        for code in range(6):
            with self.subTest(code=code):
                result = comparison.solve_path(spec, code, 7, 5000)
                if code == 1:
                    self.assertEqual(result['status'], 'unsat')
                    self.assertIsNone(result['witness'])
                    continue
                self.assertEqual(result['status'], 'sat')
                self.assertEqual(comparison.expected_code(spec, result['witness']), code)

    def test_sampling_reproducible_and_in_domain(self):
        import compare_fuzz as comparison
        for strategy in ('uniform', 'edge-enriched'):
            first, second = random.Random(42), random.Random(42)
            for _ in range(100):
                values = comparison.sample(first, strategy)
                self.assertEqual(values, comparison.sample(second, strategy))
                for value, (low, high) in zip(values, comparison.LIMITS):
                    self.assertLessEqual(low, value)
                    self.assertLessEqual(value, high)

    def test_budget_and_first_hit_are_truthful(self):
        import compare_fuzz as comparison
        miss = comparison.blackbox(lambda *args: 0, 1, 9, 'uniform', 3)
        hit = comparison.blackbox(lambda *args: 3, 1, 9, 'uniform', 3)
        self.assertFalse(miss['found'])
        self.assertEqual(miss['c_calls'], 9)
        self.assertIsNone(miss['witness'])
        self.assertTrue(hit['found'])
        self.assertEqual(hit['c_calls'], 1)

    def test_smt_model_tracks_specification(self):
        import compare_fuzz as comparison
        spec = generator.load_spec()
        spec['operations']['reserve'][0]['when'] = 'q < 1 or q > 50'
        result = comparison.solve_path(spec, 3, 1, 5000)
        self.assertEqual(result['status'], 'sat')
        self.assertLessEqual(result['witness'][2], 50)
        self.assertEqual(comparison.expected_code(spec, result['witness']), 3)


def target_compiler():
    import stock_json_fuzz as target
    return target.toolchain()['gcc']


if __name__ == '__main__':
    unittest.main(verbosity=2)
