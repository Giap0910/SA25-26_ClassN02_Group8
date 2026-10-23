"""Thử cố định khóa escape và token số; chỉ ghi trong thư mục kết quả này."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'attempt-02'
sys.path.insert(0, str(ROOT))
import stock_json_fuzz as target
import generate_simulator as generator
import fuzz_runner as legacy

NAMES = ['stock_json_adapter.c', 'stock_json_seclab.c', 'stock_spec.json',
         'stock_json_fuzz.py', 'fuzz_runner.py', 'generate_simulator.py']


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in NAMES}


def expected(code, quantity=2):
    if code == 0:
        return target.result(0, (10 - quantity, quantity, 10, 0, 1))
    if code == 2:
        return target.result(2, (10, 0, 10, 0, 0))
    return target.result(code)


def add(rows, group, name, data, code, quantity=2):
    rows.append(dict(group=group, name=name, data=data,
                     expected=expected(code, quantity)))


def escaped_cases(rows, raw):
    for index, key in enumerate(target.FIELDS + ('quantity',)):
        token = ('"' + key + '"').encode()
        for style in ('lower', 'upper'):
            spelling = ''.join('\\u' + format(ord(c), '04x' if style == 'lower' else '04X') for c in key)
            data = raw.replace(token, ('"' + spelling + '"').encode())
            add(rows, 'escape', f'escaped-field-{index}-{style}', data, 0)
    for style in ('lower', 'upper'):
        spelling = b'"ite\\u006ds"' if style == 'lower' else b'"ite\\u006Ds"'
        add(rows, 'escape', 'items-hex-' + style, raw.replace(b'"items"', spelling), 0)


def invalid_keys(rows, raw):
    keys = [b'\\u00G1tems', b'\\u00g1tems', b'\\u001', b'\\u',
            b'\\u001ftems', b'\\u007ftems', b'\\uD800tems', b'\\u0100tems',
            b'\\x69tems', b'\\nitems', b'\\u0069temz']
    for index, key in enumerate(keys):
        add(rows, 'escape', f'invalid-key-{index}', raw.replace(b'items', key), 100)
    duplicate = raw[:-1] + b',"ite\\u006ds":[{"quantity":2}]}'
    add(rows, 'escape', 'duplicate-decoded-items', duplicate, 100)
    for length in (30, 31, 32):
        add(rows, 'escape', f'unknown-key-length-{length}', raw.replace(b'items', b'x' * length), 100)


def number_cases(rows, raw):
    accepted = [(b'2.0', 2), (b'2E+0', 2), (b'200E-2', 2), (b'0.02e2', 2),
                (b'2e0000', 2), (b'2E-0', 2), (b'20e-1', 2), (b'1e1', 10)]
    rejected = [b'99e9', b'2e10010', b'2e-10010', b'2e10009', b'2e-10009',
                b'1.5', b'2e', b'2E+', b'2E-', b'2.', b'.2', b'+2', b'02',
                b'2e+-1', b'2e1.0', b'2147483648', b'-2147483649']
    for index, (token, quantity) in enumerate(accepted):
        add(rows, 'number', f'exact-number-{index}', raw.replace(b'"quantity":2', b'"quantity":' + token), 0, quantity)
    for index, token in enumerate(rejected):
        add(rows, 'number', f'rejected-number-{index}', raw.replace(b'"quantity":2', b'"quantity":' + token), 100)
    for token, code in [(b'-0', 103), (b'0E+0', 103), (b'0e10009', 103),
                        (b'0e10010', 100), (b'11e0', 2), (b'100.0', 2), (b'101e0', 103)]:
        add(rows, 'number', 'quantity-' + token.decode(), raw.replace(b'"quantity":2', b'"quantity":' + token), code)


def boundary_cases(rows, raw):
    for size in (63, 64, 65):
        token = b'2.' + b'0' * (size - 2)
        add(rows, 'number', f'token-bytes-{size}', raw.replace(b'"quantity":2', b'"quantity":' + token), 0 if size <= 64 else 100)
    for size in (16383, 16384, 16385):
        add(rows, 'byte-boundary', f'input-bytes-{size}', raw + b' ' * (size - len(raw)), 0 if size <= 16384 else 101)


def combined_cases(rows, raw):
    for action in (0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 13, 14, 15):
        data = target.encode(target.fixture(action=action))
        data = data.replace(b'"items"', b'"ite\\u006Ds"').replace(b'"quantity":2', b'"quantity":200E-2')
        state = 1 if action & 3 == 0 else 2 if action & 3 == 1 else 3
        available, reserved = (10, 0) if state == 2 else (8, 2 if state == 1 else 0)
        va, vr = (available, reserved) if action & 8 else (10, 0)
        rows.append(dict(group='combined', name=f'escaped-exponent-action-{action}', data=data,
                         expected=target.result(0, (available, reserved, va, vr, state))))


def cases():
    rows, raw = [], target.encode(target.fixture())
    add(rows, 'control', 'plain-valid', raw, 0)
    escaped_cases(rows, raw)
    invalid_keys(rows, raw)
    number_cases(rows, raw)
    boundary_cases(rows, raw)
    combined_cases(rows, raw)
    return rows


def manifest(rows):
    directory = OUT / 'inputs'
    directory.mkdir()
    records = []
    for index, row in enumerate(rows, 1):
        data = row.pop('data')
        path = directory / f'{index:03}-{row["name"]}.json'
        path.write_bytes(data)
        row['input'] = str(path.relative_to(OUT))
        row['sha256'] = hashlib.sha256(data).hexdigest()
        row['bytes'] = len(data)
        row['oracle'] = target.oracle(data)
        if row['oracle'] != row['expected']:
            raise RuntimeError('Kỳ vọng thủ công khác oracle: ' + row['name'])
        records.append(row)
    (OUT / 'manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    return records


def run_cases(binary, directory, rows):
    directory.mkdir(exist_ok=True)
    results = []
    for index, row in enumerate(rows, 1):
        data = (OUT / row['input']).read_bytes()
        outcome, actual, log = target.execute(binary, data, directory, index)
        passed = outcome == 'ok' and actual == row['expected']
        results.append(dict(name=row['name'], group=row['group'], outcome=outcome,
                            actual=actual, expected=row['expected'], passed=passed, log=log))
    (directory / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    return dict(cases=len(results), passed=sum(row['passed'] for row in results),
                failures=[row for row in results if not row['passed']])


def run():
    before = hashes()
    OUT.mkdir()
    rows = manifest(cases())
    spec, tools = generator.load_spec(), target.toolchain()
    source = OUT / 'stock_json_target.c'
    source.write_text(generator.generate_json(spec), encoding='utf-8')
    normal = OUT / 'normal'
    normal.mkdir()
    binary = legacy.compile_target(normal, tools['gcc'], source, 'stock_json_target')
    report = dict(kind='Ca kiểm thử cố định, không phải fuzzer tự khám phá', cases=len(rows))
    report['normal'] = run_cases(binary, normal / 'targeted', rows)
    report['coverage'] = coverage(normal, tools['gcov'])
    print('Normal:', report['normal'], flush=True)
    sanitizer = OUT / 'sanitizer'
    sanitizer.mkdir()
    compiler = target.sanitizer_compiler()
    sanitized, command = target.compile_sanitized(source, sanitizer, compiler)
    report['sanitizer'] = run_cases(sanitized, sanitizer / 'targeted', rows)
    report['sanitizer_command'], report['leak_sanitizer'] = command, False
    report['source_hashes_before'], report['source_hashes_after'] = before, hashes()
    report['source_unchanged'] = before == hashes()
    (OUT / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Sanitizer:', report['sanitizer'], flush=True)
    print('Saved:', OUT, flush=True)


def coverage(directory, gcov):
    hit, branches, lines, total = legacy.coverage(directory, gcov, 'stock_json_target.c')
    return dict(line_hits=len(hit), line_total=len(lines), branch_hits=len(branches),
                branch_total=len(total), scope='Ca cố định qua CLI; gcov toàn file C sinh ra')


if __name__ == '__main__':
    run()
