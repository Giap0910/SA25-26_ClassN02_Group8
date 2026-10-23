from pathlib import Path
import subprocess,os,json,hashlib,time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
COMPILER=ROOT/'toolchain/llvm-mingw-20261006-ucrt-x86_64/bin/x86_64-w64-mingw32-clang.exe'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def execute(cmd, log, seconds=60):
    begin=time.monotonic()
    proc=subprocess.run([str(x) for x in cmd],capture_output=True,env=ENV,timeout=seconds,cwd=HERE)
    text=(proc.stdout+proc.stderr).decode('utf-8',errors='replace')
    (HERE/log).write_text(text,encoding='utf-8')
    return {'command':[str(x) for x in cmd],'returncode':proc.returncode,'seconds':time.monotonic()-begin,'log':log,'sanitizer_finding':('runtime error:' in text or 'ERROR: AddressSanitizer' in text)}
ENV=dict(os.environ)
ENV['PATH']=str(COMPILER.parent)+os.pathsep+ENV.get('PATH','')
ENV['ASAN_OPTIONS']='detect_leaks=0:symbolize=1'
protected=['stock_json_adapter.c','stock_json_seclab.c','stock_spec.json','Baocao.docx','Baocao.pdf','badminton_spec.xlsx']
report={'scope':'Fuzz có định hướng helper jsonInteger trên lỗi đã biết; không phải khám phá lỗi mới hoặc kiểm thử website. Chỉ nhận token số nguyên không dấu đúng cú pháp, buffer hợp lệ. Không cung cấp input gây lỗi sẵn.','hashes_before':{p:digest(ROOT/p) for p in protected},'builds':{},'runs':[]}
for phase in ['before','after']:
    report['builds'][phase]=execute([COMPILER,'-std=c11','-O1','-g','-Wno-unused-function','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',HERE/f'{phase}-fuzz.c','-o',HERE/f'{phase}-fuzz.exe'],f'{phase}-build.log')
    if report['builds'][phase]['returncode']: raise RuntimeError(report['builds'][phase])

import random
for seed in [1,7,42]:
    rng=random.Random(seed)
    corpus=[b'0',b'1',b'12',b'123']
    trace=[]; finding=None
    folder=HERE/f'seed-{seed}';folder.mkdir()
    (folder/'initial-corpus.json').write_text(json.dumps([x.decode() for x in corpus]),encoding='utf-8')
    started=time.monotonic()
    for iteration in range(1,501):
        base=rng.choice(corpus)
        op=rng.choice(['insert','duplicate','replace','delete'])
        pos=rng.randrange(len(base)+1)
        if op=='insert': candidate=base[:pos]+bytes(rng.randrange(48,58) for _ in range(rng.randint(1,16)))+base[pos:]
        elif op=='duplicate': candidate=base[:pos]+base+base[pos:]
        elif op=='delete': candidate=base[:pos]+base[min(pos+1,len(base)):]
        else: candidate=base[:pos]+bytes([rng.randrange(48,58)])+base[min(pos+1,len(base)):]
        if not candidate or len(candidate)>256 or (len(candidate)>1 and candidate[0]==48): continue
        path=folder/'candidate.bin';path.write_bytes(candidate)
        result=execute([HERE/'before-fuzz.exe',path],f'seed-{seed}/latest.log',10)
        trace.append({'iteration':iteration,'operation':op,'parent_hex':base.hex(),'input_hex':candidate.hex(),'bytes':len(candidate),'returncode':result['returncode'],'finding':result['sanitizer_finding']})
        if result['sanitizer_finding']:
            crash=folder/'finding.bin';crash.write_bytes(candidate)
            (folder/'finding.log').write_bytes((folder/'latest.log').read_bytes())
            finding={'bytes':len(candidate),'iteration':iteration,'executions':len(trace),'input':str(crash.relative_to(HERE)),'sha256':digest(crash)}
            finding['before_replay']=execute([HERE/'before-fuzz.exe',crash],f'seed-{seed}/before-replay.log')
            finding['after_replay']=execute([HERE/'after-fuzz.exe',crash],f'seed-{seed}/after-replay.log')
            break
        if result['returncode']!=0: raise RuntimeError(result)
        if len(candidate) not in {len(x) for x in corpus}: corpus.append(candidate)
        if time.monotonic()-started>45:break
    (folder/'trace.json').write_text(json.dumps(trace,indent=2),encoding='utf-8')
    report['runs'].append({'seed':seed,'executions':len(trace),'seconds':time.monotonic()-started,'finding':finding})
    (HERE/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('seed',seed,'executions',len(trace),'finding',finding,flush=True)
report['method']='Python structure-aware mutation: insert/delete/replace/duplicate digits; retain novel lengths, not coverage feedback. Initial corpus 0,1,12,123; max 256 bytes; budget 500 mutation attempts or 45 seconds per seed.'
report['hashes_after']={p:digest(ROOT/p) for p in protected}
report['protected_unchanged']=report['hashes_before']==report['hashes_after']
report['source_hashes']={phase:digest(ROOT/f'results/patch-audit-20261022/{phase}-stock_json_seclab.c') for phase in ['before','after']}
report['compiler']=execute([COMPILER,'--version'],'compiler.log')
(HERE/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
