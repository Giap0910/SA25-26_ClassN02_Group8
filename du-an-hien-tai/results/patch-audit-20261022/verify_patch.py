"""Lưu bằng chứng trước/sau cho giới hạn đầu vào helper; không chạy fuzz."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
COMPILER = ROOT / 'toolchain/llvm-mingw-20261006-ucrt-x86_64/bin/x86_64-w64-mingw32-clang.exe'
HARNESS = r'''
#include "SOURCE_FILE"
#include <assert.h>

static int checkValid(void) {
    const char *texts[] = {"0", "-1", "2147483647", "-2147483648", "2.0", "20e-1"};
    int32_t expected[] = {0, -1, INT32_MAX, INT32_MIN, 2, 2};
    for (size_t i = 0; i < 6; ++i) {
        int32_t value = 77;
        assert(jsonInteger(texts[i], strlen(texts[i]), &value) == 1);
        assert(value == expected[i]);
    }
    char zeros[65];
    memset(zeros, '0', 64); zeros[63] = '1'; zeros[64] = 0;
    int32_t value = 77;
    assert(jsonInteger(zeros, 64, &value) == 1 && value == 1);
    assert(jsonInteger("2147483648", 10, &value) == 0);
    assert(jsonInteger("1.5", 3, &value) == 0);
    return 0;
}

static int checkBounds(void) {
    int32_t value = 77;
    assert(jsonInteger(NULL, 1, &value) == 0);
    assert(jsonInteger("", 0, &value) == 0);
    assert(jsonInteger("1", 1, NULL) == 0);
    assert(jsonInteger("1", 65, &value) == 0);
    assert(value == 77);
    return 0;
}

static int checkPublic(void) {
    char text[512], number[66];
    memset(number, '1', 65); number[65] = 0;
    snprintf(text, sizeof(text), "{\"available\":10,\"reserved\":0,"
        "\"variant_available\":10,\"variant_reserved\":0,\"action\":0,"
        "\"items\":[{\"quantity\":%s}]}", number);
    assert(stock_json(text) == 100);
    assert(stock_json_case(10, 0, 2, 0) == 0);
    assert(stock_json_case(0, 0, 1, 0) == 2);
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 2) return 64;
    if (strcmp(argv[1], "valid") == 0) return checkValid();
    if (strcmp(argv[1], "bounds") == 0) return checkBounds();
    if (strcmp(argv[1], "public") == 0) return checkPublic();
    char text[66]; memset(text, '1', 65); text[65] = 0;
    int32_t value = 77;
    int result = jsonInteger(text, 65, &value);
    printf("result=%d output=%" PRId32 "\n", result, value);
    return result == 0 && value == 77 ? 0 : 1;
}
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, environment):
    process = subprocess.run(command, capture_output=True, timeout=45, env=environment)
    return {'command': command, 'returncode': process.returncode,
            'stdout': process.stdout.decode('utf-8', errors='replace'),
            'stderr': process.stderr.decode('utf-8', errors='replace')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['before', 'after'])
    args = parser.parse_args()
    source = HERE / f'{args.phase}-stock_json_seclab.c'
    if source.exists():
        raise SystemExit('Snapshot đã tồn tại; không ghi đè bằng chứng.')
    source.write_bytes((ROOT / 'stock_json_seclab.c').read_bytes())
    harness = HERE / f'{args.phase}-probe.c'
    harness.write_text(HARNESS.replace('SOURCE_FILE', source.name), encoding='utf-8')
    binary = HERE / f'{args.phase}-probe.exe'
    env = dict(os.environ, PATH=str(COMPILER.parent) + os.pathsep + os.environ.get('PATH', ''))
    command = [str(COMPILER), '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-unused-function', '-fsanitize=address,undefined',
               '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(harness), '-o', str(binary)]
    build = execute(command, env)
    if build['returncode'] != 0:
        raise RuntimeError(build)
    cases = ['overflow', 'valid', 'public'] + (['bounds'] if args.phase == 'after' else [])
    runs = {name: execute([str(binary), name], env) for name in cases}
    report = {'phase': args.phase, 'source_sha256': digest(source),
              'compiler': execute([str(COMPILER), '--version'], env), 'build': build, 'runs': runs,
              'scope': 'Ca cố định gọi helper trực tiếp và kiểm tra JSON công khai; không fuzz, không GUI, không LSan.'}
    (HERE / f'{args.phase}-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for name, result in runs.items():
        (HERE / f'{args.phase}-{name}.log').write_text(result['stdout'] + result['stderr'], encoding='utf-8')
        print(args.phase, name, result['returncode'])
    if args.phase == 'before':
        assert runs['overflow']['returncode'] != 0
        diagnostic = runs['overflow']['stderr']
        assert 'stack-buffer-overflow' in diagnostic or 'index 64 out of bounds' in diagnostic
    else:
        assert all(result['returncode'] == 0 for result in runs.values())
    assert all(runs[name]['returncode'] == 0 for name in ['valid', 'public'])


if __name__ == '__main__':
    main()
