# Biên bản cập nhật tài liệu ngày 20/10/2026

## Bổ sung ảnh thực (sau lần rà 16 trang bên dưới)

PDF có ảnh `Bao_cao_An_toan_phan_mem.images-20261020.pdf` dài 25 trang.
PDF chính bị ứng dụng giữ mở, thao tác Copy-Item bị từ chối nên chưa thay được bản 16 trang.
Trang 14–21 của bản có ảnh có 8 nguồn ảnh gốc: 1 Ch1, 2 Ch2, 5 Ch3.
Mỗi trang nhúng ảnh toàn cảnh và chi tiết từ chính ảnh, không sửa nội dung ảnh gốc.
Nguồn Ch1 được sao chép khỏi Temp vào `ch1-gui-user-20261018.png`; 7 ảnh khác dùng
file lưu trong thư mục ch123. PDF chứa 8 trang ảnh, mỗi trang 2 đối tượng ảnh để trình bày.
Đã render 25 trang, xem cả 3 contact sheet và kiểm tra riêng trang 14, 18, 21.
Trang 22 liệt kê những ảnh chưa có: không biến log thực thành ảnh terminal dựng lại.
Bản 16 trang trước thay đổi: `Bao_cao_An_toan_phan_mem.before-images-20261020.pdf`.
Không đổi Excel hoặc mã nguồn nghiệp vụ; chỉ sửa bộ dựng báo cáo và ghi chú tài liệu.

Phạm vi: cập nhật PDF và rà Excel theo bằng chứng đã chạy. Không chạy lại chiến dịch
fuzz dài, không sửa web, mã C, spec, generator hoặc nguồn Java tham chiếu.
Thông tin nhóm tạm để trống; Ch5–Ch6 không được ghi nhận hoàn tất.

## Nguồn đối chiếu

- `results/ch123-20261018-202400-9a09dbce/`: Ch1, Ch2, Ch3, ảnh GUI và gói xuất.
- `results/comparison-20261018-110108-14dd28b3/summary.json`: 15 lượt trên 5 seed.
- `results/leak-20261018-225714-fe111d0d/leak-summary.json`: đối chứng và 1.410 lần gọi.
- Các chiến dịch JSON/sanitizer lịch sử được ghi riêng trong phần 6.1–6.3, không cộng gộp.

## Kết quả rà soát

- PDF có 16 trang, đủ 8 phần theo cấu trúc cũ; render cả 16 trang, xem 2 ảnh tổng quan
  và kiểm tra riêng trang 11–13 chứa số liệu mới. Không thấy mất dấu, tràn bảng hoặc cắt chữ.
- Kiểm tra trích xuất PDF: tất cả trang có nội dung, không có ký tự thay thế U+FFFD.
- Excel giữ nguyên tên/thứ tự 10 sheet, 12 yêu cầu và 55 ca kiểm thử.
- Chỉ 8 ô thay đổi giá trị: ThongTin!B13, B14, B15, B16, B17, A18, B18; TestCase!F51.
- Mọi giá trị ô khác giữ nguyên, kể cả đầu vào TC-SMT1 quantity=101 của lượt cũ.
- Ghi rõ gói GUI mới dùng quantity=0; không gán kết quả thực thi mới cho fixture cũ.
- Giữ nguyên freeze panes A2 ở cả 10 sheet; workbook không có table/data-validation trước/sau.
- Tính lại và kiểm tra lỗi Excel: không có #REF!, #DIV/0!, #VALUE!, #NAME?, #NUM!, #NULL!.
- Chỉnh chiều cao/wrap các dòng ghi chú ThongTin 13–18 để đọc đủ nội dung.
- Các ghi chú mới là tổng hợp thủ công, không thay nguồn nghiệp vụ. Chạy lại builder Excel
  từ stock_json_fuzz.py sẽ không tự mang các ghi chú mới, phải tránh ghi đè bản đã rà.

## Giới hạn được giữ trong tài liệu

- 100% là 22/22 probe của guard, không phải toàn bộ parser hay website.
- Uniform 0/5 chỉ là chưa tìm thấy trong ngân sách; không tính tỷ lệ tăng tốc vô hạn.
- SMT trực tiếp cùng nhánh không đồng nhất bộ máy concolic đầy đủ.
- Leak: 141 fixture lặp 10 lần, không phải 1.410 đầu vào độc lập. Còn potential possible
  24 byte ntdll/TLS giống đối chứng sạch; chưa chạy LeakSanitizer.
- Không tạo v0/v1 hay lỗi sản phẩm giả. BMC toàn mô hình chưa thực hiện.

## Khôi phục và truy vết

Bản trước cập nhật: `Bao_cao_An_toan_phan_mem.pdf.before-20261020`,
`badminton_spec.xlsx.before-20261020`, hai file builder cùng hậu tố, đều nằm cùng thư mục này.
Đây là bản sao byte nguyên gốc; muốn mở trực tiếp cần sao chép ra tên có đuôi PDF/XLSX đúng.
Không xóa bản sao, log hoặc ảnh cũ.

Hash C trước/sau phải giữ nguyên:
`dae8dd9162d9e8929f9a67af7cee1555b90ff42ae70995802c0b89ea185a82c5`.

Chưa tạo gói nộp, chưa commit/tag và chưa gửi bài. Mục “chốt phiên bản/kiểm tra bộ nộp”
trong PDF giải thích bước rà soát sau cùng, không khẳng định đã làm mọi điều kiện nộp.
