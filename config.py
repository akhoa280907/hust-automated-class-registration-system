# =========================================================
# CẤU HÌNH CHUNG
# =========================================================

REGISTER_URL = (
    "https://qldt.hust.edu.vn/"
    "students/learn/class-registration"
)

# Các mã lớp xử lý theo đúng thứ tự.
CLASS_IDS = [
    "767562",
    "767633",
    "767516",
    "767658",
    "767463",
#    "",
#    "",
#    "",
#    "",
#    "",
#    "",
#    "",
]

DEFAULT_TIMEOUT = 15000
SEARCH_TIMEOUT = 60000


# =========================================================
# GỬI XÁC NHẬN SAU KHI HỦY
# =========================================================
#
# False:
#   Sau khi bot bấm Hủy -> Xác nhận cho các lớp Hết chỗ,
#   bot KHÔNG gọi f() để gửi thay đổi hủy.
#
# True:
#   Sau khi bot hủy xong tất cả lớp Hết chỗ,
#   bot gọi f() đúng 1 lần để gửi thay đổi hủy.
#
# Đây là công tắc DUY NHẤT cho phần gửi hủy.
# =========================================================

CONFIRM_CANCEL = True