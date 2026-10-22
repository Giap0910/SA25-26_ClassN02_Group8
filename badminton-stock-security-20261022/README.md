# Badminton Stock Security — Nhóm 8

Bộ nộp cập nhật ngày 22/10/2026, học phần An toàn phần mềm. Mô hình độc lập kiểm tra giữ hàng, hoàn khi hủy và tất toán cho một sản phẩm, tối đa một biến thể. Trọng tâm Ch4 Fuzzing và độ phủ, có Ch3 hỗ trợ phân tích guard/CFG/SMT.

## Đọc theo thứ tự

1. [Báo cáo và phân công](bao-cao/Baocao.docx).
2. [Excel](excel/badminton_spec.xlsx): 5 sheet, 12 yêu cầu, 57 ca thiết kế; không có nghĩa tất cả 57 ca đã thực thi và PASS.
3. [stock_spec.json](dac-ta-mo-hinh/stock_spec.json) và [mã C đầy đủ](ma-c/stock_json_seclab.c).
4. [Gói test](test-ung-dung/README.md) và [bằng chứng đã lưu](bang-chung/README.md).

## Các nhóm file

| Thư mục | Tác dụng |
|---|---|
| bao-cao | Báo cáo Word mới, gồm bản vá và kết quả Ch4 |
| huong-dan | Hướng dẫn và công cụ chuan_bi.py ghép bản sao để chạy |
| dac-ta-mo-hinh | Đặc tả quy tắc/giới hạn/hash Java; stock_kripke.json là mô hình tham khảo, không bắt buộc chạy Ch1 |
| ma-c | Simulator sinh từ quy tắc, adapter JSON viết riêng, C đầy đủ nạp SecLabFramework |
| bo-sinh-kiem-thu | Bộ sinh, runner fuzz, oracle, so sánh và kiểm thử generator |
| java-tham-chieu | Ba file Java đóng băng để truy vết; không phải backend độc lập |
| excel | Đặc tả và thiết kế ca kiểm thử |
| test-ung-dung | Gói 13 test stock_json_case mới và bộ sáu test guard lịch sử; giữ tên wrapper riêng |
| bang-chung | Ảnh, summary, log và snapshot nhỏ liên quan số liệu báo cáo |

## Chuẩn bị bản chạy Windows

Cần Python 3.12+, GCC/gcov cùng phiên bản trên PATH. Các lệnh dưới chạy từ thư mục `badminton-stock-security-20261022`:

```powershell
python -X utf8 -B huong-dan/chuan_bi.py
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install pytest==9.1.1 z3-solver==5.3.1.0
Set-Location .work
& ..\.venv\Scripts\python.exe -m pytest -v test_target_stock_json_case_fuzz.py
```

`chuan_bi.py` ghép các bản sao vào `.work`, đặt Java tại `.work/reference_backend`, giữ nguyên các nhóm nguồn. Nếu `.work` đã có file khác nguồn mới, công cụ dừng để tránh ghi đè; dùng một bản clone/thư mục làm việc mới khi cần kiểm tra bộ cập nhật, không xóa dữ liệu đang dùng.

Gói không kèm DLL. Wrapper Python sẽ biên dịch từ shim và `sl_target.c` khi thiếu thư viện; cần gcc hoạt động. Chỉ định đúng file pytest, không chạy quét toàn repository có compiler hoặc nhiều bản sao. Tên module/wrapper, shim và `sl_target.c` phải được giữ cùng thư mục như `.work`.

## Chạy Ch4 trong ứng dụng thầy

Nạp `ma-c/stock_json_seclab.c` tại **Sinh test + C wrap**, dò/chọn `stock_json_case`, Wrap & biên dịch rồi sinh test. Chuyển sang **Chiến dịch fuzzing**, xác nhận đúng hàm/mã, chọn Boundary, Black-box, Mutation, Coverage-guided. Lượt đã lưu dùng ngân sách hiển thị 180/kỹ thuật, không sanitizer, không concolic; tổng thực chạy 581, không suy thành 720.

`stock_json` thử chuỗi JSON thô; `stock_json_case` tạo JSON từ bốn số rồi gọi parser/nghiệp vụ; `stock_reserve_guard` chỉ kiểm tra điều kiện, không cập nhật kho. Không chọn helper con trỏ tùy ý. Mã tùy chỉnh trong ứng dụng này dành cho Python theo mẫu.

## Runner oracle khi cần kiểm tra trạng thái cuối

Từ `.work` sau bước chuẩn bị:

```powershell
& ..\.venv\Scripts\python.exe -X utf8 -B stock_json_fuzz.py --iterations 50 --seeds 1 --seconds 30
```

50 lượt/30 giây áp dụng cho mỗi chế độ ở seed 1, chưa gồm mọi bước chuẩn bị. Kết quả mới được tạo trong `.work/results`. Đọc đúng thư mục runner in ra. `oracle_mismatch` và `invariant_failure` bổ sung kiểm tra trạng thái; khác test characterization chỉ phát lại mã đã quan sát.

Bộ `test_generator.py` có kiểm tra cần cấu hình compiler portable hoặc sanitizer riêng; không hứa mọi nhóm test chạy được chỉ với gcc trên PATH. ASan/UBSan cần LLVM-MinGW hỗ trợ sanitizer; LeakSanitizer bị tắt trong các lượt đã báo cáo. Xem yêu cầu từng phép kiểm tra trước khi chạy, không tắt fingerprint hoặc sửa expected để cho qua.

## Kết quả và giới hạn

- GUI stock_json_case: 581 input, 13 test; không tìm thấy lỗi/crash trong ngân sách, khoảng 29,9 giây. Coverage hiển thị 75%, console qua wrap 3/4 khối; không phải 75% toàn parser.
- 13 test characterization được người thực nghiệm chạy đạt trong 2,84 giây; ảnh được lưu. Chưa có log pytest dạng văn bản của lượt đó.
- Runner và sanitizer lịch sử giữ số liệu riêng theo snapshot; không cộng các lượt thành một chiến dịch. Việc đóng gói lần này không chạy lại fuzz hoặc pytest.
- Bản vá jsonInteger chặn NULL/rỗng/token quá 64 byte ở helper gọi trực tiếp. Có snapshot và log trước/sau; không nhận lỗi helper là do chiến dịch 581 input phát hiện.
- Không kiểm thử trực tiếp HTTP, MySQL, transaction đồng thời hoặc PayOS. Java là nguồn đóng băng; hash không tự theo dõi thay đổi website ngoài dự án.

Các đường `results/...` trong báo cáo tương ứng `bang-chung/results/...` trong repository. Đây là hồ sơ chọn lọc, không phải toàn bộ corpus, dump AST, compiler hoặc binary. Hash DLL trong báo cáo chỉ định danh binary cục bộ, không có nghĩa DLL được đưa lên GitHub.
