# An toàn phần mềm — SA25-26 lớp N02 nhóm 8

Đề tài **Badminton Stock Security**, kiểm thử mô hình tồn kho C bằng fuzzing và độ phủ. Bộ nộp hiện tại tập trung Ch4; Ch3 hỗ trợ phân tích nhánh và chọn đầu vào.

**Bắt đầu tại [hướng dẫn bộ nộp](badminton-stock-security-20261022/README.md).**

| Nội dung | Đường dẫn |
|---|---|
| Báo cáo mới và phân công nhóm | [Baocao.docx](badminton-stock-security-20261022/bao-cao/Baocao.docx) |
| Đặc tả và mô hình | [dac-ta-mo-hinh](badminton-stock-security-20261022/dac-ta-mo-hinh/) |
| Mã C nạp ứng dụng | [ma-c](badminton-stock-security-20261022/ma-c/) |
| Bộ sinh, fuzz, oracle và kiểm thử | [bo-sinh-kiem-thu](badminton-stock-security-20261022/bo-sinh-kiem-thu/) |
| Nguồn Java đóng băng | [java-tham-chieu](badminton-stock-security-20261022/java-tham-chieu/) |
| Excel 5 sheet và 57 ca thiết kế | [badminton_spec.xlsx](badminton-stock-security-20261022/excel/badminton_spec.xlsx) |
| Gói test xuất ứng dụng | [test-ung-dung](badminton-stock-security-20261022/test-ung-dung/) |
| Ảnh, log và snapshot đối chiếu | [bang-chung](badminton-stock-security-20261022/bang-chung/README.md) |

Kết quả GUI đã lưu: 581 input, giữ 13 test; pytest chạy lại đạt 13/13 trong 2,84 giây theo characterization. Coverage hiển thị 75% thuộc phạm vi mục tiêu qua wrap, không phải toàn dự án. Đọc giới hạn trong báo cáo và README của bộ nộp.

Không cần website, MySQL hoặc PayOS để chạy mô hình độc lập này. Compiler, môi trường Python, DLL/EXE và các kết quả trung gian lớn không nằm trong bộ nộp.
