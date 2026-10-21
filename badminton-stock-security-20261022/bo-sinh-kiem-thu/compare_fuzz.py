# Công dụng: So sánh lấy mẫu đều, lấy mẫu tăng cường biên và SMT khi tìm cùng một nhánh guard C; không kiểm thử website.
"""So sánh ngẫu nhiên/SMT tới cùng nhánh guard C; không kiểm thử web."""
import argparse
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import uuid

import generate_simulator as generator
import stock_json_fuzz as runner

HERE = Path(__file__).resolve().parent
MAX = 2147483647
NAMES = ('available', 'reserved', 'q', 'variant', 'va', 'vr')
LIMITS = ((0, MAX), (0, MAX), (1, 100), (0, 1), (0, MAX), (0, MAX))


def symbolic(node, variables, z3):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return z3.IntVal(node.value)
    if isinstance(node, ast.Name) and node.id in variables:
        return variables[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return symbolic(node.left, variables, z3) + symbolic(node.right, variables, z3)
    if isinstance(node, ast.BoolOp):
        values = [symbolic(value, variables, z3) for value in node.values]
        values = [value if z3.is_bool(value) else value != 0 for value in values]
        if isinstance(node.op, ast.And): return z3.And(*values)
        if isinstance(node.op, ast.Or): return z3.Or(*values)
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left = symbolic(node.left, variables, z3)
        right = symbolic(node.comparators[0], variables, z3)
        if isinstance(node.ops[0], ast.Lt): return left < right
        if isinstance(node.ops[0], ast.Gt): return left > right
    raise ValueError('Biểu thức chưa hỗ trợ: ' + ast.dump(node))


def path_constraints(spec, code, variables, z3):
    constraints = []
    for rule in generator.guard_rules(spec):
        expression = ast.parse(rule['when'], mode='eval').body
        condition = symbolic(expression, variables, z3)
        if rule['return'] == code:
            return constraints + [condition]
        constraints.append(z3.Not(condition))
    if code == 0: return constraints
    raise ValueError('Không có nhánh trả về yêu cầu')


def domain_constraints(variables):
    return [bound for name, (low, high) in zip(NAMES, LIMITS)
            for bound in (variables[name] >= low, variables[name] <= high)]


def solve_path(spec, code, seed, timeout_ms):
    import z3
    start = time.perf_counter()
    variables = {name: z3.Int(name) for name in NAMES}
    solver = z3.Solver()
    solver.set(timeout=timeout_ms, random_seed=seed)
    solver.add(*domain_constraints(variables))
    solver.add(*path_constraints(spec, code, variables, z3))
    status = solver.check()
    witness = None
    if status == z3.sat:
        model = solver.model()
        witness = [model.eval(variables[name], model_completion=True).as_long() for name in NAMES]
    return {'status': str(status), 'solve_seconds': time.perf_counter() - start,
            'witness': witness, 'reason_unknown': solver.reason_unknown() if status == z3.unknown else None}


def expected_code(spec, values):
    environment = dict(zip(NAMES, values))
    for rule in generator.guard_rules(spec):
        expression = compile(ast.parse(rule['when'], mode='eval'), '<validated-spec>', 'eval')
        if eval(expression, {'__builtins__': {}}, environment): return rule['return']
    return 0


def sample(randomizer, strategy):
    values = []
    for low, high in LIMITS:
        edges = sorted({low, min(low + 1, high), max(low, high - 1), high})
        use_edge = strategy == 'edge-enriched' and randomizer.random() < 0.2
        values.append(randomizer.choice(edges) if use_edge else randomizer.randint(low, high))
    return values


def blackbox(function, seed, budget, strategy, target):
    randomizer = random.Random(seed)
    start = time.perf_counter()
    histogram = {}
    for attempt in range(1, budget + 1):
        values = sample(randomizer, strategy)
        code = function(*values)
        histogram[str(code)] = histogram.get(str(code), 0) + 1
        if code == target:
            return dict(method='black-box', strategy=strategy, seed=seed, found=True,
                        c_calls=attempt, seconds=time.perf_counter()-start, witness=values, codes=histogram)
    return dict(method='black-box', strategy=strategy, seed=seed, found=False,
                c_calls=budget, seconds=time.perf_counter()-start, witness=None, codes=histogram)


def smt(function, spec, seed, timeout_ms, target):
    start = time.perf_counter()
    result = solve_path(spec, target, seed, timeout_ms)
    values = result['witness']
    code = function(*values) if values is not None else None
    if values is not None and (code != target or expected_code(spec, values) != target):
        raise AssertionError('Nghiệm SMT không khớp mã C/đặc tả')
    return dict(method='SMT', seed=seed, found=code == target, c_calls=int(values is not None),
                seconds=time.perf_counter()-start, observed_code=code, **result)


def compile_library(directory, spec):
    source = generator.generate_json(spec, library=True)
    current = (HERE / 'stock_json_seclab.c').read_text(encoding='utf-8')
    if source != current: raise ValueError('C nộp chưa khớp bộ sinh; không tự ghi đè')
    path = directory / 'target.c'
    path.write_text(source, encoding='utf-8')
    compiler = Path(runner.toolchain()['gcc'])
    environment = dict(os.environ, PATH=str(compiler.parent)+os.pathsep+os.environ.get('PATH', ''))
    command = [str(compiler), '-std=c11', '-O0', '-shared', '-Wall', '-Wextra', '-Werror',
               '-Wno-unused-function', str(path), '-o', str(directory / 'target.dll')]
    process = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=60)
    (directory / 'compile.log').write_text(process.stdout+process.stderr, encoding='utf-8')
    if process.returncode: raise RuntimeError(process.stderr)
    library = ctypes.CDLL(str(directory / 'target.dll'))
    function = library.stock_reserve_guard
    function.argtypes, function.restype = [ctypes.c_int]*6, ctypes.c_int
    return library, function, command


def verify_paths(function, spec):
    results = []
    for code in (0, 2, 3, 4, 5):
        result = solve_path(spec, code, 1, 5000)
        values = result['witness']
        if values is None or function(*values) != code or expected_code(spec, values) != code:
            raise AssertionError('Đối chứng dịch đường đi SMT thất bại: ' + str(code))
        results.append(dict(code=code, witness=values))
    return results


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--budget', type=int, default=50000)
    parser.add_argument('--seeds', type=int, nargs='+', default=[1, 7, 42, 101, 2026])
    parser.add_argument('--smt-timeout-ms', type=int, default=5000)
    args = parser.parse_args()
    if not 1 <= args.budget <= 1000000: parser.error('budget phải từ 1 đến 1000000')
    if args.smt_timeout_ms < 1 or any(seed < 0 or seed > MAX for seed in args.seeds):
        parser.error('timeout phải dương; seed thuộc 0..INT_MAX')
    return args


def metadata(args, command, checks, results):
    import z3
    return dict(target='stock_reserve_guard:return 3', domain=dict(zip(NAMES, LIMITS)),
                budget_c_calls=args.budget, smt_timeout_ms=args.smt_timeout_ms,
                z3_version=z3.get_version_string(), command=command, controls=checks, results=results,
                sha256={name: hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                        for name in ('stock_json_seclab.c', 'stock_spec.json', 'compare_fuzz.py')},
                scope='Nhánh từ chối tràn, không phải crash/lỗi. SMT giải trực tiếp đường đi, không phải concolic.',
                timing='Không gồm biên dịch/đối chứng/nạp Z3. SMT gồm tạo ràng buộc, solve và gọi C.',
                sampling='uniform độc lập; edge-enriched: 20% chọn biên mỗi trường, 80% uniform; cùng miền.',
                censored='Không tìm thấy trong ngân sách không có nghĩa không thể tìm; không tính tỷ lệ tăng tốc từ lượt này.')


def main():
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    args = arguments()
    directory = HERE / 'results' / ('comparison-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    directory.mkdir(parents=True)
    spec = generator.load_spec()
    library, function, command = compile_library(directory, spec)
    checks = verify_paths(function, spec)
    results = []
    for seed in args.seeds:
        for strategy in ('uniform', 'edge-enriched'):
            results.append(blackbox(function, seed, args.budget, strategy, 3))
        results.append(smt(function, spec, seed, args.smt_timeout_ms, 3))
    data = metadata(args, command, checks, results)
    (directory/'summary.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print(directory)


if __name__ == '__main__':
    main()
