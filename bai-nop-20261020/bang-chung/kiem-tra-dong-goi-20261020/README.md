# Kiểm tra bản phân thư mục trước khi tải GitHub

Ngày 20/10/2026, chạy trong bản sao `.work/` sau bước `huong-dan/chuan_bi.py`.
Không sửa mã C, spec, test hay nguồn Java tham chiếu; compiler dùng junction local
tới toolchain có sẵn, không đưa junction/compiler lên Git.

Lệnh kiểm tra:

```powershell
python -X utf8 -B -m pytest -p no:cacheprovider test_generator.py test_stock_json_seclab_stock_reserve_guard_fuzz.py -q --junitxml=pytest-dong-goi.xml
```

Kết quả: **38 passed, 10555 subtests passed in 9.91s**. XML gốc ở cùng thư mục.
Đây là kiểm tra đóng gói mới, không thay thời gian các lượt lịch sử trong báo cáo.

Trước đó, chạy trong sandbox thiếu vị trí portable và quyền ghi TEMP gây lỗi
môi trường: lần đầu 7 failed/30 passed/1 skipped; sau đặt junction còn 6 lỗi
PermissionError khi wrapper ghi job.json. Lượt cuối chạy với quyền tiến trình
phù hợp đạt toàn bộ 38 test, không sửa code để che lỗi hoặc bỏ test.

Đối chiếu riêng 19 file nguồn/spec/test/tham chiếu/PDF: khớp byte với dự án gốc.
PDF đúng 25 trang; Excel đúng 10 sheet và 55 ca tài liệu hóa. Các ghi chú Excel
là rà thủ công, không ghi nhận toàn bộ 55 ca đã thực thi trong GUI.

Quét các file text trong bộ mới theo mẫu private key và token phổ biến không
thấy kết quả khớp. Đây không phải cam kết phát hiện mọi dạng bí mật.
Không đưa .env, toolchain, môi trường ảo, executable/DLL, symbol cache hoặc
các ảnh render/backup PDF lên GitHub. Giữ nguyên nội dung cũ có sẵn trên repo.
