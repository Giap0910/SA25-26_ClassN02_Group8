Phong, khi thầy yêu cầu chạy, hãy trình diễn **đúng phạm vi đã làm: Ch1–Ch4 và kiểm tra leak riêng**. Không cần mở frontend, backend hay MySQL.

## 1. Chạy kiểm thử bằng terminal

Mở PowerShell trong thư mục dự án:

```powershell
cd C:\Project\Badminton_Stock_Security
$py = ".\.venv\Scripts\python.exe"
```

Chạy **từng lệnh**, đợi xong và kiểm tra kết quả rồi mới chạy tiếp.

**Kiểm tra bộ sinh, nghiệp vụ, bộ nhớ và gói pytest:**

```powershell
& $py -X utf8 -B -m pytest -p no:cacheprovider test_generator.py test_stock_json_seclab_stock_reserve_guard_fuzz.py -q
```

Kết quả mong đợi: không có test thất bại. Lượt đã xác minh gần nhất là **38 test đạt**.

**Chạy fuzz JSON trên C:**

```powershell
& $py -X utf8 -B stock_json_fuzz.py
```

Runner tự sinh và biên dịch C, chạy hồi quy rồi chạy black-box/coverage-guided với ba seed. Kết quả lưu vào thư mục mới trong `results`.

**Chạy ASan/UBSan:**

```powershell
& $py -X utf8 -B stock_json_fuzz.py --sanitizer --iterations 100 --seeds 1 --seconds 60
```

Đọc số lượt **thực chạy** trong kết quả. Đây không phải kiểm tra leak bằng LeakSanitizer.

**So sánh black-box và SMT trên cùng nhánh:**

```powershell
& $py -X utf8 -B compare_fuzz.py
```

Giải thích với thầy: hai phương pháp cùng tìm tới nhánh từ chối tràn giữ chỗ, **không phải cố tạo crash**.

## 2. Mở ứng dụng thầy

Nếu ứng dụng đang mở, lưu kết quả và tự đóng cửa sổ cũ trước. Sau đó chạy:

```powershell
& $py -X utf8 -B stock_json_fuzz.py --open-lab
```

Lệnh này giúp ứng dụng tìm thấy GCC, nhưng **không tự chạy các chương**.

### Ch1 — Mô hình trạng thái

Nạp:

```text
C:\Project\Badminton_Stock_Security\stock_kripke.json
```

Kiểm tra lần lượt:

```text
EF(reserved)
EF(cancelled)
EF(settled)
AG(!(cancelled & settled))
```

Sau đó kiểm tra Mutual Exclusion với hai nhãn `cancelled` và `settled`.

### Ch2 — Bộ nhớ và phân tích tĩnh

Nạp:

```text
C:\Project\Badminton_Stock_Security\stock_json_seclab.c
```

Bấm:

1. **Phân tích Struct Alignment**.
2. **Quét lỗi con trỏ / memory leak**.

Nếu vẫn xuất hiện hai kết quả cũ, trình bày đúng:

- GUI chưa nhận diện struct; dùng số đo compiler trong bằng chứng Ch2.
- Cảnh báo leak dòng 263 đã được đối chiếu với `free` dòng 267; không gọi đây là lỗi đã vá.

### Ch3 — AST, CFG và SMT

Nạp cùng file C, rồi:

1. **Trích xuất AST**.
2. Nhập tên hàm `stock_reserve_guard` → **Vẽ CFG**.
3. Trong ô SAT, nhập điều kiện:

```text
available >= q and r >= 0 and r <= 2147483647 and q >= 1 and q <= 100 and r + q > 2147483647
```

Danh sách biến:

```text
available,r,q
```

Kỳ vọng **SAT**. Sau đó thêm điều kiện:

```text
and r <= 2147483647 - q
```

Kỳ vọng **UNSAT**. Đây là kiểm tra công thức với tiền điều kiện, không phải chứng minh toàn bộ chương trình an toàn.

### Ch4 — White-box sinh test

Nạp cùng file C:

- Chọn đúng hàm `stock_reserve_guard`, không chọn `java_add`.
- Chỉ tích **Concolic / white-box**.
- Chọn **Không dùng sanitizer** vì đã chạy riêng.
- Đặt ngân sách 500 → sinh test.

Lượt trước thực chạy **60 input**, giữ sáu test, phủ **22/22 probe riêng guard**. Lượt mới phải đọc kết quả thực tế và kiểm tra có fallback hay không.

## 3. Trình diễn lại kiểm tra leak

Để chạy lại **bộ thử leak đã chốt**, chuyển vào thư mục bằng chứng:

```powershell
cd C:\Project\Badminton_Stock_Security\results\leak-20261018-225714-fe111d0d
```

Chạy ba phép thử theo các câu lệnh đã lưu:

```powershell
foreach ($file in @("control-leak-run.json", "control-clean-run.json", "simulator-run.json")) {
    $job = Get-Content -Raw $file | ConvertFrom-Json
    $exe = $job.command[0]
    $toolArgs = @($job.command | Select-Object -Skip 1)
    & $exe @toolArgs > "replay-$file.stdout.log"
    Write-Host "$file : exit code $LASTEXITCODE"
}
```

Lệnh tạo log đầu ra mới; Dr. Memory cũng tạo thư mục báo cáo mới.

- Đối chứng có leak: dự kiến phát hiện **123 byte**, mã thoát **23 là chủ ý**.
- Đối chứng free đúng: dự kiến mã thoát 0.
- Simulator: kiểm tra 141 đầu vào lặp 10 vòng, tổng **1.410 lượt**.

Phải trình bày cả cảnh báo nghi ngờ 24 byte ở thư viện Windows nếu vẫn xuất hiện. Bộ này chạy binary đã chốt; nếu thay đổi mã C thì cần dựng lại trước khi dùng để kết luận cho phiên bản mới.

**Không chạy lần lượt mọi file `.py` một cách tùy ý.** Các lệnh trên là các điểm chạy chính; Ch5–Ch6 chưa nằm trong lượt trình diễn này vì Phong đang tạm gác hai chương đó.
