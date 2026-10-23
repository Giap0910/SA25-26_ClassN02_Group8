from pathlib import Path
import ctypes, hashlib, json, os, random, re, subprocess, time
import z3
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
compiler=ROOT/'toolchain/llvm-mingw-20261006-ucrt-x86_64/bin/x86_64-w64-mingw32-clang.exe'
source=(ROOT/'stock_json_seclab.c').read_bytes()
(HERE/'target.c').write_bytes(source)
cmd=[str(compiler),'-std=c11','-O1','-Wall','-Wextra','-Werror','-shared',str(HERE/'target.c'),'-o',str(HERE/'target.dll')]
build=subprocess.run(cmd,capture_output=True)
(HERE/'build.log').write_bytes(build.stdout+build.stderr)
assert build.returncode==0,build.stderr
os.environ['PATH']=str(compiler.parent)+os.pathsep+os.environ['PATH']
lib=ctypes.CDLL(str(HERE/'target.dll'))
target=lib.stock_magic_json;target.argtypes=[ctypes.c_char_p];target.restype=ctypes.c_int
payload=b'{"available":10,"reserved":0,"variant_available":10,"variant_reserved":0,"action":0,"items":[{"quantity":2}]}'
(HERE/'payload.json').write_bytes(payload)
report={'method':'Black-box uniform four bytes; white-box basic SMT from explicit C magic equality, based on ch4_dynafuzz/06_white_box_fuzzing.py. Not automatic concolic or GUI.', 'target':'stock_magic_json returns 0 with fixed JSON', 'budget_per_seed':200000,'source_sha256':hashlib.sha256(source).hexdigest(),'build_command':cmd,'z3_version':z3.get_version_string(),'runs':[]}
# Only the white-box stage reads the source condition.
for seed in [1,7,42,101,2026]:
 rng=random.Random(seed);found=None;counts={};start=time.perf_counter()
 for attempt in range(1,200001):
  candidate=rng.getrandbits(32).to_bytes(4,'little')+payload
  code=target(candidate);counts[str(code)]=counts.get(str(code),0)+1
  if code==0:found=candidate;break
 elapsed=time.perf_counter()-start
 row={'seed':seed,'mode':'black-box','executions':attempt,'seconds':elapsed,'found':found is not None,'return_counts':counts}
 if found:
  name=f'black-{seed}.bin';(HERE/name).write_bytes(found);row['input']=name;row['replay_code']=target(found)
 report['runs'].append(row);print(row,flush=True)
for seed in [1,7,42,101,2026]:
 start=time.perf_counter()
 body=source.decode().split('int stock_magic_json(',1)[1].split('int stock_json_case(',1)[0]
 magic=re.search(r'const char magic\[\] = "([A-Za-z0-9]+)";',body).group(1).encode()
 assert len(magic)==4
 variables=[z3.BitVec(f'b{i}',8) for i in range(4)]
 solver=z3.Solver();solver.set(random_seed=seed,timeout=10000)
 solver.add(*[v==value for v,value in zip(variables,magic)])
 solve_start=time.perf_counter();status=solver.check();solve_seconds=time.perf_counter()-solve_start
 assert status==z3.sat
 model=solver.model();prefix=bytes(model.eval(v).as_long() for v in variables)
 candidate=prefix+payload;code=target(candidate)
 elapsed=time.perf_counter()-start;assert code==0
 name=f'white-{seed}.bin';(HERE/name).write_bytes(candidate)
 row={'seed':seed,'mode':'white-box SMT','solver_queries':1,'executions':1,'seconds':elapsed,'solver_seconds':solve_seconds,'found':True,'input':name,'magic_hex':prefix.hex(),'return_code':code,'replay_code':target(candidate)}
 report['runs'].append(row);print(row,flush=True)
report['notes']=['Timers exclude build and library loading; white-box total includes condition extraction, solving, constructing input and C execution.','Black-box samples 0..255 per byte. Embedded NUL terminates the C string and is rejected.','No speedup ratio: black-box failures are censored by the budget.','Fixed payload isolates magic reachability; this does not measure whole-parser coverage.']
(HERE/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
