"""Fuzz JSON trên C tồn kho sinh từ đặc tả; không gọi HTTP/database."""
import argparse
import copy
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
BAD = ('crash', 'timeout', 'invariant_failure', 'oracle_mismatch', 'sanitizer_failure')


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
    if any(marker in log for marker in ('ERROR: AddressSanitizer','runtime error:', 'UndefinedBehaviorSanitizer:')):
        return 'sanitizer_failure', {}, log
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
    if function(None) != 101: raise RuntimeError('NULL không được từ chối')
    count = 0
    for name, data, expected in golden_cases():
        if b'\0' in data: continue
        if function(data) != expected: raise RuntimeError('Hàm wrap lệch oracle: ' + name)
        count += 1
    return count


def toolchain():
    portable = legacy.ROOT/'toolchain/mingw64/bin'
    tools = {name: str(portable/(name+'.exe')) if (portable/(name+'.exe')).exists() else shutil.which(name)
             for name in ('gcc', 'gcov')}
    if not all(tools.values()): raise RuntimeError('Thiếu GCC/gcov')
    os.environ['PATH'] = str(Path(tools['gcc']).parent)+os.pathsep+os.environ.get('PATH','')
    return tools


def open_lab(application=None):
    portable = legacy.ROOT/'toolchain/mingw64/bin'
    compiler = str(portable/'gcc.exe') if (portable/'gcc.exe').exists() else shutil.which('gcc')
    if not compiler: raise RuntimeError('Không tìm thấy GCC portable hoặc GCC trên PATH')
    application = Path(application) if application else Path.home()/'Downloads/SecLabFramework.exe'
    if not application.exists(): raise RuntimeError('Không tìm thấy ứng dụng thầy; dùng --lab-exe để chọn đường dẫn')
    environment = dict(os.environ, PATH=str(Path(compiler).parent)+os.pathsep+os.environ.get('PATH',''))
    process = subprocess.Popen([str(application)],cwd=legacy.ROOT,env=environment,
                               creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    print(f'Đã yêu cầu mở ứng dụng với GCC trong PATH tiến trình, PID {process.pid}.')
    print('Cần kiểm tra giao diện xác nhận compiler và nạp stock_json_seclab.c; chưa tự chạy fuzz trong GUI.')
    return 0


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
                    limits=dict(bytes=MAX_BYTES,records=MAX_RECORDS),sanitizer=(
                        'Yêu cầu ASan+UBSan; xem compile log và summary để xác nhận. Không chạy LeakSanitizer.'
                        if getattr(args,'sanitizer',False) else 'Chưa chạy sanitizer; không kết luận không có leak.'))
    metadata['reference_mode'] = 'Bản nguồn Java đóng băng trong reference_backend; không đọc hoặc kiểm tra web đang chạy.'
    (root/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')


def sanitizer_compiler():
    directory = HERE/'toolchain/llvm-mingw-20261006-ucrt-x86_64/bin'
    compiler = directory/'x86_64-w64-mingw32-clang.exe'
    if not compiler.is_file(): raise RuntimeError('Chưa có LLVM-MinGW portable hỗ trợ sanitizer')
    os.environ['PATH'] = str(directory)+os.pathsep+os.environ.get('PATH','')
    os.environ['ASAN_OPTIONS'] = 'detect_leaks=0:halt_on_error=1'
    os.environ['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
    return str(compiler)


def compile_sanitized(source, directory, compiler):
    binary = directory/'stock_json_sanitized.exe'
    command = [compiler,'-std=c11','-Wall','-Wextra','-Werror','-O1','-g',
               '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
               str(source),'-o',str(binary)]
    process = subprocess.run(command,capture_output=True,text=True,timeout=60)
    (directory/'sanitizer-compile.log').write_text(process.stdout+process.stderr,encoding='utf-8')
    if process.returncode: raise RuntimeError(process.stderr)
    return binary, command


def sanitizer_campaign(binary, directory, args, seed):
    directory.mkdir()
    rng, start = random.Random(seed), time.perf_counter()
    corpus = [data for _,data,_ in golden_cases() if len(data)<4096]
    counts, codes, used = dict.fromkeys(BAD,0), {}, 0
    with (directory/'events.csv').open('w',newline='',encoding='utf-8') as stream:
        writer = csv.writer(stream); writer.writerow(['iteration','outcome','code'])
        for index in range(1,args.iterations+1):
            if time.perf_counter()-start >= args.seconds: break
            outcome, actual, log = execute(binary,candidate(rng,corpus,'mutation'),directory,index)
            used = index; code = str(actual.get('code')); codes[code] = codes.get(code,0)+1
            writer.writerow([index,outcome,actual.get('code')])
            if outcome != 'ok':
                counts[outcome] += 1
                (directory/'failure.txt').write_text(log,encoding='utf-8'); break
    return dict(mode='sanitizer-seeded-mutation',seed=seed,iterations=used,
                seconds=time.perf_counter()-start,codes=codes,**counts)


def run_sanitizer(args):
    spec, compiler = generator.load_spec(), sanitizer_compiler()
    root = legacy.OUTPUT/('sanitizer-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
    root.mkdir(parents=True)
    source = root/'stock_json_target.c'; source.write_text(generator.generate_json(spec),encoding='utf-8')
    save_metadata(root,source,spec,args,dict(clang=compiler))
    binary, command = compile_sanitized(source,root,compiler)
    regression = root/'regression'; regression.mkdir()
    report = dict(regressions=regressions(binary,regression),results=[],command=command,
                  sanitizer='ASan+UBSan',leak_sanitizer=False,coverage_measured=False)
    for seed in args.seeds:
        report['results'].append(sanitizer_campaign(binary,root/f'mutation-{seed}',args,seed))
        (root/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Sanitizer, seed={seed}: {report["results"][-1]["iterations"]} lượt',flush=True)
        if any(report['results'][-1][key] for key in BAD): print(root); return 1
    print(json.dumps(report,ensure_ascii=False,indent=2)); print(root)
    return 0


def spec_tables():
    tables = copy.deepcopy(generator.load_spec()['teacher_tables'])
    tables['ThongTin'] = [tables['ThongTin'][0], ['name','badminton_stock_json'],
        ['description','Một sản phẩm, tối đa một biến thể. JSON fixture → kiểm tra kiểu/kích thước/record → nghiệp vụ C sinh từ đặc tả → fuzz → test case.'],
        ['source','OrderService.validateRequestedItems/validateProductForOrder/settleReservedStock; ProductVariantService.reserve/settle; OrderItemRequest.readQuantity.'],
        ['input',encode(fixture()).decode()], ['fields','available, reserved, variant_available, variant_reserved: int32. action: 0–15. items: mảng record chỉ có quantity.'],
        ['limits','Tối đa 16.384 byte UTF-8, 64 byte/token số, 1–100 record. quantity mỗi dòng 1–100, tổng không quá 100. Giới hạn byte/token là của simulator, không phải giới hạn HTTP đã xác nhận.'],
        ['memory','calloc đúng 100 phần tử int32_t; kiểm tra NULL, không ghi quá 100 phần tử, free trên mọi đường thoát sau cấp phát. Không thêm lỗi cố ý.'],
        ['ch4','Nạp mã C đầy đủ được sinh riêng vào Ch4: Sinh test + CWE hoặc Chiến dịch fuzz. Excel Ch6 không tự nhập kết quả chiến dịch C.'],
        ['scope','Fixture không phải JSON tạo đơn thực tế. Một sản phẩm/biến thể đã chọn, không khóa DB, HTTP, PayOS hoặc đồng thời. Khóa lạ/trùng bị từ chối theo hợp đồng adapter.'],
        ['action','Bit 8: có biến thể; 2 bit thấp 0 giữ, 1 hoàn, 2/3 tất toán; bit 4 lặp thao tác hoàn/tất toán. Đây là mã fixture, không phải trạng thái HTTP.'],
        ['errors','0 thành công; 1–7 nghiệp vụ; 100 sai JSON/schema/kiểu/int32; 101 quá dài/NULL; 102 số record; 103 số lượng; 104 fixture; 105 cấp phát; 106 bất biến.'],
        ['static_scope','HamSinhMa của Ch6 vẫn là phép cộng minh họa. Muốn phân tích toàn bộ parser/luồng bộ nhớ phải nạp C đầy đủ vào Ch2/Ch3. Không coi CWE từ phép cộng trần là lỗi backend.']]
    tables['YeuCauChucNang'] += [[key,text,'safety','HIGH'] for key,text in json_requirements()]
    tables['RangBuoc'] = [tables['RangBuoc'][0]] + [[f'CON-{i+1}',text,'HIGH'] for i,text in enumerate(json_constraints())]
    tables['ThuocTinhAnToan'] = [tables['ThuocTinhAnToan'][0],['EF(reserved)'],['EF(cancelled)'],['EF(settled)'],['AG(!(cancelled & settled))']]
    tables['KiemTraSoHoc'] = [tables['KiemTraSoHoc'][0],['guarded_reserved_sum','r, q','r >= 0 and q >= 1 and q <= 100 and r <= 2147483647 - q and r + q > 2147483647',None]]
    tables['TestCase'] += [excel_case(index,name,data,code) for index,(name,data,code) in enumerate(golden_cases(),1)]
    tables['TestCase'] += [['TC-J42','REQ-J5','Cấp phát thất bại','Bản C thử thay kết quả calloc bằng NULL',
        'Biên dịch bản thử\nGọi stock_json với fixture hợp lệ','Trả 105, không dereference NULL','HIGH'],
        ['TC-J43','REQ-J5','Cân bằng cấp phát/giải phóng','Bản thử đếm khối cấp phát còn sống',
        'Gọi các ca hợp lệ và lỗi JSON qua thư viện C\nĐọc bộ đếm sau mỗi ca','Không còn khối sống sau từng ca. Không thay thế ASan/LSan.','HIGH']]
    return tables


def json_requirements():
    return [('REQ-J1','Đọc JSON fixture theo schema, từ chối thiếu/thừa/trùng trường và sai kiểu.'),
        ('REQ-J2','Chặn độ dài đầu vào, token số và số record trước khi ghi quá vùng nhớ.'),
        ('REQ-J3','Số lượng nguyên chính xác, mỗi dòng và tổng của cùng sản phẩm từ 1 đến 100.'),
        ('REQ-J4','Trạng thái kho hợp lệ; giữ/hoàn/tất toán đúng quy tắc đã truy vết backend.'),
        ('REQ-J5','Kiểm tra cấp phát thất bại, chỉ đọc/ghi trong giới hạn và giải phóng vùng nhớ đã cấp phát.'),
        ('REQ-J6','Lưu đầu vào và đối chiếu kết quả C với oracle; đo coverage để hướng dẫn mutation.')]


def json_constraints():
    return ['Giữ nguyên 6 yêu cầu nghiệp vụ tồn kho. JSON chỉ là adapter kiểm thử, không thay endpoint hoặc DTO web.',
        'Tất cả record thuộc một sản phẩm/biến thể. Không mô phỏng đơn nhiều sản phẩm, canonical JSON hoặc database transaction.',
        'calloc 100 * sizeof(int32_t), free đúng một lần sau cấp phát thành công; parser không đệ quy.',
        '16.384 byte và token số 64 byte là giới hạn thử nghiệm riêng. Chấp nhận 2.0 và 20e-1, từ chối phần lẻ hoặc ngoài int32.',
        'Gọi hàm stock_json(const char *json) qua wrapper chuỗi C có NUL cuối. NUL nhúng chỉ kiểm tra bằng CLI đọc file có độ dài, không coi ctypes.c_char_p giữ được phần sau NUL.',
        'Đồ thị Kripke là trừu tượng nghiệp vụ, không chứng minh toàn bộ parser, bộ nhớ hoặc khóa đồng thời.',
        'CWE phải có bằng chứng và phạm vi mã. Không gán CVE cho website từ CVE minh họa. Không kết luận không leak khi chưa có phép đo phù hợp.']


def excel_case(index, name, data, code):
    requirement = {101:'REQ-J2',102:'REQ-J2',103:'REQ-J3',104:'REQ-J4'}.get(code,'REQ-J1')
    if code == 0: requirement = 'REQ-J4, REQ-J6'
    if len(data) > 500: content = 'Fixture chuẩn và biến đổi theo golden_cases(): ' + name + f'. Độ dài {len(data)} byte.'
    else: content = data.decode('utf-8',errors='backslashreplace').replace('\0','\\u0000')
    return [f'TC-J{index:02}',requirement,'JSON tồn kho: '+name,content,
        'Sinh C từ stock_spec.json\nChạy input qua C và oracle độc lập\nLưu input và actual trong regression.json',
        json.dumps(oracle(data),ensure_ascii=False),'HIGH']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iterations',type=int,default=500)
    parser.add_argument('--seconds',type=float,default=120)
    parser.add_argument('--seeds',type=int,nargs='+',default=[1,7,42])
    parser.add_argument('--print-spec',action='store_true',help='Xuất dữ liệu 10 sheet Excel tồn kho JSON')
    parser.add_argument('--open-lab',action='store_true',help='Mở ứng dụng thầy với PATH riêng có GCC portable')
    parser.add_argument('--lab-exe',help='Đường dẫn SecLabFramework.exe nếu không nằm trong Downloads')
    parser.add_argument('--sanitizer',action='store_true',help='Chạy riêng ASan+UBSan bằng LLVM-MinGW portable; không đo gcov')
    args = parser.parse_args()
    if args.print_spec:
        print(json.dumps(spec_tables(),ensure_ascii=False)); return 0
    if args.iterations < 1 or args.seconds <= 0: parser.error('Ngân sách phải dương')
    try:
        if args.open_lab: return open_lab(args.lab_exe)
        if args.sanitizer: return run_sanitizer(args)
        return run(args)
    except (OSError,ValueError,RuntimeError) as error:
        print('CHƯA HOÀN TẤT: '+str(error),file=sys.stderr); return 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
