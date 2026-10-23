"""Sinh biến thể JSON, đối chiếu oracle và sanitizer; không sửa mã nghiệp vụ."""
import collections
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PREVIOUS = ROOT / 'results/targeted-escape-number-20261023-01/attempt-02'
BASELINE = ROOT / 'results/stock-json-20261022-233209-5a40b58a'
sys.path.insert(0, str(ROOT))
import stock_json_fuzz as target
import generate_simulator as generator
import fuzz_runner as legacy

NAMES = ['stock_json_adapter.c', 'stock_json_seclab.c', 'stock_spec.json',
         'stock_json_fuzz.py', 'fuzz_runner.py', 'generate_simulator.py',
         'test_generator.py', 'compare_fuzz.py']
SEEDS = (1, 7, 42)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def hashes():
    return {name: digest((ROOT / name).read_bytes()) for name in NAMES}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare_corpus():
    rows = json.loads((PREVIOUS / 'manifest.json').read_text(encoding='utf-8'))
    good, controls = [], []
    for row in rows:
        data = (PREVIOUS / row['input']).read_bytes()
        assert digest(data) == row['sha256']
        assert target.oracle(data) == row['expected']
        (good if row['expected']['code'] == 0 else controls).append((row, data))
    assert good and controls
    for label, group in [('corpus', good), ('controls', controls)]:
        directory = OUT / label
        directory.mkdir()
        for index, (row, data) in enumerate(group):
            (directory / f'{index:03}.json').write_bytes(data)
        save(directory / 'manifest.json', [row for row, _ in group])
    return good, controls, {digest(data) for _, data in good + controls}


def escaped_key(key, rng):
    parts = []
    for char in key:
        style = rng.randrange(3)
        parts.append(char if style == 0 else '\\u' + format(ord(char), '04x' if style == 1 else '04X'))
    return '"' + ''.join(parts) + '"'


def numeric_token(value, rng):
    zeros = rng.randrange(1, 9)
    exponent = rng.choice(['e', 'E'])
    choices = [str(value), f'{value}.' + '0' * zeros,
               f'{value}{exponent}+0000', f'{value}{exponent}-0']
    if value == 0:
        choices += ['-0', '0E+9999', '-0.000e-10009']
    if value != 0:
        digits = str(abs(value))
        choices.append(str(value) + '0' * zeros + exponent + '-' + str(zeros))
        choices.append(('-' if value < 0 else '') + '0.' + digits + exponent + '+' + str(len(digits)))
    return rng.choice(choices)


def render(value, rng):
    space = rng.choice(['', ' ', '\n', '\t', '\r\n'])
    if isinstance(value, dict):
        keys = list(value)
        rng.shuffle(keys)
        pairs = [escaped_key(key, rng) + space + ':' + space + render(value[key], rng) for key in keys]
        return '{' + space + (',' + space).join(pairs) + space + '}'
    if isinstance(value, list):
        return '[' + space + (',' + space).join(render(row, rng) for row in value) + space + ']'
    return numeric_token(value, rng)


def successful_fixture(base, rng):
    value = target.parse(base)
    quantity = rng.choice([1, 2, 10, 99, 100, rng.randint(1, 100)])
    count = rng.randint(1, min(quantity, rng.choice([1, 2, 5, 100])))
    cuts = sorted(rng.sample(range(1, quantity), count - 1))
    amounts = [b - a for a, b in zip([0] + cuts, cuts + [quantity])]
    available = rng.choice([quantity, 100, 2147483647, rng.randint(quantity, 2147483647)])
    reserved = rng.choice([0, 1, 2147483647 - quantity, rng.randint(0, 2147483647 - quantity)])
    value.update(available=available, reserved=reserved, variant_available=available,
                 variant_reserved=reserved, action=rng.randrange(16),
                 items=[{'quantity': amount} for amount in amounts])
    assert target.oracle(target.encode(value))['code'] == 0
    return value


def invalid_variant(value, rng):
    kind = rng.randrange(10)
    raw = target.encode(value)
    if kind == 0:
        return 'duplicate-decoded-key', raw[:-1] + b',"\\u0061vailable":1}', 100
    if kind == 1:
        return 'invalid-key-escape', raw.replace(b'"items"', b'"ite\\u00Gds"'), 100
    if kind == 2:
        return 'unknown-key-length', raw.replace(b'"items"', b'"' + b'x' * rng.randint(30, 70) + b'"'), 100
    if kind == 3:
        return 'trailing-bytes', raw + rng.choice([b'[]', b'\x00', b' true']), 100
    if kind == 4:
        token = b'0.' + b'0' * rng.randint(63, 90)
        return 'long-token', raw.replace(b'"action":' + str(value['action']).encode(), b'"action":' + token), 100
    if kind == 5:
        return 'input-too-long', raw + b' ' * (rng.randint(16385, 16420) - len(raw)), 101
    return domain_variant(value, rng, kind)


def domain_variant(value, rng, kind):
    if kind == 6:
        value['items'][0]['quantity'] = rng.choice([-1, 0, 101])
        return 'quantity-domain', target.encode(value), 103
    if kind == 7:
        value['action'] = rng.choice([-1, 16, 2147483647])
        return 'action-domain', target.encode(value), 100
    if kind == 8:
        value['available'] = -rng.randint(1, 100)
        return 'stock-domain', target.encode(value), 104
    value['items'] = [{'quantity': 1}] * rng.randint(101, 110)
    return 'record-count', target.encode(value), 102


def generate(seed, corpus):
    rng, seen, rows = random.Random(seed), set(), []
    while len(rows) < 500:
        base = rng.choice(corpus)[1]
        value = successful_fixture(base, rng)
        canonical = target.encode(value)
        if len(rows) % 4:
            kind, data, code = 'equivalent-json', render(value, rng).encode('ascii'), 0
        else:
            kind, data, code = invalid_variant(value, rng)
        if digest(data) in seen:
            continue
        expected = target.oracle(data)
        assert expected['code'] == code, (kind, expected, code)
        if kind == 'equivalent-json':
            assert expected == target.oracle(canonical)
        seen.add(digest(data))
        rows.append(dict(kind=kind, data=data, expected=expected,
                         parent_sha256=digest(base), canonical=canonical.decode()))
    return rows


def write_inputs(seed, rows, old):
    directory = OUT / f'seed-{seed}'
    directory.mkdir()
    records = []
    for index, row in enumerate(rows):
        path = directory / f'input-{index:04}.json'
        path.write_bytes(row['data'])
        records.append(dict(index=index, kind=row['kind'], input=str(path.relative_to(OUT)),
                            sha256=digest(row['data']), bytes=len(row['data']), expected=row['expected'],
                            parent_sha256=row['parent_sha256'], canonical=row['canonical'],
                            outside_previous_83=digest(row['data']) not in old))
    save(directory / 'manifest.json', records)
    return records


def execute(binary, path):
    try:
        p = subprocess.run([str(binary), str(path)], cwd=binary.parent, capture_output=True, timeout=2)
    except subprocess.TimeoutExpired:
        return dict(outcome='timeout', actual=None, log='timeout 2 seconds')
    log = (p.stdout + p.stderr).decode('utf-8', errors='replace')
    if any(x in log for x in ['ERROR: AddressSanitizer', 'runtime error:', 'UndefinedBehaviorSanitizer:']):
        return dict(outcome='sanitizer_failure', actual=None, log=log)
    if p.returncode != 0:
        return dict(outcome='process_failure', actual=None, exit=p.returncode, log=log)
    try:
        actual = json.loads(p.stdout)
    except (ValueError, UnicodeError):
        return dict(outcome='output_failure', actual=None, log=log)
    expected = target.oracle(path.read_bytes())
    return dict(outcome='ok' if actual == expected else 'oracle_mismatch', actual=actual, log=log)


def shrink(binary, data, outcome, folder):
    folder.mkdir()
    path, attempts, width = folder / 'candidate.json', 0, max(1, len(data) // 2)
    while width and attempts < 80:
        changed = False
        for pos in range(0, len(data), width):
            candidate = data[:pos] + data[pos + width:]
            path.write_bytes(candidate)
            attempts += 1
            if execute(binary, path)['outcome'] == outcome:
                data, changed = candidate, True
                break
            if attempts >= 80:
                break
        if not changed:
            width //= 2
    (folder / 'minimized.json').write_bytes(data)
    return dict(attempts=attempts, bytes=len(data), replay=execute(binary, folder / 'minimized.json'))


def run_records(binary, records, output):
    events = []
    for row in records:
        path = OUT / row['input']
        assert digest(path.read_bytes()) == row['sha256']
        event = dict(index=row['index'], sha256=row['sha256'], **execute(binary, path))
        events.append(event)
        if event['outcome'] != 'ok':
            save(output, events)
            detail = shrink(binary, path.read_bytes(), event['outcome'], output.with_suffix(''))
            save(output.with_suffix('.failure.json'), dict(original=event, reduction=detail))
            raise RuntimeError('Bất thường đã lưu và thử thu nhỏ: ' + str(output))
    save(output, events)
    return dict(cases=len(events), passed=len(events), codes=dict(collections.Counter(e['actual']['code'] for e in events)))


def coverage_set(path):
    lines, branches, line = set(), set(), 0
    for text in path.read_text(encoding='utf-8').splitlines():
        match = re.match(r'\s*([^:]+):\s*(\d+):', text)
        if match:
            count, line = match.group(1).strip(), int(match.group(2))
            if count.rstrip('*').isdigit() and int(count.rstrip('*')) > 0:
                lines.add(line)
        match = re.match(r'branch\s+(\d+)\s+taken\s+(\d+)', text)
        if match and int(match.group(2)) > 0:
            branches.add((line, int(match.group(1))))
    return lines, branches


def coverage_comparison(source, normal, gcov):
    assert source.read_bytes() == (BASELINE / 'stock_json_target.c').read_bytes()
    assert source.read_bytes() == (PREVIOUS / 'stock_json_target.c').read_bytes()
    hit, branch, total, total_branch = legacy.coverage(normal, gcov, 'stock_json_target.c')
    old_lines, old_branches = set(), set()
    paths = list(BASELINE.glob('*/*.gcov')) + list((PREVIOUS / 'normal').glob('*.gcov'))
    for path in paths:
        lines, branches = coverage_set(path)
        old_lines.update(lines)
        old_branches.update(branches)
    return dict(line_hits=len(hit), line_total=len(total), branch_hits=len(branch),
                branch_total=len(total_branch), baseline_lines=len(old_lines), baseline_branches=len(old_branches),
                new_lines=sorted(hit - old_lines), new_branches=sorted(branch - old_branches),
                merged_lines=len(hit | old_lines), merged_branches=len(branch | old_branches))


def prepare_build(before):
    snapshots = OUT / 'source_snapshot'
    snapshots.mkdir()
    for name in NAMES:
        shutil.copyfile(ROOT / name, snapshots / name)
    source = OUT / 'stock_json_target.c'
    source.write_text(generator.generate_json(generator.load_spec()), encoding='utf-8')
    tools, compiler = target.toolchain(), target.sanitizer_compiler()
    normal, sanitized = OUT / 'normal', OUT / 'sanitizer'
    normal.mkdir()
    sanitized.mkdir()
    binary = legacy.compile_target(normal, tools['gcc'], source, 'stock_json_target')
    checked, command = target.compile_sanitized(source, sanitized, compiler)
    save(OUT / 'metadata.json', dict(hashes_before=before, source_sha256=digest(source.read_bytes()),
         seeds=SEEDS, iterations_per_seed=500, tools=tools, sanitizer_command=command,
         leak_sanitizer=False, timeout_seconds=2, script_sha256=digest(Path(__file__).read_bytes()),
         method='Sinh biến thể có cấu trúc và kiểm tra tính tương đương; không concolic, không coverage-guided',
         scope='Mỗi input khởi tạo lại state; không HTTP/DB/PayOS, không chuỗi request giữ trạng thái'))
    return source, binary, checked, tools


def run():
    before = hashes()
    corpus, controls, old = prepare_corpus()
    datasets = {seed: generate(seed, corpus) for seed in SEEDS}
    for seed in SEEDS:
        assert [r['data'] for r in datasets[seed]] == [r['data'] for r in generate(seed, corpus)]
    source, binary, checked, tools = prepare_build(before)
    control_rows = [dict(index=i, input=f'controls/{i:03}.json', sha256=digest(data)) for i, (_, data) in enumerate(controls)]
    report = dict(corpus=len(corpus), fixed_controls=len(controls), results=[], complete=False)
    for mode, executable in [('normal', binary), ('sanitizer', checked)]:
        report[mode + '_controls'] = run_records(executable, control_rows, OUT / f'{mode}-controls.json')
    for seed, rows in datasets.items():
        records = write_inputs(seed, rows, old)
        entry = dict(seed=seed, groups=dict(collections.Counter(r['kind'] for r in rows)),
                     outside_previous_83=sum(r['outside_previous_83'] for r in records))
        for mode, executable in [('normal', binary), ('sanitizer', checked)]:
            entry[mode] = run_records(executable, records, OUT / f'{mode}-{seed}.json')
            print(mode, seed, entry[mode], flush=True)
        report['results'].append(entry)
        save(OUT / 'summary.json', report)
    report['coverage'] = coverage_comparison(source, binary.parent, tools['gcov'])
    report.update(complete=True, hashes_after=hashes(), source_unchanged=before == hashes())
    assert report['source_unchanged']
    save(OUT / 'summary.json', report)
    print('COMPLETE', report['coverage'], flush=True)


if __name__ == '__main__':
    run()
