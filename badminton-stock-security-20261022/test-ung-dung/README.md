# Test xuất từ SecLabFramework

## Bộ mới 13 test của stock_json_case

- `test_target_stock_json_case_fuzz.py`: 4 boundary, 4 black-box, 3 mutation, 2 coverage-guided.
- `target_wrap.py`: gọi C trong tiến trình con; tự biên dịch nếu thiếu DLL.
- `target_shim.c`: xuất hàm C cho ctypes; include `sl_target.c`.
- `sl_target.c`: snapshot C trong gói xuất, tương đương mã C hiện tại khi bỏ khác biệt dòng trắng cuối file.

Sau khi chạy `huong-dan/chuan_bi.py`, dùng đúng lệnh pytest tại `.work` trong README chính. Không kèm `libtarget_wrap.dll`; cần gcc để wrapper tạo thư viện trên máy nhận. Thư mục `.work` giữ test, wrapper, shim, C đích và thư viện sinh ra cùng nhau.

Ảnh đã lưu xác nhận **13 passed in 2.84s**, chế độ **characterization**. Đây là chạy lại mã trả đã ghi nhận và trạng thái tiến trình, chưa thay cho oracle kiểm tra trạng thái tồn kho cuối. 100% trong tiến độ pytest không phải coverage.

## Bộ guard lịch sử

`test_stock_json_seclab_stock_reserve_guard_fuzz.py`, `stock_json_seclab_wrap.py`, `stock_json_seclab_shim.c` là bộ guard có tên wrapper khác. Có sáu test và bằng chứng lịch sử ở `bang-chung/results/ch123-20261018-202400-9a09dbce`. Không cộng sáu test này vào bộ 13 test hoặc nhận kết quả cũ là lần chạy mới.

Không sửa shim hoặc expected bằng tay để cho test đạt; khi thay mã cần xuất/biên dịch lại đúng gói.
