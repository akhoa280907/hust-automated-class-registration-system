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
3.Thêm file account.py (Quan trọng)

File cần có 2 nội dung:

EMAIL = "YOUR_HUST_EMAIL" - Điền email đăng nhập

PASSWORD = "YOUR_PASSWORD" - Điền mật khẩu đăng nhập

Chạy 
python auth_manager.py --force --headed        (ép buộc tạo auth.json)

Khi chạy register.py thì auth.json luôn được tự động tạo

----------

4. Chạy project
Trong file config có

CLASS_IDS là điền mã lớp

CONFIRM_CANCEL là có huỷ lớp hết chỗ sau khi đăng khí hay không

Chạy file Python mong muốn bằng:

File chính (Khi chạy auth.json sẽ được tự động kiểm tra và tạo):

python register.py (Tự do chọn vị trí gửi đăng kí)

Các file phụ (Nếu auth.json hết hạn thì phải tạo lại)

python r1.py (Đăng kí hết mã lớp đã chọn rồi mới gửi đăng kí)

python r1c.py (Đăng kí hết mã lớp đã chọn rồi mới gửi đăng kí và huỷ các lớp hết chỗ sau khi hoàn thành gửi đăng kí toàn bộ)

python r2.py (Mỗi lần đăng kí mã lớp là 1 lần gửi đăng kí)

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
