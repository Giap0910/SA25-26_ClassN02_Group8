# Bằng chứng thực chạy được chọn lọc

Giữ nguyên nội dung file gốc; không gõ lại log thành kết quả mới. Các thư mục dưới
`results/` giữ tên lượt chạy để đối chiếu đường dẫn trong PDF.

| Thư mục | Bằng chứng chính |
|---|---|
| `ch123-20261018-202400-9a09dbce/` | CTL độc lập; Ch2 layout/static/sanitizer; Ch3 CFG/SMT, ảnh GUI, pytest |
| `comparison-20261018-110108-14dd28b3/` | Summary 15 lượt, source snapshot và pytest |
| `leak-20261018-225714-fe111d0d/` | Fixture, control C, summary, log Dr. Memory và potential_errors |
| `stock-json-20261018-083428-95703d48/` | Summary chiến dịch lịch sử 3.000 input |
| `sanitizer-20261018-084125-187616c4/` | Summary lượt sanitizer lịch sử 1.384 input |
| Các lượt `093532` / `093549` | Summary lượt JSON 200 input và sanitizer 100 input |
| `report-final/` | Ảnh Ch1 gốc, log/XML pytest lịch sử và biên bản cập nhật tài liệu |

Không đưa compiler, executable/DLL, cache Dr. Memory/symbol/PDB, gcov trung gian,
ảnh render PDF hoặc các bản PDF backup lên GitHub. Full AST Clang ~14 MB không
đưa vào bộ chọn lọc này; báo cáo phân biệt nó với kết quả heuristic GUI.
Không đưa log startup Dr. Memory chưa chạy thành công làm bằng chứng “sạch”.

Dr. Memory: dùng đúng report positive PID16552, negative PID21052, simulator PID22444.
Giữ `potential_errors.txt` cạnh report nếu có; cảnh báo potential 24 byte chưa bị
loại trừ triệt để. Bộ lọc hệ thống mặc định vẫn bật, không thêm suppression riêng.

Thư mục `kiem-tra-dong-goi-20261020/` (nếu có) là log kiểm tra bản phân thư mục khi
chuẩn bị GitHub, không phải thay thế kết quả lịch sử trong báo cáo.
