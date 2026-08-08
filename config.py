# =========================================================
# HUST REGISTER CONFIG
# =========================================================

REGISTER_URL = (
    "https://qldt.hust.edu.vn/"
    "students/learn/class-registration"
)


# =========================================================
# KẾ HOẠCH ĐĂNG KÝ CHO register.py MỚI
# =========================================================
#
# "" = gửi đăng ký tại vị trí đó.
#
# Batch:
# PLAN = [
#     "767562",
#     "767516",
#     "767658",
# ]
#
# Sequential:
# PLAN = [
#     "767562",
#     "",
#     "767516",
#     "",
#     "767658",
# ]
#
# Hybrid:
# PLAN = [
#     "767562",
#     "767516",
#     "",
#     "767658",
# ]
#
# Nếu cuối PLAN còn lớp chưa gửi,
# register.py mới sẽ tự gửi lần cuối.
# =========================================================

SEND_MARKER = ""

PLAN = [
    "767562",
    "767516",
    "",
    "767658",
]


# =========================================================
# HẾT CHỖ THÌ HỦY
# =========================================================
#
# True:
#   Huỷ các lớp full (Có 2 mode)
#
# False:
#   Không huỷ các lớp full
# =========================================================

CANCEL_IF_FULL = True

# =========================================================

CLASS_IDS = [
    item
    for item in PLAN
    if item.strip() != SEND_MARKER
]

CONFIRM_CANCEL = CANCEL_IF_FULL


# =========================================================
# CÁCH HỦY
# =========================================================
#
# Chỉ có ý nghĩa khi có bật hủy.
#
# 1 = hủy ngay sau từng lần/nhóm gửi
# 2 = đăng ký hết vòng rồi mới hủy
# =========================================================

CANCEL_MODE = 1


# =========================================================
# RETRY
# =========================================================

RETRY_LOOP = True

# Tổng số vòng tối đa, tính cả vòng đầu tiên
LOOP_LIMIT = 2

# Nghỉ giữa các vòng retry, đơn vị giây
RETRY_DELAY = 1

# True:
#   THÀNH CÔNG         -> loại
#   HẾT CHỖ            -> hủy được thì retry
#   KHÔNG THÀNH CÔNG   -> retry
#   trạng thái khác    -> không tự retry
#
# False:
#   chỉ retry lớp Hết chỗ đã hủy
RETRY_FAILED_ONLY = True


# =========================================================
# KẾT QUẢ / LOG
# =========================================================

SHOW_SUMMARY = True

SAVE_LOG = True
LOG_FILE = "register.log"


# =========================================================
# AUTH / BROWSER
# =========================================================

AUTH_FILE = "auth.json"

HEADLESS = False


# =========================================================
# TIMEOUT
# Đơn vị: mili-giây
# =========================================================

DEFAULT_TIMEOUT = 15000
SEARCH_TIMEOUT = 60000
UI_TIMEOUT = 30000