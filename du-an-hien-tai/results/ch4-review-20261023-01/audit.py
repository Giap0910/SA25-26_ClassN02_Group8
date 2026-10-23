"""Đối chiếu coverage Ch4 và chạy các đường API/cấp phát ngoài đầu vào JSON thô."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import stock_json_fuzz as target


def read_coverage(path):
    hits, totals, lines, all_lines, source = set(), set(), set(), set(), {}
    line, index = 0, 0
    for text in path.read_text(encoding='utf-8').splitlines():
        match = re.match(r'\s*([^:]+):\s*(\d+):(.*)', text)
        if match:
            count, line, index = match[1].strip(), int(match[2]), 0
            source[line] = match[3]
            if line and count != '-':
                all_lines.add(line)
                if count.rstrip('*').isdigit() and int(count.rstrip('*')) > 0:
                    lines.add(line)
        if text.strip().startswith('branch '):
            key = (line, index)
            totals.add(key)
            if re.search(r'taken [1-9]\d*', text):
                hits.add(key)
            index += 1
    return hits, totals, lines, all_lines, source


def historical_paths():
    base = ROOT / 'results/stock-json-20261022-233209-5a40b58a'
    extra = ROOT / 'results/targeted-escape-number-20261023-01/attempt-02/normal'
    recent = ROOT / 'results/structured-variants-20261023-01/normal'
    return list(base.glob('*/*.gcov')) + list(extra.glob('*.gcov')) + list(recent.glob('*.gcov'))


def verify_branch_identity():
    sample = OUT / 'branch-identity.gcov'
    sample.write_text(' 1: 1:if (a && b)\nbranch 0 taken 1\nbranch 1 taken 0\n'
                      'branch 0 taken 0\nbranch 1 taken 1\n', encoding='utf-8')
    hits, total, _, _, _ = read_coverage(sample)
    assert hits == {(1, 0), (1, 3)}
    assert total == {(1, 0), (1, 1), (1, 2), (1, 3)}


def classify(line):
    if line <= 37:
        return 'Nhánh nội bộ bị tiền điều kiện JSON/chuỗi reserve-settle che; không nới hợp đồng để tăng coverage.'
    if line == 143:
        return 'Biên helper đã thử riêng trong probe và hồi quy; không đi tới với NULL/size sai qua scanner.'
    if line == 156:
        return 'Nhánh vòng lặp khi count<=first bị return trước đó chặn; phân tích mã, chưa chứng minh SMT.'
    if line in (251, 257, 258, 306):
        return 'Điều kiện bất biến/short-circuit bị kiểm tra trước che; chưa là bằng chứng lỗi hay chứng minh toàn C.'
    if line in (263, 267, 275, 277):
        return 'NULL, cấp phát hoặc API chuỗi: đã bổ sung probe riêng, giữ khác phạm vi CLI fuzz.'
    if line == 288:
        return 'Nhánh lỗi snprintf; fixture cố định với bốn int32 nằm trong 256 byte, chưa tiêm lỗi thư viện.'
    if line in (294, 296, 300):
        return 'Lỗi môi trường CLI: argc, fopen, fread; không phải nhánh parser nhận JSON hợp lệ.'
    return 'Guard là entry point độc lập, không được gọi bởi CLI này; xem bằng chứng guard riêng.'


def baseline(paths):
    hits, totals, lines, all_lines, sources = set(), set(), set(), set(), {}
    expected = (OUT / 'stock_json_target.c').read_bytes()
    for path in paths:
        assert (path.parent / 'stock_json_target.c').read_bytes() == expected, str(path)
        h, t, l, a, s = read_coverage(path)
        hits.update(h)
        totals.update(t)
        lines.update(l)
        all_lines.update(a)
        sources.update(s)
    missing = [dict(line=n, branch=i, code=sources[n].strip(), assessment=classify(n))
               for n, i in sorted(totals - hits)]
    return dict(files=[str(p.relative_to(ROOT)) for p in paths], line_hits=len(lines),
                line_total=len(all_lines), branch_hits=len(hits), branch_total=len(totals), missing=missing)


def command(args, name, env=None):
    process = subprocess.run(args, cwd=OUT, capture_output=True, env=env, timeout=60)
    (OUT / name).write_bytes(process.stdout + process.stderr)
    if process.returncode:
        raise RuntimeError(f'{name}: exit {process.returncode}')
    return dict(command=[str(a) for a in args], exit=process.returncode, log=name)


def run_probes():
    tools = target.toolchain()
    gcc = tools['gcc']
    build = command([gcc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                     '-O0', '--coverage', 'probe.c', '-o', 'probe.exe'], 'compile.log')
    executed = command([str(OUT / 'probe.exe')], 'probe.log')
    measured = command([tools['gcov'], '-b', '-c', 'probe.c'], 'gcov.log')
    compiler = target.sanitizer_compiler()
    flags = ['-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function', '-O1', '-g',
             '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
    sanitized = command([str(compiler), *flags, 'probe.c', '-o', 'probe-sanitized.exe'], 'sanitizer-build.log')
    env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
    checked = command([str(OUT / 'probe-sanitized.exe')], 'sanitizer.log', env)
    h, t, l, a, _ = read_coverage(OUT / 'stock_json_target.c.gcov')
    return dict(build=build, execution=executed, gcov=measured, sanitizer_build=sanitized,
                sanitizer_execution=checked, line_hits=len(l), line_total=len(a),
                branch_hits=len(h), branch_total=len(t), leak_sanitizer=False,
                scope='Ca cố định gọi API/helper và tiêm lỗi calloc; không phải chiến dịch fuzz hoặc coverage CLI.')


def regression_tests():
    import unittest
    import test_generator as tests
    tests.runner.OUTPUT = OUT
    names = ['test_json_adapter_and_wrap', 'test_json_allocation_failure', 'test_json_allocation_balance',
             'test_json_integer_rejects_unsafe_direct_inputs', 'test_seclab_numeric_entry_uses_json_pipeline',
             'test_submission_c_matches_generator']
    suite = unittest.TestSuite(tests.GeneratorTests(name) for name in names)
    with (OUT / 'regression.log').open('w', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    assert result.wasSuccessful() and not result.skipped
    return dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped))


def main():
    verify_branch_identity()
    names = ['stock_json_adapter.c', 'stock_json_seclab.c', 'stock_spec.json', 'stock_json_fuzz.py',
             'fuzz_runner.py', 'generate_simulator.py', 'test_generator.py', 'Baocao.docx', 'badminton_spec.xlsx']
    before = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    summary = dict(source_sha256=hashlib.sha256((OUT / 'stock_json_target.c').read_bytes()).hexdigest(),
                   baseline=baseline(historical_paths()), probes=run_probes(), regressions=regression_tests())
    after = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    assert before == after
    summary.update(protected_files_unchanged=True, hashes=after,
                   correction='Bỏ merged_branches=329 trong hồ sơ cũ: branch ID gcov không đồng nhất với thứ tự nhánh theo dòng của runner.')
    (OUT / 'audit.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['hashes', 'baseline', 'probes']}, ensure_ascii=False))
    print('Baseline:', summary['baseline']['line_hits'], '/', summary['baseline']['line_total'],
          'lines;', summary['baseline']['branch_hits'], '/', summary['baseline']['branch_total'], 'branches')


if __name__ == '__main__':
    main()
