# Kiểm thử an toàn phần mềm cho tồn kho badminton

Dự án độc lập phục vụ môn An toàn phần mềm. Mã mục tiêu viết bằng C; Python dùng sinh mã, điều phối fuzz và đối chiếu oracle.
Không cần frontend, Spring Boot, MySQL hoặc bản checkout web để sinh C và chạy kiểm thử.

## Phạm vi và nguồn gốc

Mô phỏng một sản phẩm, tối đa một biến thể đã chọn: giữ hàng, hoàn khi hủy, tất toán và lặp thao tác.
Đầu vào JSON là fixture kiểm thử chứa trạng thái kho ban đầu, không phải request HTTP để người mua sửa tồn kho.
Mô hình không kiểm thử trực tiếp website, transaction, khóa đồng thời, giá, voucher hoặc PayOS.

Ba file Java trong `reference_backend/` là bản tham chiếu đóng băng từ sản phẩm gốc.
Chúng không được biên dịch hay chạy trong dự án này. Bộ sinh đối chiếu SHA-256 của bản tham chiếu với `stock_spec.json`.
Kiểm tra này phát hiện bản tham chiếu bị thay đổi, **không theo dõi các thay đổi mới của website bên ngoài**.
Muốn đối chiếu web phiên bản mới phải chủ động cập nhật nguồn, hash, quy tắc và kiểm thử tương ứng. Không tắt kiểm tra hash để chạy cho qua.

## Chạy nhanh trên Windows

Cần Python 3.12+ và GCC/gcov cùng phiên bản. Runner chỉ dùng thư viện chuẩn Python.
Mở terminal ngay trong thư mục dự án:

```powershell
python -B test_generator.py
python -B stock_json_fuzz.py
```

Lệnh fuzz mặc định chạy hai chế độ black-box/coverage-guided, ba seed 1, 7, 42.
Mỗi chế độ/seed có tối đa 500 lượt và 120 giây, không phải tổng ngân sách của toàn bộ lệnh.
Kết quả được tạo riêng từng lượt trong `results/stock-json-<mã-lượt>/`; không ghi vào dự án web.

Chạy ngắn để kiểm tra môi trường:

```powershell
python -B stock_json_fuzz.py --iterations 50 --seeds 1 --seconds 30
```

Bộ khung nhị phân cũ vẫn dùng được với `python -B fuzz_runner.py --module stock`.
Bản độc lập không có ba module Voucher/Loyalty/Idempotency và không có runner HTTP/database.

## Compiler và GitHub

Bản sao trên máy này có GCC portable trong `toolchain/mingw64/`, giữ nguyên từ bộ công cụ đang dùng.
Thư mục compiler khoảng 916 MiB, chỉ dùng cục bộ và được loại khỏi GitHub bằng `.gitignore`.
Nếu lấy mã từ GitHub, hãy cài GCC/gcov hoặc đặt cùng cấu trúc portable trên máy nhận.
Runner ưu tiên portable của chính dự án; nếu không có thì tìm trên PATH. Không sử dụng compiler nằm trong dự án web.

Không đưa `toolchain/`, `results/`, môi trường Python, binary, .env hoặc dữ liệu web lên GitHub.
Không cần đưa toàn bộ web vào repository môn học. Chưa tự tạo repository, commit hoặc push.
Các file nguồn, Excel, nguồn Java tham chiếu và bằng chứng nhỏ trong `evidence/` có thể nộp cùng dự án.

## File C và Excel để nghiệm thu

- `stock_json_seclab.c`: mã C đầy đủ để nạp Ch2/Ch3/Ch4 của SecLabFramework. Chọn `stock_json` để fuzz chuỗi JSON thô; chọn `stock_json_case` để fuzz tham số số nguyên qua JSON hợp lệ về cú pháp.
- `stock_json_adapter.c`: parser/adapter, chưa phải mã C độc lập; cần ghép nghiệp vụ từ đặc tả bằng bộ sinh.
- `stock_spec.json`: quy tắc nghiệp vụ, hợp đồng JSON và hash nguồn Java tham chiếu.
- `generate_simulator.py`: sinh nghiệp vụ reserve/settle từ rules; adapter parser được viết riêng, không tuyên bố mọi dòng C đều sinh tự động.
- `stock_json_fuzz.py`: oracle độc lập, hồi quy, hai chế độ fuzz, thu gcov và dữ liệu Excel hiện tại.
- `test_generator.py`: kiểm tra bộ sinh, hành vi C, thư viện, truy vết và các đường cấp phát/giải phóng.
- `badminton_spec.xlsx`: 10 sheet, 12 yêu cầu và 55 test case tài liệu hóa cho riêng tồn kho, dùng nạp Ch6.
- `evidence/`: bằng chứng lịch sử của lượt chạy trước khi tách; không được gọi nó là kết quả chạy tại thư mục mới.

Sinh lại file C nộp sau khi đổi đặc tả hoặc adapter:

```powershell
python -B generate_simulator.py --json --library --output stock_json_seclab.c
```

Excel không tự cập nhật sau fuzz. `python -B stock_json_fuzz.py --print-spec` chỉ xuất dữ liệu 10 sheet dưới dạng JSON.
Các hàm cộng Ch6 là minh họa, không phải toàn bộ parser C. Muốn kiểm tra mã đầy đủ phải nạp C trực tiếp vào các tab tương ứng.

Sau khi lưu và tự đóng ứng dụng cũ, mở lại với PATH compiler chỉ trong tiến trình con:

```powershell
python -B stock_json_fuzz.py --open-lab
```

Mặc định tìm SecLabFramework.exe trong Downloads của người dùng hiện tại. Có thể chỉ định `--lab-exe "D:\\CongCu\\SecLabFramework.exe"`.
Lệnh không tự đóng cửa sổ cũ, không sửa PATH hệ thống, không tự nạp mã hoặc chứng minh chiến dịch GUI đã chạy.

## Hợp đồng JSON

### Chạy nghiệp vụ trong SecLabFramework

Khi công cụ sinh chuỗi ngẫu nhiên chỉ trả mã 100, nạp lại `stock_json_seclab.c` và chọn
`int stock_json_case(int available, int reserved, int quantity, int action)`.
Hàm này tạo JSON một record, đặt kho biến thể bằng kho tổng rồi gọi đúng `stock_json`;
không bỏ qua parser, cấp phát hoặc các quy tắc nghiệp vụ. Nó không thay thế fuzz JSON thô.

Các đầu vào đối chiếu: `(10,0,2,0)` giữ hàng → 0; `(0,0,1,0)` thiếu kho → 2;
`(10,2147483647,1,0)` tràn giữ chỗ → 3; `(10,0,0,0)` số lượng sai → 103;
`(10,0,2,5)` hủy lặp → 0; `(10,0,2,6)` tất toán lặp → 0;
`(10,0,2,8)` giữ biến thể → 0. Trả 0 chưa tự chứng minh trạng thái cuối đúng;
runner JSON riêng đối chiếu thêm các trường trạng thái bằng oracle độc lập.

Chỉ chọn hàm công khai cần thử, không chọn các helper nhận con trỏ cấu trúc.
Sau khi sửa mã phải nạp lại và biên dịch lại trong ứng dụng, không dùng DLL cũ.
Nếu dùng concolic, kiểm tra log có dịch được hàm hay chỉ dùng từ điển; tham số số nguyên
không bảo đảm công cụ dịch được `snprintf` và chuỗi lời gọi C sang SMT.
Coverage riêng hàm đầu vào không phải coverage toàn bộ parser/nghiệp vụ.
Lượt GUI cũ: 285 input, giữ 5 test chuỗi sai, không phát hiện crash; chưa xác nhận GUI chạy hàm mới.

### Điểm kiểm tra thuần số nguyên cho SMT

`stock_reserve_guard(available, reserved, quantity, variant, variant_available, variant_reserved)`
được sinh từ phần điều kiện trả về trước khi cập nhật trạng thái của `operations.reserve`.
Hàm không có mảng, con trỏ, macro kiểu số hoặc lời gọi hàm, nhằm tránh giới hạn dịch SMT đã gặp.
Chưa coi SMT trong ứng dụng là thành công cho đến khi log thực tế xác nhận không dùng fallback.
Lượt thử guard đầu tiên báo Z3 Sort mismatch Int/Bool và dùng fallback. Bộ sinh đã được sửa
để biểu diễn điều kiện số nguyên tường minh, ví dụ `(variant != 0) && (...)`, kể cả trong phủ định.
Thay đổi này giữ nguyên cách C hiểu 0/khác 0; vẫn cần chạy lại ứng dụng để xác nhận bộ dịch SMT chấp nhận.

Phạm vi: sáu tham số int32, kiểm tra điều kiện trực tiếp của reserve; các trạng thái kho thử độc lập
không bắt buộc thỏa quan hệ kho tổng/biến thể của fixture JSON. Không thay thế parser, kiểm tra
trạng thái ban đầu của JSON, phép cập nhật kho, hủy/tất toán hoặc kiểm tra bộ nhớ.
Mã 0 nghĩa là qua các điều kiện giữ hàng, KHÔNG có nghĩa đã thực hiện giữ hàng.
Mã 1: quantity ngoài miền; 2: thiếu kho tổng; 3: tràn giữ chỗ tổng;
4: thiếu kho biến thể; 5: tràn giữ chỗ biến thể. Không đồng nhất mã 1 của guard với mã 103 của JSON.

Phép kiểm tra `reserved + q > INT_MAX` được sinh thành `reserved > INT_MAX - quantity`;
chỉ thực hiện sau guard quantity từ 1 đến giới hạn dương để phép trừ không tràn int32.
Bộ sinh từ chối thay đổi đặc tả không còn bảo đảm điều kiện này hoặc xen return sau cập nhật trạng thái.

Nạp lại `stock_json_seclab.c`, chọn riêng `stock_reserve_guard`, biên dịch rồi sinh test
với Concolic/white-box. Giữ Không dùng sanitizer khi ứng dụng nhận GCC cũ.
Lưu log để xác nhận SMT thật sự dịch được hàm, mô hình tạo ra nằm trong int32 và có thực thi C.
Không dùng coverage hàm guard để đại diện cho toàn bộ simulator.
Kiểm tra tương đương đã chạy 10.006 bộ tham số giữa guard và reserve gốc, gồm đủ mã 0–5.
Test sửa đặc tả giới hạn quantity từ 100 xuống 50 xác nhận guard thay đổi hành vi tương ứng.
Sau bổ sung, 27 nhóm kiểm tra đạt; lượt JSON ngắn mới chạy 100 input, 41 hồi quy và 40 ca DLL
không ghi nhận bất thường: `results/stock-json-20261018-090441-6ab9bafb/summary.json`.
Đây chưa phải bằng chứng ứng dụng thầy đã giải được SMT cho hàm mới.

### Đối chiếu lượt GUI 1.258 input

Lượt `stock_json_case` do người dùng chạy giữ 15 test, không ghi nhận crash, coverage riêng hàm 75%.
Log xác nhận SMT lỗi `CTranslateError` do mảng/con trỏ và chuyển sang từ điển hằng số + biên.
Không ghi lượt này là giải ràng buộc SMT thành công. 15 mã trả về đã được chạy lại bằng C và
đối chiếu oracle độc lập trong `test_gui_cases_match_independent_oracle`; không có nghĩa GUI đã
kiểm tra các trường trạng thái cuối. Test xuất ở chế độ characterization cần giữ đúng nhãn này.

```json
{"available":10,"reserved":0,"variant_available":10,"variant_reserved":0,"action":0,"items":[{"quantity":2}]}
```

Sáu trường gốc bắt buộc. Mỗi record chỉ có quantity; khóa thiếu/lạ/trùng hoặc sai kiểu bị từ chối.
Các số phải biểu diễn chính xác int32: 2.0 và 20e-1 được nhận; 1.5, true, chuỗi "2", null hoặc ngoài int32 bị từ chối.
Có 1–100 record, mỗi quantity từ 1–100 và tổng số lượng cùng sản phẩm không quá 100.
Giới hạn riêng của adapter là 16.384 byte đầu vào và 64 byte/token số; không khẳng định backend có cùng giới hạn HTTP.

Action là mã fixture 0–15: bit 8 bật biến thể, hai bit thấp 0 giữ/1 hoàn/2 hoặc 3 tất toán, bit 4 lặp thao tác hoàn hoặc tất toán.
Không đánh đồng nó với enum trạng thái API. NUL nhúng được kiểm tra qua CLI đọc file có độ dài;
wrapper ctypes.c_char_p chỉ truyền chuỗi đến NUL đầu tiên.

Parser không đệ quy, calloc 100 phần tử int32_t, kiểm tra NULL, không ghi ngoài 100 phần tử và free sau cấp phát thành công.
Test riêng tiêm thất bại cấp phát và kiểm tra bộ đếm khối sống về 0; đây không phải bằng chứng sanitizer không phát hiện leak/UAF.
GCC portable hiện thiếu libasan và libubsan. Không tự kết luận chương trình hết lỗi khi các lượt fuzz PASS.

### Kiểm tra ASan và UBSan riêng

Khi đã giải nén bộ LLVM-MinGW UCRT được xác minh checksum vào
`toolchain/llvm-mingw-20261006-ucrt-x86_64/`, chạy:

```powershell
python -B stock_json_fuzz.py --sanitizer
```

Lệnh biên dịch riêng với ASan+UBSan, chạy 41 ca hồi quy và đột biến JSON từ seed,
đối chiếu toàn bộ trạng thái với oracle. Kết quả nằm trong `results/sanitizer-<mã-lượt>/`.
Không gọi đây là coverage-guided và không gộp số liệu coverage GCC vào lượt sanitizer.
Runner chỉ đặt PATH và tùy chọn sanitizer trong tiến trình đang chạy, không sửa PATH hệ thống.
LeakSanitizer bị tắt trên Windows: kết quả sạch ASan/UBSan không chứng minh không rò rỉ bộ nhớ.
Test đối chứng dùng chương trình lỗi mẫu riêng trong results; phát hiện ở đó không phải lỗi của web hoặc simulator.
Compiler vẫn là công cụ cục bộ, không nộp thư mục toolchain lên GitHub.

## Cập nhật đầu vào nghiệm thu — 18/10/2026

Đã thêm `stock_json_case` để công cụ nhận tham số số nguyên rồi tạo JSON và gọi parser hiện có.
Hàm này được kiểm tra trên 523 bộ tham số với oracle độc lập; một test khác xác nhận sửa quy tắc
trong đặc tả làm thay đổi hành vi của hàm nghiệm thu. Không sửa mã nguồn web.
Tại mốc bổ sung sanitizer, bộ kiểm tra có 22 nhóm đạt, gồm đối chứng ASan phát hiện use-after-free và UBSan phát hiện
tràn số có dấu trong hai chương trình lỗi mẫu riêng. Log đối chứng được lưu dưới
`results/generator-tests-d8c6c44a/use-after-free/diagnostic.log` và `overflow/diagnostic.log`.
Chiến dịch JSON `results/stock-json-20261018-083428-95703d48/summary.json` chạy đủ 3.000 lượt,
41 ca hồi quy và 40 ca qua DLL, không ghi nhận crash, timeout, vi phạm bất biến hoặc lệch oracle.
Mã nguồn đúng mốc chạy được lưu trong thư mục kết quả; không đồng nhất với các sửa đổi runner về sau.
Chiến dịch `results/sanitizer-20261018-084125-187616c4/summary.json` chạy 41 ca hồi quy và
1.384 lượt với ASan+UBSan: seed 1 chạy 423, seed 7 chạy 461 (đạt giới hạn 120 giây),
seed 42 chạy đủ 500. Không ghi nhận lỗi sanitizer, crash, timeout, vi phạm bất biến hoặc lệch oracle.
Lượt này không đo coverage và không chạy LeakSanitizer; không kết luận chương trình hết lỗi.
Compiler tải từ bản phát hành chính thức https://github.com/mstorsjo/llvm-mingw/releases/tag/20261006,
gói `llvm-mingw-20261006-ucrt-x86_64.zip`, SHA-256
`317492c456aa27ee607a5919f1d2d38dcdc1112516a24d0bf4b00d078f52d17a`.
Nghiệm thu GUI hàm mới, cập nhật Excel và báo cáo nộp cuối cùng vẫn còn cần hoàn thiện.

## Kiểm chứng sau khi tách — 17/10/2026

- 18 nhóm kiểm tra đạt, gồm đường dẫn độc lập và file C nộp khớp bộ sinh. Log: `results/standalone-tests.log`.
- Chiến dịch JSON `results/stock-json-20261017-233702-ae300fd0/summary.json`: 3.000 lượt, 41 hồi quy C,
  40 ca qua thư viện, không ghi nhận crash/timeout/vi phạm bất biến/lệch oracle trong ngân sách đã chạy.
- Bộ fuzz nhị phân cũ chạy từ ngoài thư mục dự án: 25 hồi quy và 80 lượt thử đều đạt.
- Compiler thực tế nằm trong toolchain của bản độc lập; nguồn tham chiếu không đọc từ website bên ngoài.
- Dữ liệu kiểm tra `.gitignore` nằm trong results, không tạo repository Git tại gốc dự án và chưa commit/push.

Các kiểm tra này không thay thế nghiệm thu GUI hoặc sanitizer; các giới hạn bên dưới vẫn còn áp dụng.

## Bằng chứng và tình trạng nghiệm thu

`evidence/summary.json` ghi 3.000 lượt fuzz JSON trước khi tách, 41 hồi quy C và 40 ca qua thư viện.
Không ghi nhận bất thường trong ngân sách đó. `evidence/metadata.json` và `evidence/source_snapshot/`
lưu mốc mã nguồn/hashes cũ; đường dẫn web trong bằng chứng lịch sử không phải phụ thuộc chạy của bản độc lập.
`evidence/verification-tests.log` là log kiểm tra tại dự án gốc, không thay thế log kiểm tra độc lập mới.
Kết quả sau khi tách nằm trong `results/`, được phân biệt với bằng chứng lịch sử.

Ứng dụng đã chạy chiến dịch hàm `stock_json` trên 285 input và giữ 5 test chuỗi sai;
chưa xác nhận nghiệm thu nghiệp vụ qua hàm mới `stock_json_case` trong GUI.
Các lần đọc cửa sổ và thử CLI trước đây bị timeout. Excel khai báo 49 test case không có nghĩa GUI đã thực thi PASS 49 ca.
Không tự gán CVE cho website từ ví dụ minh họa. Báo cáo PDF chưa cập nhật cho luồng JSON nên không sao chép bản cũ làm báo cáo nộp.


## Tổng hợp báo cáo ngày 18/10/2026

Báo cáo `Bao_cao_An_toan_phan_mem.pdf` đã tổng hợp đủ 8 phần theo mẫu. Đây là bản đối chiếu bằng chứng hiện có, chưa xác nhận hoàn tất mọi yêu cầu nộp bài.

Excel chính đã bổ sung 6 test TC-SMT1–6 và 5 ghi chú phạm vi trong ThongTin; giữ nguyên dữ liệu cũ. Tổng cộng 55 test tài liệu hóa không có nghĩa GUI đã thực thi 55 ca. Bản trước cập nhật còn tại `results/report-final/badminton_spec.before.xlsx`.

Log người dùng cung cấp xác nhận guard chạy 60 input, giữ 6 test, phủ 22/22 probe riêng guard; lượt cuối không báo fallback. Gói pytest đã chạy lại 6/6 PASS tại `results/pytest-stock-guard.xml`. Các ghi chú GUI chưa hoàn tất ở mục lịch sử phía trên mô tả các mốc cũ.

Mốc tổng hợp: `results/report-final/pytest-combined.log` ghi 34 test và 10.549 subtest đạt. Lượt JSON mới `results/stock-json-20261018-093532-9d53d681` chạy 200 input, 41 hồi quy và 40 ca DLL; lượt sanitizer mới `results/sanitizer-20261018-093549-a35b9b72` chạy 100 input và 41 hồi quy. Không cộng các lượt khác phiên bản thành một chiến dịch.

Còn thiếu tại mốc dựng PDF: so sánh định lượng black-box/SMT cùng mục tiêu/nhánh; LeakSanitizer; bằng chứng v0/v1 nếu yêu cầu before/after áp dụng; thông tin nhóm và tên đề tài đăng ký. Phép so sánh đã bổ sung ở mục dưới, chưa đưa vào PDF/Excel. Không dùng chương trình lỗi mẫu để tuyên bố simulator hoặc website có lỗi. Không tự gán CVE.

Nghiệm thu: mở PDF kiểm tra thông tin nhóm; nạp Excel chính vào Ch6; nạp lại C vào GUI và chọn đúng hàm; giữ log đầy đủ, mã snapshot và kết quả từng lượt. Không sửa code web trong đợt hoàn thiện tài liệu này.

## So sánh cùng nhánh C — bổ sung ngày 18/10/2026

Chạy tại thư mục dự án độc lập, dùng Python riêng đã có Z3:

```powershell
.\.venv\Scripts\python.exe -B compare_fuzz.py
```

Phụ thuộc bổ sung trong `.venv`: `z3-solver==5.3.1.0`. Máy mới cần cài phụ thuộc này trước.
Không cần khởi chạy website hoặc ứng dụng của thầy. Công cụ tự biên dịch bản C hiện tại,
kiểm tra khớp bộ sinh, rồi lưu `target.c`, DLL, log biên dịch và `summary.json`
trong `results/comparison-<mã-lượt>/`. Không ghi đè C nộp hoặc gọi HTTP/DB/PayOS.

Mục tiêu duy nhất: `stock_reserve_guard` trả mã 3, tức từ chối khi `reserved + quantity > INT_MAX`,
sau khi đã vượt qua kiểm tra số lượng và đủ kho. Đây là nhánh phòng ngừa tràn, không phải phát hiện crash/lỗ hổng.
SMT dịch điều kiện từ đặc tả và phủ định các guard đứng trước; không chép sẵn nghiệm.
Đây là giải đường đi bằng SMT, không phải tự triển khai concolic đầy đủ hoặc chạy lại chiến dịch GUI.
Mọi nghiệm được gọi trên cùng DLL C và đối chiếu lại điều kiện đặc tả.

Cùng miền dữ liệu cho các phương pháp: kho/giữ/biến thể thuộc 0..INT_MAX,
quantity thuộc 1..100, variant thuộc 0..1. Đây là miền guard, không áp đặt tổng kho bằng kho biến thể
như fixture JSON. Trong miền này mã 1 không thể đạt; đối chứng xác nhận UNSAT cho mã 1,
SAT và chạy C khớp cho các mã 0, 2, 3, 4, 5. Không suy rộng sang toàn bộ parser/website.

Lượt thành công: `results/comparison-20261018-110108-14dd28b3/summary.json`.
Seed 1, 7, 42, 101, 2026; tối đa 50.000 lần gọi C mỗi phương pháp/seed;
SMT giới hạn solve 5 giây. SMT không cần dùng hết ngân sách C.

| Phương pháp | Số lượt tìm được/5 seed | Lần gọi C tới nhánh | Thời gian |
|---|---:|---|---|
| Black-box ngẫu nhiên đều | 0/5 | Hết 50.000/seed, chưa thấy | Khoảng 0,82–1,00 giây/seed |
| Black-box ưu tiên biên | 5/5 | Lần lượt 32, 2, 4, 16, 21 | Dưới 1 mili giây/seed trên máy thử |
| SMT giải đường đi | 5/5 | 1/seed để xác nhận nghiệm C | Khoảng 10 mili giây/seed; xem số chính xác trong JSON |

Ưu tiên biên: mỗi trường có xác suất 20% lấy một giá trị ở đầu/cuối miền, 80% lấy ngẫu nhiên đều;
không kiểm tra điều kiện nhánh khi sinh dữ liệu. Hai chiến lược có cùng miền nhưng khác phân phối.
Không kết luận SMT luôn nhanh hơn: ở đây chiến lược biên nhanh hơn về thời gian, SMT ít lần gọi C hơn.
Không tính tỷ lệ tăng tốc từ lượt ngẫu nhiên đều chưa tìm được; đây là kết quả bị giới hạn ngân sách.
Thời gian không gồm biên dịch, nạp Z3 và chạy đối chứng; SMT có tính tạo ràng buộc, giải và xác nhận C.
Các lượt chạy ngắn chịu ảnh hưởng nhiễu đo; không dùng chúng làm benchmark hiệu năng tổng quát.

Kiểm tra sau bổ sung: 38 test và 10.555 subtest đạt; gồm bốn test mới về dịch đường đi,
theo dõi thay đổi đặc tả, sampling tái lập/đúng miền và đếm lần thử khi trúng/hết ngân sách.
Thư mục comparison trước đó còn được giữ: phép chạy đã lưu JSON nhưng bước in terminal lỗi mã hóa;
không dùng lượt đó làm mốc thành công. Bản sửa đặt UTF-8 cho stdout, không sửa nghiệp vụ C.

Phép so sánh bổ sung một bằng chứng cùng nhánh; không thay thế yêu cầu magic/checksum nếu tên đề tài
đăng ký bắt buộc nội dung này. PDF và Excel hiện tại chưa cập nhật số liệu bổ sung này.
LeakSanitizer, thông tin nhóm và bằng chứng v0/v1 nếu thầy yêu cầu vẫn cần đối chiếu riêng.

## Bằng chứng Ch1–Ch3 độc lập — 18/10/2026

Thư mục `results/ch123-20261018-202400-9a09dbce/` lưu bản sao đầu vào, log gốc,
câu lệnh tái lập và kết quả đối chiếu. Đây là công cụ dòng lệnh độc lập, không phải log xuất từ SecLabFramework.
Không sửa nghiệp vụ C hoặc code web trong lượt này. PDF/Excel chưa cập nhật các kết quả mới này.

- Đối chiếu đầu vào: 10 sheet Excel khớp bộ xuất hiện tại, có 12 yêu cầu và 55 ca tài liệu hóa;
  C khớp bộ sinh. Các hash được ghi tại `ch1-model-check.json`.
- Ch1: kiểm tra điểm bất động trên đồ thị 5 trạng thái; không deadlock. Từ `ready`,
  `EF(reserved)`, `EF(cancelled)`, `EF(settled)` và `AG(!(cancelled & settled))` đều đúng.
  Đối chứng bỏ cạnh `reserved -> cancelled` làm `cancelled` không còn tới được từ trạng thái đầu.
  Đây là mô hình nhãn khai báo, không chứng minh các giá trị kho hoặc bộ nhớ trong C.
- Ch2: GCC 16.2 với `-fanalyzer -Wall -Wextra -Werror -Wno-unused-function`, chế độ sinh assembly
  vào thiết bị NUL, hoàn tất mã 0 và không phát cảnh báo. Lượt này không chạy sanitizer hoặc LeakSanitizer.
  Không coi kết quả sạch cảnh báo là chứng minh không có lỗi.
- Ch3: Clang 23.1.3 xuất AST đầy đủ và CFG; xác định 25 định nghĩa hàm trong nguồn C.
  CFG riêng `stock_reserve_guard` có 16 khối kể cả ENTRY/EXIT, 23 cạnh;
  McCabe theo `E-N+2` là 9, có tính các nhánh short-circuit. Không so trực tiếp với 22 probe của GUI.
- Điều kiện guard được đọc từ AST Clang, dịch sang Z3 5.3.1 và giải trên miền sáu tham số int32 có dấu.
  Cả sáu đường trả mã 0–5 đều SAT; chạy lại từng nghiệm trên DLL C từ cùng bản sao nguồn,
  đối chiếu đặc tả độc lập, kết quả đều khớp. Khác miền benchmark so sánh (quantity 1–100),
  miền Ch3 này có quantity ngoài khoảng nên nhánh trả 1 đạt được.
- Truy vấn `reserved + quantity` vượt int32 sau khi đã vượt ba kiểm tra đầu của guard trả UNSAT.
  Chứng minh chỉ áp dụng phép cộng với tiền điều kiện này; không phải BMC hoặc chứng minh toàn parser an toàn.

Các file chính: `ch1-model-check.json`, `compiler-analysis.json`,
`ch3-clang-ast.stdout.log`, `ch3-clang-cfg.stderr.log`, `ch3-ast-smt-check.json`, `executed-commands.json`.
AST có cả khai báo header hệ thống nên dung lượng lớn hơn mã C; giữ để truy vết, không cần in nguyên AST vào báo cáo.

Còn thao tác trên ứng dụng thầy: nạp Excel hiện tại để kiểm tra mô hình/CTL bằng chức năng đọc đặc tả,
nạp toàn bộ `stock_json_seclab.c` vào Ch2, rồi phân tích guard ở Ch3. Cần lưu log/ảnh thực tế;
không điền trạng thái GUI PASS từ các kết quả dòng lệnh ở trên. Không yêu cầu chạy BMC nếu công cụ
không hỗ trợ bài toán; phải ghi đúng giới hạn. Khi có bằng chứng GUI mới cập nhật tài liệu nộp cuối.

## Chốt bằng chứng Ch2 trong phạm vi đã kiểm tra — 18/10/2026

Đọc bản đối chiếu tại `results/ch123-20261018-202400-9a09dbce/ch2-assessment.md`;
`ch2-verification.json` kiểm tra số liệu và hash đầu vào. Mã nghiệp vụ C và code web không đổi.

- Đã lưu hai ảnh GUI người dùng cung cấp. GUI không nhận diện struct; compiler thực xác nhận
  Input 24/align 4, Stock 24/align 4, JsonReader 24/align 8, JsonFixture 40/align 8 byte trên Windows x64.
- Cảnh báo leak dòng 263 là cảnh báo giả sau đối chiếu free dòng 267 và luồng trả về;
  không ghi là tìm được/vá lỗi CWE-401 của sản phẩm. Giới hạn nhận diện con trỏ thành viên là giả thuyết,
  không tuyên bố đã xác minh mã heuristic của ứng dụng.
- Bốn nhóm kiểm tra mới chạy lại đều đạt, không bỏ qua: cấp phát thất bại, cân bằng cấp phát,
  hồi quy JSON CLI/DLL và đối chứng lỗi ASan/UBSan. Log tại `ch2-memory-tests.log`.
- Lượt `sanitizer-20261018-212014-2669991f/` bên trong thư mục ch123: 41 hồi quy,
  100 lượt đột biến seed 1, không ghi nhận lỗi trong ngân sách thử. Không đo coverage, không chạy LeakSanitizer.
- Phần thực nghiệm và đối chiếu Ch2 nêu trên đã hoàn tất. Nếu thầy bắt buộc log LeakSanitizer,
  yêu cầu này vẫn chưa được đáp ứng; không đổi nó thành PASS. PDF chính chưa cập nhật bằng chứng GUI/Ch2 mới.

Chưa chuyển sang thao tác Ch3; chờ Phong xem kết luận Ch2. Không cần sửa mã sản phẩm chỉ để làm mất cảnh báo GUI.

## Bổ sung nghiệm thu GUI Ch3 — 18/10/2026

Sau mốc chốt Ch2, Phong đã chạy Ch3 trên ứng dụng và cung cấp ảnh kết quả.
Các ảnh gốc được lưu với tiền tố `ch3-gui-` tại `results/ch123-20261018-202400-9a09dbce/`.

- Trích xuất AST: GUI liệt kê các hàm/điều kiện của toàn mã và báo McCabe ước lượng 162,
  độ sâu lồng nhau 3, khoảng 206 câu lệnh. Không dùng 162 làm độ phức tạp riêng guard hoặc số lỗi.
- CFG riêng `stock_reserve_guard`: GUI báo 18 khối, 22 cạnh, McCabe khoảng 6;
  lượt vẽ ban đầu ghi 9/11 khối được phủ qua wrap. Cách dựng và đếm khác log Clang,
  đặc biệt việc tách short-circuit và khối JOIN; không coi hai bộ số đo là cùng chỉ số.
- Ảnh SAT cho thấy nghiệm `available=1, r=2147483647, q=1`: đầu vào cần từ chối do nguy cơ tràn giữ chỗ.
- Ảnh UNSAT xác nhận truy vấn sau khi thêm điều kiện `r <= 2147483647 - q` và vẫn yêu cầu
  `r + q > 2147483647` không có nghiệm. Đây là kiểm tra công thức nhập riêng, không tự động chứng minh toàn C.
- Sinh test trên guard: GUI ghi thực chạy 60 input, giữ 6 test, không lỗi/crash,
  phủ 22/22 probe của riêng guard. Không thấy thông báo fallback trong ảnh lượt cuối.
  Không ghi 500 lượt thực chạy chỉ vì ô ngân sách là 500; không đồng nhất 22/22 probe với toàn parser.
- Phong xuất lại gói vào thư mục gốc, cập nhật gói đã có. Đã lưu snapshot tiền tố `ch3-export-`,
  chạy lại đúng file pytest vừa xuất: 6/6 đạt trong 1,65 giây, không lỗi hoặc bỏ qua.
  Sáu đầu vào được đối chiếu thêm với đặc tả độc lập, bao phủ đủ mã trả về 0–5.
  `sl_target.c` khớp C sinh hiện tại nếu bỏ qua dòng trống; không sửa gói xuất để làm test đạt.

Bằng chứng mới: `ch3-export-pytest.xml`, `ch3-export-pytest.log`, `ch3-export-verification.json`.
Gói vẫn là characterization: chỉ các đầu vào được kiểm tra và phạm vi guard có kết luận tương ứng.
Chưa chạy BMC cho nghiệp vụ; không chạy ví dụ vòng lặp mẫu rồi ghi là bằng chứng của tồn kho.
Phần AST/CFG/SMT và chạy lại test Ch3 đã có bằng chứng; PDF chính chưa cập nhật các mốc mới này.

## Bổ sung kiểm tra leak chuyên dụng — 18/10/2026

Đã dùng Dr. Memory 2.6.0 portable để bổ sung kiểm tra leak trên Windows.
Đọc `results/leak-20261018-225714-fe111d0d/leak-assessment.md` và `leak-summary.json`.
Các ghi chú “chưa có công cụ dò leak chuyên dụng” ở mốc trước không còn mô tả đầy đủ trạng thái hiện tại;
LeakSanitizer riêng vẫn chưa chạy và không được đổi tên công cụ trong báo cáo.

- Đối chứng bỏ quên malloc 123 byte: công cụ phát hiện đúng 123 byte leak xác định.
- Cùng đối chứng nhưng free đúng: không có leak xác định.
- Simulator chạy 141 đầu vào (41 hồi quy, 100 đột biến seed 1), lặp 10 vòng: đủ 1.410 lượt,
  kết quả khớp oracle và không có leak xác định được báo ở phần ứng dụng.
- Có một potential possible leak 24 byte trong loader/TLS của ntdll, cùng stack ở đối chứng sạch
  và simulator. Giữ toàn bộ cảnh báo và mặc định lọc hệ thống; không khẳng định đã loại trừ tuyệt đối lỗi hệ thống.
- Không sửa nghiệp vụ C, không sửa web, không cài WSL, không sửa PATH hệ thống.
  Compiler, công cụ và cache chỉ phục vụ thử nghiệm; không nộp toolchain lên GitHub.

Kết luận chỉ áp dụng workload đã chạy, không phải “không còn leak với mọi đầu vào”.
Nếu thầy bắt buộc LeakSanitizer cụ thể thì vẫn cần môi trường hỗ trợ; Dr. Memory là bằng chứng công cụ tương đương,
không phải log LeakSanitizer. PDF/Excel chính chưa cập nhật kết quả này. Ch5–Ch6 tiếp tục tạm gác theo yêu cầu Phong.

## Cập nhật báo cáo và rà Excel ngày 20/10/2026

Mục này thay thế trạng thái “PDF/Excel chưa cập nhật” ở các ghi chú lịch sử phía trên.
Báo cáo chính đã cập nhật 16 trang, đủ 8 phần: Ch1 CTL, Ch2 kiểu/size/record/cấp phát,
Ch3 AST/CFG/SAT/UNSAT và gói GUI, Ch4 các chiến dịch JSON, so sánh cùng nhánh và kiểm tra leak.
Thông tin nhóm, tên đề tài đăng ký, mã học phần và phân công vẫn chờ xác nhận; Ch5–Ch6 tạm gác.

Excel vẫn có 10 sheet, 12 yêu cầu và 55 ca tài liệu hóa; chỉ cập nhật ThongTin!B13:B18,
ThongTin!A18 và TestCase!F51. Giữ nguyên đầu vào các ca: TC-SMT1 cũ có quantity=101,
còn gói GUI Ch3 mới dùng quantity=0; cả hai trả 1 nhưng không phải cùng ca thực thi.
Các ghi chú cập nhật trong Excel là bản tổng hợp bằng chứng thủ công; sinh lại Excel từ
`stock_json_fuzz.py` có thể khôi phục ghi chú lịch sử, không nên ghi đè bản đã rà soát.

Số liệu mới: Ch3 GUI 60 input, 6 test, 22/22 probe riêng guard; pytest xuất GUI 6/6 PASS.
So sánh nhánh trả 3 trên 5 seed: uniform 0/5, edge-enriched 5/5, SMT trực tiếp 5/5.
Dr. Memory chạy 141 fixture ×10 vòng =1.410 lần gọi, 0 definite application leak;
potential possible leak 24 byte ntdll/TLS vẫn được giữ và ghi rõ, không tuyên bố đã xử lý triệt để.
LSan và BMC toàn mô hình chưa chạy; không tạo bằng chứng v0/v1 giả.

Bản trước cập nhật và ảnh kiểm tra nằm trong `results/report-final/`, hậu tố `before-20261020`
hoặc tiền tố `20261020-`. Biên bản đối chiếu: `results/report-final/update-audit-20261020.md`.
Chốt phiên bản là truy vết đúng mã bằng hash; kiểm tra bộ nộp là rà tính nhất quán và loại
phụ thuộc lớn/bí mật khỏi phạm vi nộp. Lần này chưa tạo ZIP, commit/tag hay nộp bài.
## Bổ sung ảnh thực vào báo cáo ngày 20/10/2026

Bản PDF có ảnh tại `results/report-final/Bao_cao_An_toan_phan_mem.images-20261020.pdf`
có 25 trang. PDF chính đang bị ứng dụng giữ mở, chưa thay được bản 16 trang.
Mục 6.10, trang 14–21 của bản có ảnh chứa 8 ảnh màn hình thật do Phong
cung cấp: Ch1 CTL; Ch2 nhận diện struct và cảnh báo leak; Ch3 AST, CFG, SAT, UNSAT,
sinh test concolic. Mỗi ảnh có toàn cảnh, vùng chi tiết phóng to và chú thích phạm vi.
Không dựng terminal giả, không đổi kết quả ảnh.

Mục 6.11, trang 22, ghi cụ thể ảnh còn cần bổ sung và vị trí chèn: Ch4 JSON, ASan/UBSan,
Dr. Memory đối chứng/simulator, pytest gói GUI và so sánh cùng nhánh. Có log thực không
đồng nghĩa đã có ảnh chụp màn hình của lượt chạy. Nếu chụp lúc xem lại log phải chú thích
đúng là ảnh xem lại log, không coi đó là ảnh thực thi mới.

Bản PDF 16 trang trước khi chèn ảnh nằm tại
`results/report-final/Bao_cao_An_toan_phan_mem.before-images-20261020.pdf`.
Excel, mã C và code web không thay đổi trong lần bổ sung ảnh này.

