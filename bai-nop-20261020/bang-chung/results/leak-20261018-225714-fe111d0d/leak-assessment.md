# Đối chiếu kiểm tra rò rỉ bộ nhớ bằng Dr. Memory

Ngày thực hiện: 18/10/2026. Phạm vi: simulator C tồn kho/JSON độc lập trên Windows x64.

## Kết quả

Đã bổ sung phép kiểm tra leak bằng công cụ động chuyên dụng Dr. Memory 2.6.0.
Không chạy LeakSanitizer và không gọi kết quả này là log LeakSanitizer.

| Thử nghiệm | Kết quả |
|---|---|
| Đối chứng cố ý bỏ quên vùng malloc 123 byte | Phát hiện đúng 1 leak xác định, 123 byte; mã thoát 23 theo cấu hình |
| Cùng chương trình, gọi free đúng | Không báo leak xác định; mã thoát 0 |
| Simulator: 41 ca hồi quy + 100 đầu vào đột biến seed 1, lặp 10 vòng | Đủ 1.410 lượt, mã thoát 0; không báo leak xác định của ứng dụng |
| Đối chiếu kết quả simulator với oracle | 1.410/1.410 kết quả khớp cả mã trả về và trạng thái kho |

Có một cảnh báo riêng `POSSIBLE LEAK 24 direct bytes` trong `potential_errors.txt`,
với stack thuộc `ntdll.dll` và luồng loader/TLS. Cảnh báo có cùng stack ở cả đối chứng sạch và simulator.
Vì thế chưa có bằng chứng quy nó cho parser/tồn kho; không khẳng định đã chứng minh cảnh báo này vô hại.
Giữ nguyên báo cáo này cùng các mục `ERRORS IGNORED` và `still-reachable`, không xóa hoặc che bằng suppression mới.

Kết luận dùng khi nghiệm thu: **Trong workload đã chạy, Dr. Memory không báo leak xác định ở simulator;
công cụ đã nhận diện đúng leak đối chứng. Còn một cảnh báo nghi ngờ 24 byte ở thư viện Windows,
cũng xuất hiện trong đối chứng sạch. Không kết luận toàn bộ chương trình tuyệt đối không leak.**

## Công cụ và môi trường

- Gói portable chính thức: https://github.com/DynamoRIO/drmemory/releases/download/release_2.6.0/DrMemory-Windows-2.6.0.zip
- Gói nén 97.400.372 byte; tổng nội dung ZIP khai báo 433.500.874 byte.
- SHA-256 gói đã tải: `07632ab77856579d06e30de344c669e9bdcbde9688b6ef43e84d31c39c6e46b2`.
  Đây là hash lưu để truy vết; metadata bản phát hành không có digest độc lập để đối chiếu.
- Compiler GCC 16.2, `-std=c11 -Wall -Wextra -Werror -O0 -g -gdwarf-4 -fno-inline -fno-omit-frame-pointer`.
- Chế độ Dr. Memory: `-leaks_only -check_leaks -count_leaks -batch -no_follow_children -no_fetch_symbols`.
  Không dùng `-light`, không tắt kiểm tra leak. Các bộ lọc/suppression hệ thống mặc định vẫn được giữ.
- Lần đầu công cụ tự tạo bảng syscall cho Windows build 19045 và tải symbol hệ thống vào cache bên trong
  thư mục kết quả. Lần đầu có một log khởi động chưa hoàn tất rồi tự chạy lại thành công;
  chỉ dùng `results.txt` có `FINAL SUMMARY` để xác nhận kết quả, không coi log khởi động là kết quả sạch.
- Công cụ nằm trong `toolchain/drmemory-2.6.0/`, không cài toàn hệ thống, không sửa PATH hệ thống,
  không tắt phần mềm bảo mật và không cài WSL.

## Cách kiểm tra và tính tái lập

`leak_control.c` là chương trình đối chứng riêng. Cùng một EXE nhận `leak` hoặc `clean`;
chỉ chế độ clean gọi free. Lỗi cố ý trong chương trình này không phải lỗi của simulator/website.

`stock_json_target.c` được sinh từ cùng đặc tả và adapter hiện tại. `leak_batch.c` chỉ đổi tên entry main
khi include bản C thử rồi gọi lại entry CLI theo danh sách file, lặp 10 vòng trong một tiến trình.
Không sửa đường calloc/free của sản phẩm. Kiểu đọc CLI có độ dài giữ được ca NUL nhúng.

`cases.json` lưu tên, loại, độ dài, hash và kết quả oracle của 141 đầu vào.
Các byte đầu vào nằm trong `inputs/`. 1.410 là số lần thực thi do lặp dữ liệu, không phải 1.410 đầu vào fuzz độc lập.
Các ca quá dài có thể bị từ chối trước cấp phát; không đồng nhất số lượt xử lý với số lần calloc thành công.

Bản C nộp, đặc tả, adapter, bộ sinh và runner gốc không thay đổi sau phép thử.
Hash C nộp: `dae8dd9162d9e8929f9a67af7cee1555b90ff42ae70995802c0b89ea185a82c5`.
Bản CLI thử có thêm main nên hash nguyên file khác bản nạp GUI; không coi hai file là một binary.

## Bằng chứng cần giữ

- `leak-summary.json`: kết quả đối chiếu tự động, hash nguồn và giới hạn.
- `control-leak-run.json`, `control-clean-run.json`, `simulator-run.json`: câu lệnh thực chạy và mã thoát.
- `control-leak-logs/DrMemory-leak_control.exe.16552.000/results.txt`: leak đối chứng 123 byte.
- `control-clean-logs/DrMemory-leak_control.exe.21052.000/results.txt`: đối chứng free đúng.
- `simulator-logs/DrMemory-leak_batch.exe.22444.000/results.txt`: báo cáo simulator.
- `potential_errors.txt` trong từng thư mục báo cáo: giữ cảnh báo nghi ngờ của hệ thống.
- `native.stdout.log`, `simulator.stdout.log`: kết quả chạy C không có/có công cụ, đã đối chiếu oracle.

## Giới hạn

Đây là kiểm tra leak trên workload hữu hạn, không đo coverage và không thay thế lượt ASan/UBSan trước đó.
Không chứng minh mọi đường đi parser, mọi dữ liệu hoặc website thật đều an toàn.
Nếu thầy yêu cầu đích danh LeakSanitizer thay vì chấp nhận công cụ dò leak tương đương,
vẫn phải bổ sung môi trường hỗ trợ; không đổi tên Dr. Memory thành LeakSanitizer trong báo cáo.

PDF và Excel chính chưa được cập nhật số liệu mới này. Phần kiểm tra leak chuyên dụng đã có bằng chứng;
việc chấp nhận giới hạn và yêu cầu công cụ cụ thể cần trình bày đúng khi nghiệm thu.
