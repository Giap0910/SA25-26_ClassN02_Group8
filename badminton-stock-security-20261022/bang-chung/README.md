# Bằng chứng đối chiếu báo cáo

## Ảnh Ch4 mới

Trong `anh-ch4/`: `chien-dich-581-input.png`, `danh-sach-13-test.png`, `pytest-13-passed.png`. Đây là ảnh gốc người thực nghiệm cung cấp: GUI 581 input/13 test/75%, pytest 13 passed in 2.84s. Chưa có raw hit map và log pytest dạng văn bản cho lượt GUI này; không nhận 75% là toàn parser.

## Hồ sơ chọn lọc trong results

| Thư mục | Tác dụng |
|---|---|
| stock-json-20261018-083428-95703d48 | JSON dài, 3.000 input; summary/metadata và snapshot |
| stock-json-20261018-093532-9d53d681 | JSON ngắn, 200 input; hồi quy và trạng thái đối chiếu |
| sanitizer-20261018-084125-187616c4 | ASan/UBSan dài, 1.384 input; không LeakSanitizer |
| sanitizer-20261018-093549-a35b9b72 | Sanitizer ngắn, 100 input, snapshot lịch sử riêng |
| stock-json-20261022-113600-b677973e | Runner mới 100 input; 41 hồi quy CLI, 40 DLL |
| patch-audit-20261022 | Before/after helper, source và harness, log UBSan, verification và hồi quy |
| ch123-20261018-202400-9a09dbce | Chỉ phần Ch3 guard hỗ trợ: AST → Z3 độc lập, replay C, sáu test lịch sử |

Giữ nguyên nội dung log và snapshot. Đường dẫn tuyệt đối trong log là môi trường lúc thực nghiệm, không tự tồn tại trên máy nhận. Phép đóng gói không chạy lại các lệnh trong hồ sơ.

Đường `results/...` trong báo cáo được ánh xạ sang `bang-chung/results/...`. Không đưa corpus đầy đủ, dump AST lớn, binary, compiler hoặc toàn bộ results lên repository. Ảnh lịch sử cũ đã nằm trong báo cáo; ba ảnh ngoài báo cáo là lượt mới để tiện kiểm tra.
