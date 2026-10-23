# Công dụng: Cầu nối Python dùng ctypes nạp DLL để gọi hàm C và hỗ trợ chạy cách ly; file sinh tự động, chú thích có thể bị thay khi wrap lại.
"""Python wrap (ctypes) cho mã C — SINH TỰ ĐỘNG bởi sec_lab_framework (core/c_wrapper.py).

Hàm được wrap: java_add, jsonHex, jsonExponent, jsonInteger, jsonField, stock_json, stock_json_case, stock_reserve_guard.
Dùng:
    import stock_json_seclab_wrap as w
    w.java_add(...)          # gọi TRỰC TIẾP (C crash => Python crash)
    w.call_isolated("java_add", ...)   # gọi trong TIẾN TRÌNH CON (an toàn khi C crash/treo)
Nếu chưa có thư viện `libstock_json_seclab_wrap.dll`, module tự biên dịch từ `stock_json_seclab_shim.c` + `sl_target.c` bằng `gcc`.
"""
import json, os, subprocess, sys, tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB_PATH = os.path.join(_HERE, 'libstock_json_seclab_wrap.dll')
_SHIM = os.path.join(_HERE, 'stock_json_seclab_shim.c')
_LANG = 'c'
SIGNATURES = {'java_add': {'params': [{'kind': 'int', 'ctype': 'c_int32', 'const': False},
                         {'kind': 'int', 'ctype': 'c_int32', 'const': False}],
              'ret': {'kind': 'int', 'ctype': 'c_int32', 'const': False},
              'names': ['a', 'b']},
 'jsonHex': {'params': [{'kind': 'int', 'ctype': 'c_int', 'const': False}],
             'ret': {'kind': 'int', 'ctype': 'c_int', 'const': False},
             'names': ['value']},
 'jsonExponent': {'params': [{'kind': 'str', 'ctype': 'c_char', 'const': True},
                             {'kind': 'int', 'ctype': 'c_size_t', 'const': False},
                             {'kind': 'array', 'ctype': 'c_size_t', 'const': False},
                             {'kind': 'array', 'ctype': 'c_int', 'const': False}],
                  'ret': {'kind': 'int', 'ctype': 'c_int', 'const': False},
                  'names': ['text', 'size', 'pos', 'exponent']},
 'jsonInteger': {'params': [{'kind': 'str', 'ctype': 'c_char', 'const': True},
                            {'kind': 'int', 'ctype': 'c_size_t', 'const': False},
                            {'kind': 'array', 'ctype': 'c_int32', 'const': False}],
                 'ret': {'kind': 'int', 'ctype': 'c_int', 'const': False},
                 'names': ['text', 'size', 'output']},
 'jsonField': {'params': [{'kind': 'str', 'ctype': 'c_char', 'const': True}],
               'ret': {'kind': 'int', 'ctype': 'c_int', 'const': False},
               'names': ['key']},
 'stock_json': {'params': [{'kind': 'str', 'ctype': 'c_char', 'const': True}],
                'ret': {'kind': 'int', 'ctype': 'c_int', 'const': False},
                'names': ['json']},
 'stock_json_case': {'params': [{'kind': 'int', 'ctype': 'c_int', 'const': False},
                                {'kind': 'int', 'ctype': 'c_int', 'const': False},
                                {'kind': 'int', 'ctype': 'c_int', 'const': False},
                                {'kind': 'int', 'ctype': 'c_int', 'const': False}],
                     'ret': {'kind': 'int', 'ctype': 'c_int', 'const': False},
                     'names': ['available', 'reserved', 'quantity', 'action']},
 'stock_reserve_guard': {'params': [{'kind': 'int', 'ctype': 'c_int', 'const': False},
                                    {'kind': 'int', 'ctype': 'c_int', 'const': False},
                                    {'kind': 'int', 'ctype': 'c_int', 'const': False},
                                    {'kind': 'int', 'ctype': 'c_int', 'const': False},
                                    {'kind': 'int', 'ctype': 'c_int', 'const': False},
                                    {'kind': 'int', 'ctype': 'c_int', 'const': False}],
                         'ret': {'kind': 'int', 'ctype': 'c_int', 'const': False},
                         'names': ['available',
                                   'reserved',
                                   'quantity',
                                   'variant',
                                   'variant_available',
                                   'variant_reserved']}}

# ---- runtime dùng chung (marshal đối số, worker cô lập) — cùng mã với framework ----
import ctypes, json, os, sys

_libc = None

def sl_alloc(data):
    """Cap phat bo dem bang malloc CUA C (dung kich thuoc, khong them dem) va chep `data` vao.
    Nho vay tran/doc ngoai bien cua ma C cham vao heap that (ASan dat redzone; heap hong -> crash that),
    thay vi bo dem do Python quan ly. Khong free: worker song ngan; callee co the tu free."""
    global _libc
    if _libc is None:
        _libc = ctypes.CDLL(None) if os.name != "nt" else ctypes.cdll.msvcrt
        _libc.malloc.restype = ctypes.c_void_p
        _libc.malloc.argtypes = [ctypes.c_size_t]
    p = _libc.malloc(max(len(data), 1))
    if data:
        ctypes.memmove(p, data, len(data))
    return p

def sl_marshal_arg(spec, v, keep):
    k = spec["kind"]
    if k == "int":
        return int(v)
    if k == "float":
        return float(v)
    if k == "bool":
        return bool(v)
    if k in ("str", "bytes"):
        if v is None:
            return None
        if isinstance(v, str):
            b = v.encode("utf-8", "surrogateescape")
        elif isinstance(v, (bytes, bytearray)):
            b = bytes(v)
        else:
            b = str(v).encode("utf-8", "surrogateescape")
        return sl_alloc(b + b"\0")
    if k == "array":
        if v is None:
            return None
        elem = getattr(ctypes, spec["ctype"])
        lst = list(v)
        arr = (elem * max(len(lst), 1))(*lst)
        return sl_alloc(bytes(arr)[: len(lst) * ctypes.sizeof(elem)])
    raise TypeError("kieu tham so khong ho tro: %r" % (k,))

def sl_argtype(spec):
    k = spec["kind"]
    if k in ("int", "float", "bool"):
        return getattr(ctypes, spec["ctype"])
    return ctypes.c_void_p

def sl_unmarshal_ret(spec, r):
    k = spec["kind"]
    if k == "void":
        return None
    if k == "str":
        return ctypes.string_at(r).decode("utf-8", "replace") if r else None
    if k == "ptr":
        return int(r) if r else 0
    return r

def sl_setup(lib, name, sig):
    fn = getattr(lib, "sl_wrap_" + name)
    fn.argtypes = [sl_argtype(p) for p in sig["params"]]
    rk = sig["ret"]["kind"]
    fn.restype = None if rk == "void" else (ctypes.c_void_p if rk in ("str", "ptr") else getattr(ctypes, sig["ret"]["ctype"]))
    return fn

def sl_worker_main(job_path):
    job = json.load(open(job_path, encoding="utf-8"))
    lib = ctypes.CDLL(job["lib"])
    fns = {}
    want_cov = bool(job.get("want_cov")) and hasattr(lib, "sl_cov_ptr")
    if want_cov:
        lib.sl_cov_ptr.restype = ctypes.c_void_p
        lib.sl_cov_reset.restype = None
        n_probes = int(job.get("n_probes", 0))
    out = open(job["out"], "a", encoding="utf-8")
    off = int(job.get("offset", 0))
    for j, call in enumerate(job["calls"]):
        name = call["f"]
        sig = job["sigs"][name]
        try:
            if name not in fns:
                fns[name] = sl_setup(lib, name, sig)
            keep = []
            cargs = [sl_marshal_arg(sp, v, keep) for sp, v in zip(sig["params"], call["args"])]
        except Exception as e:
            out.write(json.dumps({"i": off + j, "status": "error", "detail": "marshal: %r" % (e,)}) + "\n")
            out.flush()
            continue
        if want_cov:
            lib.sl_cov_reset()
        try:
            r = fns[name](*cargs)
            rec = {"i": off + j, "status": "ok", "ret": sl_unmarshal_ret(sig["ret"], r)}
        except Exception as e:
            rec = {"i": off + j, "status": "error", "detail": repr(e)}
        if want_cov:
            raw = ctypes.string_at(lib.sl_cov_ptr(), n_probes)
            rec["cov"] = [q for q, b in enumerate(raw) if b]
        out.write(json.dumps(rec) + "\n")
        out.flush()
    out.close()
    return 0


def build_library(force=False):
    """Biên dịch lại thư viện từ shim (cần gcc/clang, hoặc g++/clang++ cho C++)."""
    if os.path.exists(_LIB_PATH) and not force:
        return _LIB_PATH
    import shutil
    cands = (["g++", "c++", "clang++"] if _LANG == "cpp" else ["gcc", "cc", "clang"])
    cc = next((c for c in cands if shutil.which(c)), None)
    if cc is None:
        raise RuntimeError("Không tìm thấy trình biên dịch C/C++ để build thư viện wrap")
    cmd = [cc, "-shared", "-fPIC", "-O0", "-g"] + (["-std=c++17"] if _LANG == "cpp" else []) + \
          ["-I", _HERE, "-o", _LIB_PATH, _SHIM]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("Biên dịch thất bại:\n" + r.stderr)
    return _LIB_PATH


_lib = None
_fns = {}


def _fn(name):
    global _lib
    if _lib is None:
        build_library()
        _lib = ctypes.CDLL(_LIB_PATH)
    if name not in _fns:
        _fns[name] = sl_setup(_lib, name, SIGNATURES[name])
    return _fns[name]


def call_direct(name, *args):
    """Gọi TRỰC TIẾP trong tiến trình hiện tại (nếu mã C crash thì Python cũng crash)."""
    sig = SIGNATURES[name]
    keep = []
    cargs = [sl_marshal_arg(sp, v, keep) for sp, v in zip(sig["params"], args)]
    return sl_unmarshal_ret(sig["ret"], _fn(name)(*cargs))


def call_isolated(name, *args, timeout=5.0):
    """Gọi trong TIẾN TRÌNH CON: trả về dict {"status": ok|crash|timeout|error, "ret": ..., "signal": ...}."""
    build_library()
    tmp = tempfile.mkdtemp(prefix="sl_call_")
    try:
        job = {"lib": _LIB_PATH, "sigs": SIGNATURES, "offset": 0, "want_cov": False, "n_probes": 0,
               "out": os.path.join(tmp, "out.jsonl"), "calls": [{"f": name, "args": list(args)}]}
        jp = os.path.join(tmp, "job.json")
        with open(jp, "w", encoding="utf-8") as f:
            json.dump(job, f)
        open(job["out"], "w").close()
        try:
            p = subprocess.run([sys.executable, os.path.abspath(__file__), "--sl-worker", jp],
                               capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "ret": None, "signal": "TIMEOUT"}
        lines = [l for l in open(job["out"], encoding="utf-8").read().splitlines() if l.strip()]
        if lines:
            return json.loads(lines[-1])
        rc = p.returncode
        sig = ""
        if rc < 0:
            import signal as _s
            try:
                sig = _s.Signals(-rc).name
            except Exception:
                sig = "SIG%d" % -rc
        return {"status": "crash" if rc != 0 else "exit", "ret": None, "signal": sig,
                "returncode": rc, "stderr": p.stderr[-500:]}
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# ---- hàm Python wrap (mỗi hàm C một hàm Python cùng tên) ----
def java_add(a, b):
    """C: int32_t java_add(int32_t a, int32_t b)   (dòng 12)

    Tham số: a:int, b:int. Trả về: int [c_int32] 32-bit có dấu."""
    return call_direct('java_add', a, b)

def jsonHex(value):
    """C: int jsonHex(int value)   (dòng 72)

    Tham số: value:int. Trả về: int [c_int] 32-bit có dấu."""
    return call_direct('jsonHex', value)

def jsonExponent(text, size, pos, exponent):
    """C: int jsonExponent(const char * text, size_t size, size_t * pos, int * exponent)   (dòng 126)

    Tham số: text:str, độ dài = size, size:int, là độ dài của text, pos:array, exponent:array. Trả về: int [c_int] 32-bit có dấu."""
    return call_direct('jsonExponent', text, size, pos, exponent)

def jsonInteger(text, size, output):
    """C: int jsonInteger(const char * text, size_t size, int32_t * output)   (dòng 140)

    Tham số: text:str, độ dài = size, size:int, là độ dài của text, output:array. Trả về: int [c_int] 32-bit có dấu."""
    return call_direct('jsonInteger', text, size, output)

def jsonField(key):
    """C: int jsonField(const char * key)   (dòng 191)

    Tham số: key:str. Trả về: int [c_int] 32-bit có dấu."""
    return call_direct('jsonField', key)

def stock_json(json):
    """C: int stock_json(const char * json)   (dòng 271)

    Tham số: json:str. Trả về: int [c_int] 32-bit có dấu."""
    return call_direct('stock_json', json)

def stock_json_case(available, reserved, quantity, action):
    """C: int stock_json_case(int available, int reserved, int quantity, int action)   (dòng 279)

    Tham số: available:int, reserved:int, quantity:int, action:int. Trả về: int [c_int] 32-bit có dấu."""
    return call_direct('stock_json_case', available, reserved, quantity, action)

def stock_reserve_guard(available, reserved, quantity, variant, variant_available, variant_reserved):
    """C: int stock_reserve_guard(int available, int reserved, int quantity, int variant, int variant_available, int variant_reserved)   (dòng 290)

    Tham số: available:int, reserved:int, quantity:int, variant:int, variant_available:int, variant_reserved:int. Trả về: int [c_int] 32-bit có dấu."""
    return call_direct('stock_reserve_guard', available, reserved, quantity, variant, variant_available, variant_reserved)

if __name__ == '__main__' and len(sys.argv) > 2 and sys.argv[1] == '--sl-worker':
    sys.exit(sl_worker_main(sys.argv[2]))
