# Bản vá giới hạn đầu vào hàm jsonInteger

Ngày thực hiện: 22/10/2026. Phạm vi: mô hình C tồn kho và wrapper SecLabFramework; không phải website/backend Java.

## 1. Vấn đề và điều kiện tái hiện

`jsonInteger` sử dụng `char digits[64]`. Trước vá, vòng đọc ghi `digits[count++]` nhưng hàm không tự kiểm tra giới hạn độ dài đầu vào. Khi gọi trực tiếp với chuỗi 65 chữ số và size=65, vòng ghi truy cập phần tử thứ 65, vượt mảng. Phân loại phù hợp: CWE-787, ghi ngoài biên bộ nhớ ngăn xếp.

Đường gọi cần phân biệt:

- Qua parser `stock_json`: `jsonScanNumber` đã giới hạn token 64 byte. Ca JSON có token 65 chữ số được từ chối mã 100 cả trước và sau vá; không tái hiện lỗi qua đường này.
- Qua hàm export `sl_wrap_jsonInteger` của shim: helper được gọi trực tiếp, bỏ qua giới hạn parser. Harness gọi trực tiếp cùng helper xác nhận lỗi trước vá; thư viện wrapper được biên dịch lại riêng đã kiểm tra từ chối đầu vào dài sau vá.
- Không kết luận đây là lỗi HTTP, lỗi website hoặc lỗi transaction. Không tuyên bố đã khai thác để thực thi mã.

## 2. Bằng chứng trước vá

- Snapshot: `before-stock_json_seclab.c`.
- Harness: `before-probe.c`, sinh từ `verify_patch.py` và include đúng snapshot.
- Kết quả: `before-results.json`, `before-overflow.log`.
- Biên dịch Clang với `-fsanitize=address,undefined -fno-sanitize-recover=all`.
- Đầu vào: 65 ký tự `1`, size=65, biến kết quả ban đầu 77.
- Tiến trình thoát 1; UBSan báo: `runtime error: index 64 out of bounds for type 'char[64]'`.
- UBSan dừng trước; không ghi thành “ASan đã báo stack-buffer-overflow”. Lần chạy đầu của script đòi riêng thông báo ASan nên assertion của script thất bại; đã sửa điều kiện nhận diện đúng chẩn đoán UBSan thực tế. Log và snapshot đầu được giữ nguyên, không chạy lại hoặc sửa bằng chứng cũ.
- Ca số hợp lệ và ca JSON công khai đều thoát 0 trước vá.

## 3. Nội dung bản vá

Thêm điều kiện đầu hàm, trước lần truy cập text[0]:

```c
if (!text || !output || size == 0 || size > 64) return 0;
```

Điều kiện từ chối con trỏ NULL, đầu vào rỗng và token vượt 64 byte; không ghi biến kết quả khi từ chối. Giới hạn khớp hợp đồng parser hiện tại.

File đã sửa:

- `stock_json_adapter.c`: nguồn adapter chính, thêm kiểm tra.
- `stock_json_seclab.c`: sinh lại nghiệp vụ + adapter đã vá, giữ chú thích công dụng đầu file.
- `sl_target.c`: đồng bộ cùng nội dung được sinh, giữ chú thích đầu file riêng.
- `test_generator.py`: thêm kiểm thử helper, đồng thời cho phép chú thích công dụng đầu file khi đối chiếu mã nộp với bộ sinh. Không bỏ qua khác biệt thân mã.

Không sửa đặc tả, Java tham chiếu, nghiệp vụ giữ/hoàn/tất toán, Word hoặc Excel. Hash các đầu vào chính được ghi trong `verification.json`.

## 4. Kết quả sau vá

Nguồn: `after-results.json`, `after-*.log`, `regression-tests.log`, `verification.json`.

| Kiểm tra | Trước vá | Sau vá |
|---|---|---|
| Helper nhận 65 chữ số | UBSan phát hiện ghi vượt mảng, exit 1 | Trả 0, giữ output=77, exit 0 |
| Các số hợp lệ, int32 biên, số thập phân/số mũ nguyên | Các ca trong harness đạt | Đạt, giữ đúng giá trị |
| Helper nhận token 64 byte biểu diễn số 1 với số 0 đầu | Đạt | Đạt |
| NULL input/output, size=0, size=65 với buffer ngắn | Không chạy các ca này trước vá | Từ chối an toàn trong harness, exit 0 |
| JSON công khai có token 65 chữ số | Mã 100 | Mã 100 |
| Hồi quy JSON CLI / DLL | Dùng log lịch sử riêng; không chạy mới trước vá | 41 /40 ca đạt trong lượt sau vá |
| Sáu ca guard qua DLL shim mới | Không chạy mới trước vá | 6/6 đúng mã 0–5 |
| Helper qua DLL shim mới | Không chạy mới trước vá | Chuỗi 65 byte bị từ chối |

Năm phương thức unittest được chọn đều đạt, không lỗi và không bỏ qua: helper bounds, hồi quy JSON/DLL, đồng bộ bộ sinh, cấp phát thất bại, cân bằng cấp phát. Phép thử helper còn kiểm tra biên 63/64 byte. Đây là tập kiểm tra cố định, không phải chạy lại toàn bộ bộ test hoặc chiến dịch fuzz.

## 5. Truy vết và giới hạn

- Snapshot trước/sau, câu lệnh compiler, phiên bản compiler, exit code và stdout/stderr được lưu trong hai file results JSON. `verification.json` lưu hash mã đã vá và kết quả wrapper.
- DLL mới: `patched-seclab-wrap.dll` trong thư mục bằng chứng. Đã biên dịch từ shim hiện có include `sl_target.c` đã vá.
- **DLL gốc `libstock_json_seclab_wrap.dll` chưa bị ghi đè.** Import wrapper Python mặc định có thể tiếp tục dùng DLL cũ. Muốn chạy bản vá trong SecLabFramework phải nạp lại C và biên dịch/wrap lại; các tiến trình đã nạp DLL cũ cần được khởi động lại theo thao tác của người dùng.
- Không tự thao tác ứng dụng thầy đang chạy; chưa có ảnh/log GUI sau vá. Bằng chứng hiện tại là compiler, sanitizer và ca cố định chạy ngoài GUI.
- Chưa chạy fuzz sau vá, chưa chạy LSan/BMC; không kết luận hết mọi lỗi bộ nhớ.
- Người gọi C vẫn phải cung cấp vùng nhớ hợp lệ có ít nhất `size` byte và token hợp lệ về cú pháp theo hợp đồng helper. Không có phép kiểm tra độ dài nào xác minh được dung lượng thật của một con trỏ C tùy ý. Bản vá này không kiểm toán toàn bộ các helper khác do công cụ xuất.

## 6. Đoạn có thể đưa vào báo cáo

Qua kiểm tra đường gọi helper được xuất cho SecLabFramework, nhóm xác định hàm jsonInteger chưa tự giới hạn độ dài trước khi ghi vào mảng digits gồm 64 phần tử. Ca gọi trực tiếp với 65 chữ số bị UndefinedBehaviorSanitizer phát hiện truy cập chỉ số 64 vượt mảng. Nhóm bổ sung kiểm tra con trỏ, đầu vào rỗng và độ dài tối đa 64 byte ngay đầu hàm, sau đó đồng bộ mã C từ adapter. Cùng ca trước đó được từ chối sau vá và không phát sinh chẩn đoán sanitizer trong tập thử cố định. Năm nhóm kiểm tra chọn lọc đạt, bao gồm 41 ca JSON và 40 ca DLL; sáu ca guard qua shim mới giữ đúng mã trả về. Parser JSON công khai đã từ chối token dài cả trước và sau vá, nên kết luận lỗi áp dụng đường gọi trực tiếp helper, không suy rộng sang website hoặc mọi đầu vào C.

## 7. Thao tác còn lại trong ứng dụng thầy

1. Nạp lại `stock_json_seclab.c` đã vá vào SecLabFramework.
2. Biên dịch và tạo lại wrapper bằng chức năng của ứng dụng; không dùng DLL cũ để chứng minh bản vá.
3. Chỉ thử helper nếu ứng dụng hỗ trợ truyền đúng buffer, size và con trỏ output. Không thay việc truyền con trỏ bằng tham số số nguyên tùy ý. Nếu GUI không hỗ trợ, dùng bằng chứng harness và ghi đúng giới hạn này.
4. Lưu ảnh/log thật của lượt sau vá nếu yêu cầu báo cáo cần bằng chứng GUI. Không gọi log terminal là log GUI.
5. Đưa mục bản vá vào Word, đồng bộ ghi chú Excel và xuất lại PDF sau khi Phong chốt nguồn báo cáo chính. Lượt này chưa sửa các tài liệu đó.
