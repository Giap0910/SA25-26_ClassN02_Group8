"""Fuzz JSON trên C tồn kho sinh từ đặc tả; không gọi HTTP/database."""
import argparse
import csv
import ctypes
from decimal import Decimal
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
import uuid

import fuzz_runner as legacy
import generate_simulator as generator

HERE = Path(__file__).resolve().parent
MAX_BYTES, MAX_RECORDS = 16384, 100
FIELDS = ('available', 'reserved', 'variant_available', 'variant_reserved', 'action', 'items')
OUTPUTS = ('available', 'reserved', 'variant_available', 'variant_reserved', 'state')
BAD = ('crash', 'timeout', 'invariant_failure', 'oracle_mismatch')


def fixture(quantity=2, action=0):
    return dict(available=10, reserved=0, variant_available=10, variant_reserved=0,
                action=action, items=[{'quantity': quantity}])


def encode(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode('ascii')


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('Khóa trùng')
        result[key] = value
    return result


def exact_number(token):
    if len(token) > 64: raise ValueError('Token số quá dài')
    exponent = re.split('[eE]', token)
    if len(exponent) > 1 and abs(int(exponent[1])) > 10009: raise ValueError('Số mũ quá lớn')
    value = Decimal(token)
    if not value.is_finite() or not -2147483648 <= value <= 2147483647:
        raise ValueError('Ngoài int32')
    if value != value.to_integral_value(): raise ValueError('Không phải số nguyên chính xác')
    return int(value)


def parse(data):
    def invalid_constant(_): raise ValueError('Hằng số ngoài JSON')
    value = json.loads(data.decode('utf-8'), object_pairs_hook=strict_object,
                       parse_int=exact_number, parse_float=exact_number, parse_constant=invalid_constant)
    if type(value) is not dict or set(value) != set(FIELDS): raise ValueError('Sai schema')
    if any(type(value[key]) is not int for key in FIELDS[:-1]): raise ValueError('Sai kiểu')
    if not 0 <= value['action'] <= 15 or type(value['items']) is not list: raise ValueError('Sai action/items')
    for row in value['items']:
        if type(row) is not dict or set(row) != {'quantity'} or type(row['quantity']) is not int:
            raise ValueError('Sai record')
    return value


def result(code, values=(0, 0, 0, 0, 0)):
    return dict(code=code, **dict(zip(OUTPUTS, values)))


def oracle(data):
    if len(data) > MAX_BYTES: return result(101)
    try:
        value = parse(data)
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        return result(100)
    quantities = [row['quantity'] for row in value['items']]
    if not 1 <= len(quantities) <= MAX_RECORDS: return result(102)
    if any(not 1 <= quantity <= 100 for quantity in quantities) or sum(quantities) > 100:
        return result(103)
    return stock_oracle(value, sum(quantities))


def stock_oracle(value, quantity):
    a, r, va, vr, action = [value[key] for key in FIELDS[:-1]]
    initial = (a, r, va, vr, 0)
    variant = bool(action & 8)
    if a < 0 or r < 0 or variant and (va < 0 or vr < 0 or a != va or r != vr):
        return result(104, initial)
    checks = [(a < quantity, 2), (r + quantity > legacy.MAXIMUM, 3),
              (variant and va < quantity, 4), (variant and vr + quantity > legacy.MAXIMUM, 5)]
    for invalid, code in checks:
        if invalid: return result(code, initial)
    status, values = legacy.oracle(legacy.pack(a, r, va, vr, quantity, action))
    if status != 'accepted': raise ValueError('Oracle nghiệp vụ không nhất quán')
    return result(0, values)


def base_cases():
    cases = [('reserve', fixture(), 0), ('cancel-twice', fixture(action=5), 0),
             ('settle-twice', fixture(action=6), 0), ('variant', fixture(action=8), 0)]
    changes = [('empty', {'items': []}, 102), ('many-records', {'items': [{'quantity': 1}] * 101}, 102),
               ('aggregate-limit', {'items': [{'quantity': 51}, {'quantity': 50}]}, 103),
               ('quantity-zero', {'items': [{'quantity': 0}]}, 103), ('quantity-negative', {'items': [{'quantity': -1}]}, 103),
               ('quantity-101', {'items': [{'quantity': 101}]}, 103), ('stock-missing', {'available': 0}, 2),
               ('reserved-overflow', {'reserved': legacy.MAXIMUM}, 3), ('negative-stock', {'available': -1}, 104),
               ('variant-inconsistent', {'action': 8, 'variant_available': 9}, 104),
               ('max-records', {'available': 100, 'items': [{'quantity': 1}] * 100}, 0),
               ('max-int', {'available': legacy.MAXIMUM, 'reserved': legacy.MAXIMUM-2}, 0)]
    return cases + [(name, dict(fixture(), **changes), code) for name, changes, code in changes]


def golden_cases():
    rows = [(name, encode(value), code) for name, value, code in base_cases()]
    raw = encode(fixture())
    changes = [('exact-decimal', b'2.0', 0), ('exact-exponent', b'20e-1', 0),
               ('fraction', b'1.5', 100), ('overflow-number', b'2147483648', 100),
               ('string', b'"2"', 100), ('boolean', b'true', 100), ('null', b'null', 100),
               ('leading-zero', b'02', 100), ('huge-exponent', b'2e9999', 100),
               ('negative-zero', b'-0', 103), ('long-token', b'0.' + b'0'*64, 100)]
    rows += [(name, raw.replace(b'"quantity":2', b'"quantity":' + value), code) for name, value, code in changes]
    rows += [('missing-key', encode({k:v for k,v in fixture().items() if k != 'reserved'}), 100),
             ('extra-key', encode(dict(fixture(), extra=1)), 100), ('duplicate-key', raw[:-1]+b',"available":10}', 100),
             ('invalid-utf8', b'\xff'+raw, 100), ('embedded-nul', raw+b'\0', 100),
             ('trailing-data', raw+b'[]', 100), ('trailing-comma', raw[:-1]+b',}', 100),
             ('truncated', raw[:-1], 100), ('root-array', b'[]', 100), ('blank', b'', 100),
             ('nested', raw.replace(b'"quantity":2', b'"quantity":[[2]]'), 100),
             ('limit-bytes', raw+b' '*(MAX_BYTES-len(raw)), 0),
             ('over-limit-bytes', raw+b' '*(MAX_BYTES-len(raw)+1), 101),
             ('escaped-key', raw.replace(b'"available"', b'"\\u0061vailable"'), 0)]
    return rows


def execute(binary, data, directory, index):
    path = directory / f'input-{index:05}.json'; path.write_bytes(data)
    try:
        process = subprocess.run([str(binary), str(path)], cwd=directory, capture_output=True, timeout=2)
    except subprocess.TimeoutExpired:
        return 'timeout', {}, ''
    log = (process.stdout + process.stderr).decode('utf-8', errors='replace')
    if process.returncode == 10: return 'invariant_failure', {}, log
    if process.returncode < 0 or process.returncode >= 0x80000000: return 'crash', {}, log
    if process.returncode: raise RuntimeError(f'Target lỗi môi trường: {process.returncode}: {log}')
    try:
        actual = json.loads(process.stdout)
    except (ValueError, UnicodeError):
        return 'oracle_mismatch', {}, log
    return ('ok' if actual == oracle(data) else 'oracle_mismatch'), actual, log


def regressions(binary, directory):
    rows = []
    for index, (name, data, expected) in enumerate(golden_cases()):
        if oracle(data)['code'] != expected: raise RuntimeError('Golden không khớp oracle: ' + name)
        outcome, actual, log = execute(binary, data, directory, index)
        rows.append(dict(name=name, expected_code=expected, actual=actual, outcome=outcome, log=log))
    (directory/'regression.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    if any(row['outcome'] != 'ok' for row in rows): raise RuntimeError('Hồi quy C không đạt: ' + str(directory))
    return len(rows)


def mutate(data, rng):
    value = bytearray(data)
    if not value: return b'{}'
    position = rng.randrange(len(value))
    mode = rng.randrange(3)
    if mode == 0: value[position] = rng.randrange(256)
    elif mode == 1: value.insert(position, rng.randrange(256))
    else: del value[position]
    return bytes(value)


def structured(rng):
    value = fixture(action=rng.randrange(16))
    value['available'] = rng.choice(legacy.BOUNDARIES + [-1])
    value['reserved'] = rng.choice(legacy.BOUNDARIES + [-1])
    value['variant_available'], value['variant_reserved'] = value['available'], value['reserved']
    count = rng.choice([0, 1, 2, 3, 99, 100, 101])
    value['items'] = [{'quantity': rng.choice([-1, 0, 1, 2, 99, 100, 101])} for _ in range(count)]
    return encode(value)


def candidate(rng, corpus, mode):
    if rng.randrange(3) == 0: return structured(rng)
    if mode == 'black-box': return bytes(rng.randrange(256) for _ in range(rng.randrange(0, 300)))
    return mutate(rng.choice(corpus), rng)


def campaign(binary, directory, tools, args, mode, seed):
    rng = random.Random(seed)
    corpus = [data for _, data, _ in golden_cases() if len(data) < 4096]
    lines, branches, counts, used = set(), set(), dict.fromkeys(BAD, 0), 0
    start = time.perf_counter()
    with (directory/'events.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream); writer.writerow(['iteration','outcome','code','lines','branches'])
        for index in range(1, args.iterations+1):
            if time.perf_counter()-start >= args.seconds: break
            data = candidate(rng, corpus, mode)
            outcome, actual, log = execute(binary, data, directory, index)
            hit, branch, total, total_branch = legacy.coverage(directory, tools['gcov'], 'stock_json_target.c')
            if mode == 'coverage-guided' and (hit-lines or branch-branches): corpus.append(data)
            lines.update(hit); branches.update(branch); used = index
            writer.writerow([index,outcome,actual.get('code'),len(lines),len(branches)])
            if outcome != 'ok':
                counts[outcome] += 1; (directory/'failure.txt').write_text(log, encoding='utf-8'); break
    if not used: raise RuntimeError('Chưa thực thi input nào')
    return dict(mode=mode,seed=seed,iterations=used,seconds=time.perf_counter()-start,
                line_hits=len(lines),line_total=len(total),branch_hits=len(branches),branch_total=len(total_branch),
                corpus=len(corpus),**counts)


def shared_check(source, root, gcc):
    library = root/'stock_json.dll'
    command = [gcc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-DSTOCK_JSON_LIBRARY', str(source), '-o', str(library)]
    process = subprocess.run(command, capture_output=True, text=True)
    (root/'shared-compile.log').write_text(process.stdout+process.stderr, encoding='utf-8')
    if process.returncode: raise RuntimeError(process.stderr)
    target = ctypes.CDLL(str(library)); function = target.stock_json
    function.argtypes, function.restype = [ctypes.c_char_p], ctypes.c_int
    count = 0
    for name, data, expected in golden_cases():
        if b'\0' in data: continue
        if function(data) != expected: raise RuntimeError('Hàm wrap lệch oracle: ' + name)
        count += 1
    return count


def toolchain():
    portable = legacy.OUTPUT/'toolchain/mingw64/bin'
    tools = {name: str(portable/(name+'.exe')) if (portable/(name+'.exe')).exists() else shutil.which(name)
             for name in ('gcc', 'gcov')}
    if not all(tools.values()): raise RuntimeError('Thiếu GCC/gcov')
    os.environ['PATH'] = str(Path(tools['gcc']).parent)+os.pathsep+os.environ.get('PATH','')
    return tools


def run(args):
    spec, tools = generator.load_spec(), toolchain()
    root = legacy.OUTPUT/('stock-json-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    root.mkdir(parents=True)
    source = root/'stock_json_target.c'; source.write_text(generator.generate_json(spec), encoding='utf-8')
    (root/'stock_json_seclab.c').write_text(generator.generate_json(spec, library=True), encoding='utf-8')
    save_metadata(root, source, spec, args, tools)
    directory = root/'regression'; directory.mkdir()
    binary = legacy.compile_target(directory, tools['gcc'], source, 'stock_json_target')
    report = dict(regressions=regressions(binary, directory), shared_library_cases=shared_check(source, root, tools['gcc']), results=[])
    for seed in args.seeds:
        for mode in ('black-box', 'coverage-guided'):
            directory = root/f'{mode}-{seed}'; directory.mkdir()
            binary = legacy.compile_target(directory, tools['gcc'], source, 'stock_json_target')
            report['results'].append(campaign(binary,directory,tools,args,mode,seed))
            (root/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'{mode}, seed={seed}: {report["results"][-1]["iterations"]} lượt', flush=True)
            if any(report['results'][-1][key] for key in BAD): print(root); return 1
    print(json.dumps(report,ensure_ascii=False,indent=2)); print(root)
    return 0


def save_metadata(root, source, spec, args, tools):
    names = ['stock_json_adapter.c','stock_json_fuzz.py','generate_simulator.py','stock_spec.json','stock_simulator.c','fuzz_runner.py']
    for name in names: shutil.copyfile(HERE/name,root/name)
    metadata = dict(backend=spec['backend_sha256'],source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    files={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in names},
                    tools=tools,budget=vars(args),scope='Fixture một sản phẩm, tối đa một biến thể; không HTTP/DB/PayOS.',
                    limits=dict(bytes=MAX_BYTES,records=MAX_RECORDS),sanitizer='Chưa chạy sanitizer; không kết luận không có leak.')
    (root/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations',type=int,default=500)
    parser.add_argument('--seconds',type=float,default=120)
    parser.add_argument('--seeds',type=int,nargs='+',default=[1,7,42])
    args = parser.parse_args()
    if args.iterations < 1 or args.seconds <= 0: parser.error('Ngân sách phải dương')
    try:
        return run(args)
    except (OSError,ValueError,RuntimeError) as error:
        print('CHƯA HOÀN TẤT: '+str(error),file=sys.stderr); return 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
