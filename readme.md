1. Cài Playwright
Chạy:

pip install playwright

Sau đó cài Chromium cho Playwright:

python -m playwright install chromium

-----------

2. Kiểm tra Playwright

Có thể kiểm tra bằng:

python -m playwright --version

Nếu hiện phiên bản Playwright thì đã cài thành công.

-----------
3. Tạo auth.json để lưu phiên bản đăng nhập (Nên để ý và tạo lại sau một thời gian)

Chạy:

python -m playwright codegen --target python --save-storage=auth.json https://qldt.hust.edu.vn/students

Đăng nhập xong thì tắt cửa sổ

----------

4. Chạy project
Trong file config có

CLASS_IDS là điền mã lớp

CONFIRM_CANCEL là có huỷ lớp hết chỗ sau khi đăng khí hay không

Chạy file Python mong muốn bằng:

python r1.py (Đăng kí hết mã lớp đã chọn rồi mới gửi đăng kí)

python r1c.py (Đăng kí hết mã lớp đã chọn rồi mới gửi đăng kí và huỷ các lớp hết chỗ sau khi hoàn thành gửi đăng kí toàn bộ)

python r2.c (Mỗi lần đăng kí mã lớp là 1 lần gửi đăng kí)

python r2c.py (Mỗi lần đăng kí mã lớp là 1 lần gửi đăng kí và huỷ hết lớp hết chỗ sau khi hoàn thành gửi đăng kí toàn bộ)

python registerclone.py (Mở nhiều tab cùng lúc và chạy song song để đăng kí tất cả mã lớp cùng lúc)

------------

Tùy chọn: dùng virtual environment

-Không bắt buộc, nhưng có thể tạo môi trường Python riêng: 

python -m venv .venv

-Kích hoạt trên Windows: 

.venv\Scripts\activate

Sau đó cài Playwright:

pip install playwright

python -m playwright install chromium
