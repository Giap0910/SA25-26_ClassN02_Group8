# Kết quả Ch2 — Bộ nhớ và phân tích tĩnh C

Ngày kiểm tra: 18/10/2026. Phạm vi: bản C tồn kho/JSON độc lập, không phải HTTP, database hoặc PayOS.

## Kết luận

Đã hoàn tất các kiểm tra Ch2 nêu trong tài liệu này và lưu bằng chứng. Cảnh báo CWE-401 tại dòng 263
được phân loại là cảnh báo giả sau đối chiếu đường cấp phát–giải phóng. Phần Struct Alignment của GUI
không nhận diện được khai báo hiện tại; đã bổ sung số đo từ compiler thực.
Không có thay đổi nghiệp vụ C hoặc mã web để làm mất cảnh báo.

Đây không phải kết luận chương trình không còn lỗi. LeakSanitizer chưa chạy; nếu thầy bắt buộc
phải có log LeakSanitizer thì yêu cầu đó vẫn chưa được đáp ứng. Báo cáo PDF chính chưa cập nhật mục này.

## 1. Đầu vào và nguồn bằng chứng

- Mã C: `stock_json_seclab.c`, SHA-256 `dae8dd9162d9e8929f9a67af7cee1555b90ff42ae70995802c0b89ea185a82c5`.
- Hai ảnh GUI là ảnh Phong cung cấp, đã sao chép nguyên bản: `ch2-gui-struct.png`, `ch2-gui-memory-warning.png`.
- `compiler-analysis.json` lưu câu lệnh và phiên bản GCC 16.2, Clang 23.1.3 từ lượt phân tích cùng mã C.
- Log và chương trình thử mới nằm dưới thư mục kết quả này; không sửa file C nộp.

## 2. Kiểu, kích thước, record và alignment

Compiler: LLVM-MinGW Clang 23.1.3, đích Windows x86_64. Đơn vị trong bảng là byte.

| Kiểu | Kích thước | Alignment | Offset thành viên theo thứ tự khai báo |
|---|---:|---:|---|
| `Input` | 24 | 4 | available 0; reserved 4; va 8; vr 12; quantity 16; action 20 |
| `Stock` | 24 | 4 | available 0; reserved 4; va 8; vr 12; state 16; variant 20 |
| `JsonReader` | 24 | 8 | data 0; size 8; pos 16 |
| `JsonFixture` | 40 | 8 | input 0; quantities 24; count 32 |

Bằng chứng compiler: `ch2-record-layouts.log`. Câu lệnh:

```text
x86_64-w64-mingw32-clang.exe -std=c11 -Xclang -fdump-record-layouts-complete -fsyntax-only stock_json_seclab.c
```

GUI báo “Không tìm thấy struct nào trong mã nguồn” trong khi compiler nhận diện được bốn struct.
Ghi nhận đây là giới hạn nhận diện của GUI, không ghi là GUI phân tích alignment thành công.
Không sửa typedef hoặc ép packing để lấy kết quả đẹp. Số đo chỉ áp dụng ABI/compiler nêu trên.

`int32_t`/`uint32_t` là 4 byte. Con trỏ và `size_t` trong đích đo này là 8 byte.
Giới hạn fixture: 16.384 byte đầu vào, 64 byte/token số, 1–100 record `items`;
mỗi quantity và tổng quantity cùng sản phẩm thuộc 1–100.
`calloc(100, sizeof(int32_t))` yêu cầu 400 byte vùng heap; 40 byte của `JsonFixture`
không bao gồm vùng heap này. Kích thước struct không phải độ dài JSON hoặc envelope nhị phân 28 byte.

## 3. Đối chiếu cảnh báo CWE-401

GUI báo tại dòng 263 rằng con trỏ `quantities` được cấp phát nhưng không thấy `free()` trong `jsonEvaluate`.
Đây là nội dung được đối chiếu từ ảnh GUI người dùng cung cấp, không phải log tự thu bằng công cụ.

Đường thực thi trong `stock_json_seclab.c`:

| Dòng | Hành vi | Đánh giá |
|---|---|---|
| 260 | Từ chối NULL hoặc đầu vào quá dài trước cấp phát | Chưa có vùng nhớ cần giải phóng |
| 263 | `fixture.quantities = calloc(...)` | Cấp phát tối đa 100 phần tử int32 |
| 264 | Nếu kết quả NULL, trả mã 105 | Không có vùng nhớ cấp phát thành công |
| 265–266 | Parse/kiểm tra/nghiệp vụ; lưu mã kết quả | Không có return sớm tại đây |
| 267 | `free(fixture.quantities);` | Giải phóng sau cấp phát thành công |
| 268 | Trả mã kết quả | Sau free |

Trong luồng trả về bình thường của hàm, cấp phát thành công đều đi qua free trước khi thoát,
kể cả khi parser trả lỗi. Vì thế mô tả “không thấy free trong hàm” không khớp mã nguồn.
Khả năng heuristic chưa liên kết được con trỏ thành viên là suy luận, chưa xác minh mã phân tích của ứng dụng.
Không ghi “đã vá CWE-401”: không có bản vá vì không xác nhận lỗi tại vị trí này.

## 4. Kiểm thử và phân tích bổ sung

`ch2-memory-tests.log` ghi bốn nhóm kiểm tra đạt, không lỗi hoặc bỏ qua:

1. Tiêm kết quả cấp phát NULL trong bản C thử: entry trả 105, không dereference NULL.
2. Bản C thử gắn bộ đếm vào calloc/free: số khối sống về 0 sau từng ca gọi qua thư viện.
3. Hồi quy JSON: 41 ca qua CLI và 40 ca qua DLL đối chiếu mã trả về/oracle.
4. Hai chương trình lỗi mẫu riêng: ASan phát hiện use-after-free và UBSan phát hiện tràn số có dấu.

Các chương trình thử được lưu tại `generator-tests-cab560bc/`.
Lỗi của chương trình mẫu không phải lỗi của simulator hoặc website.
Bộ đếm là instrumentation trong bản thử, không phải LeakSanitizer và không đo mọi lỗi bộ nhớ.
Wrapper chuỗi C dừng tại NUL đầu tiên; ca NUL nhúng đầy đủ được kiểm tra qua CLI có độ dài,
không coi phép gọi DLL giữ nguyên phần sau NUL.

GCC chạy `-fanalyzer -Wall -Wextra -Werror -Wno-unused-function`, mã thoát 0, không phát cảnh báo.
Các file `ch2-gcc-analyzer.stdout.log` và `.stderr.log` rỗng là kết quả không phát thông báo;
`compiler-analysis.json` lưu mã thoát để tránh nhầm với chưa chạy công cụ.

## 5. Chạy ASan/UBSan mới trên cùng đặc tả

Kết quả nằm tại `sanitizer-20261018-212014-2669991f/summary.json`; log tổng hợp `ch2-sanitizer.log`.

- Biên dịch với `-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer`.
- Chạy 41 ca hồi quy, 100 lượt đột biến với seed 1; phần đột biến mất khoảng 41,63 giây.
- Không ghi nhận crash, timeout, vi phạm bất biến, lệch oracle hoặc lỗi sanitizer trong lượt này.
- Không đo coverage trong lượt sanitizer; không nhập coverage của chiến dịch khác vào đây.
- `leak_sanitizer=false`; runner đặt `detect_leaks=0`. Không gọi đây là phép đo leak của ASan/LSan.
- Bản CLI có thêm main so với bản nạp GUI, nhưng nghiệp vụ/parser cùng bộ sinh; metadata và source snapshot
  của lượt sanitizer được giữ để đối chiếu, không khẳng định hai file có cùng hash nguyên file.

## 6. Cách trình bày nghiệm thu

Trình bày ảnh quét GUI trước, sau đó chỉ ra calloc dòng 263 và free dòng 267.
Đưa bảng struct từ compiler, log kiểm tra NULL/cân bằng cấp phát và kết quả sanitizer làm bằng chứng bổ sung.
Ghi rõ giới hạn GUI, giới hạn ngân sách thử và chưa có LeakSanitizer.
Không cần tạo lỗi cố ý trong mã nộp hoặc gọi cảnh báo giả là lỗ hổng đã sửa.

Phần thực nghiệm Ch2 trong phạm vi trên đã xong. Chỉ chuyển Ch3 sau khi Phong xem và thống nhất
kết luận này; nếu yêu cầu nghiệm thu bắt buộc LeakSanitizer thì phải bổ sung môi trường hỗ trợ trước khi chốt yêu cầu đó.

## 7. Bổ sung sau lượt kiểm tra ban đầu

Đã có phép đo leak bằng Dr. Memory, công cụ động chuyên dụng trên Windows, tại
`results/leak-20261018-225714-fe111d0d/leak-assessment.md` tính từ gốc dự án.
Đối chứng leak 123 byte được phát hiện đúng; đối chứng free đúng và simulator không báo leak xác định.
Simulator xử lý đủ 1.410 lượt (141 đầu vào lặp 10 vòng) và khớp oracle.
Một potential possible leak 24 byte cùng stack trong ntdll xuất hiện cả ở đối chứng sạch và simulator;
đã giữ riêng trong kết luận, không coi toàn bộ log là không có cảnh báo.

Phần thiếu công cụ dò leak chuyên dụng đã được bổ sung bằng Dr. Memory. LeakSanitizer vẫn chưa chạy;
nếu tiêu chí bắt buộc công cụ đó thì chưa đáp ứng tiêu chí riêng này. Các kết luận phía trên mô tả mốc kiểm tra trước bổ sung.
