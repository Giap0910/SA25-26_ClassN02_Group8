# Badminton Stock Security — Nhóm 8

Bộ mã cập nhật ngày 22/10/2026 phục vụ học phần An toàn phần mềm, lớp N02.
Mô hình tồn kho độc lập bằng C/Python: giữ hàng, hoàn khi hủy và tất toán cho một sản phẩm, tối đa một biến thể.

## Các nhóm file

| Thư mục | Nội dung |
|---|---|
| [Hướng dẫn](huong-dan/) | README gốc và công cụ chuẩn bị bản sao chạy |
| [Đặc tả và mô hình](dac-ta-mo-hinh/) | Quy tắc nghiệp vụ JSON, fingerprint Java và mô hình Kripke |
| [Mã C](ma-c/) | Simulator, adapter JSON và mã đầy đủ nạp SecLabFramework |
| [Bộ sinh và kiểm thử](bo-sinh-kiem-thu/) | Sinh C, fuzz/oracle, so sánh SMT và kiểm thử generator |
| [Java tham chiếu](java-tham-chieu/) | Ba file Java đóng băng để truy vết quy tắc, không phải backend chạy độc lập |
| [Excel](excel/badminton_spec.xlsx) | 10 sheet, 12 yêu cầu và 55 ca tài liệu hóa |
| [Test xuất từ ứng dụng](test-ung-dung/) | Sáu test guard, Python wrapper, shim và C đích |

Mã nguồn và Excel được sao chép nguyên byte từ dự án hiện tại. Không đóng gói báo cáo, kết quả fuzz, compiler, môi trường Python hoặc DLL trong bộ cập nhật này. Những dữ liệu ở bộ nộp cũ vẫn được giữ nguyên tại repository.

## Phiên bản và giới hạn

Mã C hiện có kiểm tra NULL, đầu vào rỗng và giới hạn 64 byte tại helper `jsonInteger`, đồng bộ trong adapter, mã nạp và `sl_target.c`. Helper trực tiếp khác với đường parser `stock_json` vốn đã kiểm tra độ dài token. Bản cập nhật này không kèm hồ sơ bằng chứng bản vá.

Chưa chạy lại chiến dịch fuzz hoặc GUI cho bản đóng gói này. Số liệu lịch sử trong README gốc và Excel không được coi là phép đo mới của mã sau vá. Các đường dẫn `results/...` trong tài liệu gốc chỉ về bằng chứng cục bộ, không nằm trong bộ này. 55 ca tài liệu hóa không đồng nghĩa toàn bộ đều đã chạy GUI.

Mô hình không kiểm thử trực tiếp HTTP, MySQL, transaction đồng thời hoặc PayOS. Hash Java chỉ đối chiếu bản tham chiếu đóng băng, không theo dõi website bên ngoài.

## Chuẩn bị bản chạy trên Windows

Từ thư mục `badminton-stock-security-20261022`, dùng Python 3.12 trở lên:

```powershell
python -X utf8 -B huong-dan/chuan_bi.py
```

Công cụ tạo `.work/`, ghép các bản sao vào cấu trúc gốc và đặt Java trong `.work/reference_backend/`. Nếu file làm việc đã khác nguồn, công cụ dừng để tránh ghi đè. Các thư mục nhóm giữ nguyên; `.work/` được Git bỏ qua.

Cần GCC/gcov cùng phiên bản để chạy C và đo coverage. Runner thông thường tìm compiler trên PATH; bài kiểm tra launcher portable cần GCC tại `.work/toolchain/mingw64/bin/`. Sanitizer cần compiler hỗ trợ ASan/UBSan tại `.work/toolchain/llvm-mingw-20261006-ucrt-x86_64/bin/`. Đây là phụ thuộc máy người chạy, không được đóng gói.

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install pytest==9.1.1 z3-solver==5.3.1.0
Set-Location .work
& ..\.venv\Scripts\python.exe -X utf8 -B -m pytest -p no:cacheprovider test_generator.py test_stock_json_seclab_stock_reserve_guard_fuzz.py -q
```

Các lệnh trên dành cho người muốn chạy lại, chưa được thực thi khi đóng gói. Chạy kiểm thử có thể tạo binary và dữ liệu mới trong `.work/`.

Để xem trên ứng dụng thầy: nạp `ma-c/stock_json_seclab.c`; chọn `stock_json` để thử JSON, `stock_json_case` để tạo fixture từ tham số số nguyên, hoặc `stock_reserve_guard` để thử điều kiện giữ hàng. Guard trả 0 chỉ là qua điều kiện, chưa cập nhật kho. Cần biên dịch/wrap lại từ mã mới; không tái sử dụng DLL cũ. Wrapper Python trong `.work/` sẽ biên dịch DLL từ shim nếu chưa có DLL và máy có GCC.
