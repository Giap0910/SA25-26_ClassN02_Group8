# Bộ bài An toàn phần mềm - cập nhật 20/10/2026

Mô hình tồn kho một sản phẩm, tối đa một biến thể: JSON → kiểm tra kiểu, size,
record/cấp phát → nghiệp vụ C sinh từ đặc tả → fuzz/oracle → test case.
Không gọi website, MySQL, PayOS; không thay toàn bộ backend bằng mô hình này.
Ch5–Ch6 tạm gác; thông tin nhóm/phân công để trống theo yêu cầu.

## Tổ chức file

| Thư mục | Vai trò |
|---|---|
| `tai-lieu/` | PDF chính 25 trang, ảnh thật trang 14–21; ghi chú dự án gốc |
| `dac-ta/` | JSON đặc tả, mô hình Kripke Ch1, Excel 10 sheet/12 yêu cầu/55 ca |
| `ma-nguon/` | Bộ sinh Python, adapter C, C nghiệp vụ và C đầy đủ nạp GUI |
| `kiem-thu/` | Runner/oracle, so sánh SMT, test và wrapper GUI |
| `bang-chung/` | Bằng chứng chọn lọc giữ nguyên nội dung, tên thư mục lượt chạy |
| `tham-chieu/` | Ba file Java đóng băng để kiểm tra fingerprint |
| `huong-dan/` | Chuẩn bị bản sao chạy và hướng dẫn trình diễn gốc |

Các file nguồn được sao chép nguyên byte từ dự án độc lập. Không sửa nghiệp vụ để
đổi cấu trúc thư mục. `chuan_bi.py` ghép bản sao vào `.work/` (Git bỏ qua), vì script
gốc cần spec, adapter, test và reference_backend ở cùng gốc làm việc.

## Chạy lại trên Windows

Yêu cầu Python 3.12+, GCC/gcov cùng phiên bản; Clang có ASan/UBSan nếu chạy sanitizer.
Không đóng gói compiler, DLL hay môi trường ảo. Để chạy đầy đủ test gốc (có kiểm tra
launcher portable), cần đặt/link bộ compiler của máy người chạy tại
`.work/toolchain/mingw64/bin/gcc.exe` và `gcov.exe`. Riêng sanitizer cần đúng
`.work/toolchain/llvm-mingw-20261006-ucrt-x86_64/bin/x86_64-w64-mingw32-clang.exe`.
Chỉ thêm Clang lên PATH chưa đủ vì runner gốc dùng vị trí portable cố định.

Từ thư mục `bai-nop-20261020`:

```powershell
python -X utf8 -B huong-dan/chuan_bi.py
# Chuẩn bị compiler theo đường dẫn portable nêu trên trước khi chạy test.
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install pytest==9.1.1 z3-solver==5.3.1.0
Set-Location .work
& ..\.venv\Scripts\python.exe -X utf8 -B -m pytest -p no:cacheprovider test_generator.py test_stock_json_seclab_stock_reserve_guard_fuzz.py -q
& ..\.venv\Scripts\python.exe -X utf8 -B stock_json_fuzz.py --iterations 50 --seeds 1 --seconds 30
& ..\.venv\Scripts\python.exe -X utf8 -B compare_fuzz.py
```

Không cần quyền quản trị hay sửa PATH hệ thống. Có thể thêm thư mục compiler
vào `$env:PATH` của PowerShell hiện tại trước khi chạy. Không đồng nhất lượt thử
ngắn ở trên với các chiến dịch lịch sử trong báo cáo. Lệnh tạo kết quả mới trong
`.work/results/`; không ghi đè bằng chứng đã nộp.

Muốn kiểm tra ASan/UBSan, đặt compiler Clang hỗ trợ vào đường dẫn portable nêu trên rồi
chạy `stock_json_fuzz.py --sanitizer --iterations 100 --seeds 1 --seconds 60`.
LSan chưa chạy trên môi trường Windows gốc; Dr. Memory được ghi riêng, không đổi tên công cụ.

Nếu máy đã có thư mục `toolchain` đầy đủ, có thể dùng junction thay vì sao chép:
`New-Item -ItemType Junction -Path .work/toolchain -Target 'D:\duong-dan-cua-ban\toolchain'`.
Chỉ chạy khi `.work/toolchain` chưa tồn tại, không cần sửa PATH hệ thống.
Wrapper cần thư mục TEMP có quyền ghi; nếu TEMP bị hạn chế, đặt `$env:TEMP` và
`$env:TMP` đến một thư mục tạm riêng do người chạy sở hữu trong `.work/`.
Các test lỗi mẫu sanitizer là đối chứng công cụ, không phải lỗi sản phẩm.

### Thao tác ứng dụng của thầy

- Ch1: nạp `dac-ta/stock_kripke.json`, kiểm tra bốn công thức trong báo cáo 6.5.
- Ch2: nạp `ma-nguon/stock_json_seclab.c`, quét bộ nhớ; đối chiếu giới hạn GUI ở báo cáo 6.6.
- Ch3: cùng mã C, chọn `stock_reserve_guard` khi vẽ CFG/sinh test; SAT/UNSAT theo mục 6.8.
- Ch4: chọn `stock_json` cho chuỗi JSON hoặc `stock_reserve_guard` cho guard thuần số.
- Gói GUI đã xuất ở `kiem-thu/`; sau chuẩn bị, wrapper tự biên dịch DLL trong `.work/`.

`huong-dan/run-goc.md` giữ nguyên hướng dẫn của máy gốc; đường dẫn `C:\Project\...`
trong đó phải thay bằng vị trí `.work` trên máy người chạy. Ứng dụng SecLabFramework
không được đóng gói trong repository và cần cài riêng nếu trình diễn GUI.

## Số liệu và giới hạn

- Ch1: 5 trạng thái, 4 CTL đúng trong mô hình vòng đời trừu tượng.
- Ch3 GUI: 60 input, giữ 6 test, 22/22 probe guard; gói xuất chạy 6/6 PASS.
- So sánh cùng nhánh trả 3: 5 seed; uniform 0/5, edge-enriched 5/5, SMT trực tiếp 5/5.
- Dr. Memory: 141 fixture lặp 10 vòng =1.410 lần gọi, 0 definite application leak;
  còn potential possible 24 byte ntdll/TLS giống đối chứng sạch.
- Không có cặp v0/v1 lỗi sản phẩm đã xác nhận; không dựng before/after giả.
- PDF trang 22 liệt kê ảnh còn cần bổ sung; ảnh có sẵn không đại diện mọi lượt chạy.

Excel là bản rà thủ công theo bằng chứng, không sinh lại để ghi đè nó: nguồn sinh
Excel còn một số ghi chú lịch sử. 55 ca tài liệu hóa không có nghĩa GUI chạy đủ 55 ca.

## Đối chiếu phiên bản

SHA-256 `ma-nguon/stock_json_seclab.c`:
`dae8dd9162d9e8929f9a67af7cee1555b90ff42ae70995802c0b89ea185a82c5`.

SHA-256 `dac-ta/stock_spec.json`:
`e078aaccd1b2aa5b2b425c09e4292a6c0cc9488c41d8e042451217efe36bb88c`.

Các đường dẫn `results/...` trong PDF/log gốc tương ứng `bang-chung/results/...`
trong bộ nộp. Đường dẫn máy gốc trong log là dữ liệu truy vết, không phải đường dẫn
phải tồn tại trên máy thầy. Xem [danh mục bằng chứng](bang-chung/README.md).
