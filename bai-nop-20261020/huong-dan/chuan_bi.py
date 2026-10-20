"""Ghép bản sao chạy thử từ các nhóm file, không thay đổi nguồn nộp."""
from pathlib import Path
import shutil

BASE = Path(__file__).resolve().parents[1]
WORK = BASE / '.work'


def copy_checked(source, target):
    if target.exists() and source.read_bytes() != target.read_bytes():
        raise SystemExit(f'File làm việc đã đổi, không ghi đè: {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def prepare():
    for group in ('ma-nguon', 'kiem-thu', 'dac-ta'):
        for source in (BASE / group).iterdir():
            if source.is_file():
                copy_checked(source, WORK / source.name)
    for source in (BASE / 'tham-chieu').glob('*.java'):
        copy_checked(source, WORK / 'reference_backend' / source.name)
    print(f'Đã chuẩn bị bản sao chạy thử: {WORK}')
    print('Nguồn nộp không đổi; kết quả chạy mới nằm trong .work/results/.')


if __name__ == '__main__':
    prepare()
