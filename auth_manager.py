import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import (
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

# ============================================================
# HUST AUTH MANAGER
# VERSION: V6_ADFS_HOST_ONLY_ACCOUNT_FILE
# ============================================================

# Tài khoản được tách riêng sang account.py.
# account.py phải được thêm vào .gitignore.
from account import EMAIL, PASSWORD

BASE_URL = "https://qldt.hust.edu.vn/"
LOGIN_URL = "https://qldt.hust.edu.vn/students"
TIMETABLE_URL = "https://qldt.hust.edu.vn/students/learn/timetable"

ROOT_DIR = Path(__file__).resolve().parent
AUTH_FILE = ROOT_DIR / "auth.json"
PROFILE_DIR = ROOT_DIR / ".auth_profile"
ERROR_SCREENSHOT = ROOT_DIR / "auth_error.png"

DEFAULT_TIMEOUT = 30_000
LOGIN_TIMEOUT = 120_000
ADFS_HOST = "sso.hust.edu.vn"


class AuthManagerError(RuntimeError):
    pass


class HumanVerificationRequired(AuthManagerError):
    pass


def get_credentials() -> tuple[str, str]:
    email = EMAIL.strip()
    password = PASSWORD

    if (
        not email
        or email == "YOUR_HUST_EMAIL"
        or not password
        or password == "YOUR_PASSWORD"
    ):
        raise AuthManagerError(
            "Bạn chưa điền EMAIL và PASSWORD trong account.py."
        )

    return email, password


def _host(page: Page) -> str:
    try:
        return (urlparse(page.url).hostname or "").lower()
    except Exception:
        return ""


def _path(page: Page) -> str:
    try:
        return urlparse(page.url).path.lower()
    except Exception:
        return ""


def _is_visible(locator) -> bool:
    try:
        return locator.count() > 0 and locator.first.is_visible()
    except Exception:
        return False


def _log_page(step: str, page: Page) -> None:
    print(f"[{step}] URL: {page.url}")


def _safe_goto(
    page: Page,
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    label: str = "NAV",
) -> None:
    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=timeout,
        )
    except Exception as exc:
        if "ERR_ABORTED" not in str(exc):
            raise

        print(
            f"[{label}] Goto bị ERR_ABORTED; "
            "đợi redirect hiện tại hoàn tất..."
        )
        page.wait_for_timeout(1200)
        _log_page(f"{label}-AFTER-ABORT", page)


def _human_verification_message(page: Page) -> str | None:
    patterns = [
        r"Approve sign in request",
        r"Verify your identity",
        r"Enter code",
        r"Microsoft Authenticator",
        r"verification code",
        r"captcha",
        r"More information required",
    ]

    try:
        body = page.locator("body").inner_text(timeout=3000)
    except Exception:
        body = ""

    for pattern in patterns:
        if re.search(pattern, body, re.I):
            return pattern

    return None


# ============================================================
# AUTH CHECK
# ============================================================

def _looks_logged_in(page: Page) -> bool:
    return (
        _host(page) == "qldt.hust.edu.vn"
        and "/students/learn/timetable" in _path(page)
    )


def _goto_timetable_and_check(page: Page) -> bool:
    try:
        _safe_goto(
            page,
            TIMETABLE_URL,
            timeout=DEFAULT_TIMEOUT,
            label="CHECK",
        )

        page.wait_for_timeout(1500)
        _log_page("CHECK", page)

        return _looks_logged_in(page)

    except Exception as exc:
        print(f"[CHECK] Lỗi: {exc}")
        return False


def auth_is_valid(playwright) -> bool:
    if not AUTH_FILE.exists():
        print("[AUTH] Chưa có auth.json.")
        return False

    browser = None
    context = None

    try:
        browser = playwright.chromium.launch(headless=True)

        context = browser.new_context(
            storage_state=str(AUTH_FILE)
        )
        context.set_default_timeout(DEFAULT_TIMEOUT)

        page = context.new_page()
        return _goto_timetable_and_check(page)

    except Exception as exc:
        print(f"[AUTH] auth.json không sử dụng được: {exc}")
        return False

    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass

        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


# ============================================================
# QLDT / MICROSOFT
# ============================================================

def _find_login_button(page: Page):
    candidates = [
        page.get_by_role(
            "button",
            name=re.compile(r"^Đăng nhập$", re.I),
        ),
        page.get_by_text("Đăng nhập", exact=True),
        page.locator('button:has-text("Đăng nhập")'),
        page.locator('a:has-text("Đăng nhập")'),
    ]

    for locator in candidates:
        if _is_visible(locator):
            return locator.first

    return None


def _find_office365(page: Page):
    candidates = [
        page.get_by_role(
            "button",
            name=re.compile(r"Office\s*365|Office", re.I),
        ),
        page.get_by_text(
            re.compile(r"Office\s*365", re.I)
        ),
        page.locator('button:has-text("Office 365")'),
        page.locator('a:has-text("Office 365")'),
    ]

    for locator in candidates:
        if _is_visible(locator):
            return locator.first

    return None


def _find_email_box(page: Page):
    candidates = [
        page.get_by_role(
            "textbox",
            name=re.compile(
                r"Enter your email|email, phone|Email",
                re.I,
            ),
        ),
        page.locator('input[name="loginfmt"]'),
        page.locator('input[type="email"]'),
    ]

    for locator in candidates:
        if _is_visible(locator):
            return locator.first

    return None


def _wait_for_email_or_adfs(
    page: Page,
    timeout: int = LOGIN_TIMEOUT,
) -> str:
    end = time.monotonic() + timeout / 1000

    while time.monotonic() < end:
        human = _human_verification_message(page)
        if human:
            raise HumanVerificationRequired(
                f"Yêu cầu xác minh tương tác: {human}"
            )

        host = _host(page)

        if host == ADFS_HOST:
            return "adfs"

        if host == "qldt.hust.edu.vn" and _looks_logged_in(page):
            return "hust"

        email_box = _find_email_box(page)
        if email_box is not None:
            return "email"

        page.wait_for_timeout(200)

    raise PlaywrightTimeoutError(
        "Không thấy màn hình nhập email Microsoft "
        "hoặc HUST ADFS sau 120 giây.\n"
        f"URL cuối: {page.url}"
    )


def _click_next(page: Page) -> None:
    candidates = [
        page.get_by_role(
            "button",
            name=re.compile(r"^Next$", re.I),
        ),
        page.get_by_text("Next", exact=True),
        page.locator('input[type="submit"]'),
    ]

    for locator in candidates:
        if _is_visible(locator):
            locator.first.click()
            return

    raise AuthManagerError(
        "Không tìm thấy nút Next của Microsoft."
    )


# ============================================================
# HUST ADFS
# ============================================================

PASSWORD_SELECTORS = (
    "#passwordInput",
    'input[type="password"]',
    'input[name="Password"]',
    'input[name="password"]',
    'input[autocomplete="current-password"]',
)


def _find_password_in_frames(page: Page):
    """
    Trả về (frame, locator).
    Không phụ thuộc query string của URL ADFS.
    """
    for frame in page.frames:
        # CSS selector trước vì ADFS thường có input password chuẩn.
        for selector in PASSWORD_SELECTORS:
            try:
                locator = frame.locator(selector)

                for i in range(min(locator.count(), 10)):
                    item = locator.nth(i)
                    if item.is_visible():
                        return frame, item
            except Exception:
                pass

        # Fallback đúng theo Codegen trước đó.
        try:
            locator = frame.get_by_role(
                "textbox",
                name=re.compile(r"^Password$", re.I),
            )

            if locator.count() > 0 and locator.first.is_visible():
                return frame, locator.first
        except Exception:
            pass

    return None, None


def _wait_until_adfs_host(
    page: Page,
    timeout: int = LOGIN_TIMEOUT,
) -> None:
    """
    Chỉ kiểm tra hostname.
    client-request-id / wctx / query string có thay đổi cũng không ảnh hưởng.
    """
    end = time.monotonic() + timeout / 1000
    last_log = 0.0

    while time.monotonic() < end:
        human = _human_verification_message(page)
        if human:
            raise HumanVerificationRequired(
                f"Yêu cầu xác minh tương tác: {human}"
            )

        host = _host(page)

        if host == ADFS_HOST:
            print("[LOGIN] Đã chuyển sang host HUST ADFS.")
            _log_page("HUST-ADFS", page)
            return

        # Có thể SSO đã tự hoàn tất mà không cần password.
        if host == "qldt.hust.edu.vn" and _looks_logged_in(page):
            return

        now = time.monotonic()
        if now - last_log >= 5:
            print(
                "[LOGIN] Đang chờ redirect sang HUST ADFS... "
                f"host hiện tại = {host or '(trống)'}"
            )
            last_log = now

        page.wait_for_timeout(200)

    raise PlaywrightTimeoutError(
        "Sau khi bấm Next, quá 120 giây vẫn chưa "
        "chuyển sang host sso.hust.edu.vn.\n"
        f"URL cuối: {page.url}"
    )


def _wait_for_adfs_password(
    page: Page,
    timeout: int = LOGIN_TIMEOUT,
):
    """
    Khi đã ở sso.hust.edu.vn thì chỉ chờ ô password.
    Không xét query string.
    """
    end = time.monotonic() + timeout / 1000
    last_debug = 0.0

    while time.monotonic() < end:
        human = _human_verification_message(page)
        if human:
            raise HumanVerificationRequired(
                f"Yêu cầu xác minh tương tác: {human}"
            )

        # Nếu redirect tiếp sang QLĐT thì SSO đã tự hoàn tất.
        if _host(page) == "qldt.hust.edu.vn":
            return None, None

        frame, password_box = _find_password_in_frames(page)

        if password_box is not None:
            print("[LOGIN] Đã tìm thấy ô mật khẩu HUST ADFS.")
            return frame, password_box

        now = time.monotonic()

        if now - last_debug >= 5:
            input_count = 0

            try:
                for frame in page.frames:
                    input_count += frame.locator("input").count()
            except Exception:
                pass

            print(
                "[LOGIN] Đã ở ADFS nhưng đang chờ ô Password... "
                f"frames={len(page.frames)}, inputs={input_count}"
            )
            last_debug = now

        page.wait_for_timeout(200)

    # Debug cuối.
    print("[DEBUG] Không tìm thấy Password.")
    print(f"[DEBUG] URL: {page.url}")
    print(f"[DEBUG] Số frame: {len(page.frames)}")

    for index, frame in enumerate(page.frames):
        try:
            print(
                f"[DEBUG] Frame {index}: "
                f"url={frame.url} | "
                f"inputs={frame.locator('input').count()}"
            )
        except Exception:
            pass

    raise PlaywrightTimeoutError(
        "Đã ở host sso.hust.edu.vn nhưng sau 120 giây "
        "vẫn không tìm thấy ô mật khẩu."
    )


def _fill_password(password_box, password: str) -> None:
    """
    Ưu tiên fill bình thường. Nếu element đã attach nhưng Playwright
    đánh giá visibility/actionability không ổn, thử force=True.
    """
    try:
        password_box.fill(
            password,
            timeout=15_000,
        )
    except Exception as first_error:
        print(
            "[LOGIN] fill() bình thường chưa thành công, "
            "thử force=True..."
        )

        try:
            password_box.fill(
                password,
                force=True,
                timeout=15_000,
            )
        except Exception:
            raise first_error

    try:
        value_length = len(password_box.input_value())
    except Exception:
        value_length = -1

    if value_length == 0:
        raise AuthManagerError(
            "Đã gọi fill() nhưng ô mật khẩu vẫn trống."
        )

    if value_length > 0:
        print(
            f"[LOGIN] Đã nhập mật khẩu ({value_length} ký tự)."
        )
    else:
        print("[LOGIN] Đã gửi mật khẩu vào ô Password.")


def _click_adfs_sign_in(frame) -> None:
    candidates = [
        frame.locator("#submitButton"),
        frame.locator('button[type="submit"]'),
        frame.locator('input[type="submit"]'),
        frame.get_by_text("Sign in", exact=True),
        frame.get_by_role(
            "button",
            name=re.compile(
                r"^(Sign in|Đăng nhập|Login)$",
                re.I,
            ),
        ),
    ]

    for locator in candidates:
        try:
            if locator.count() > 0 and locator.first.is_visible():
                locator.first.click()
                return
        except Exception:
            pass

    raise AuthManagerError(
        "Đã nhập mật khẩu nhưng không tìm thấy "
        "nút Sign in của HUST ADFS."
    )


def _wait_after_sign_in(
    page: Page,
    timeout: int = LOGIN_TIMEOUT,
) -> None:
    end = time.monotonic() + timeout / 1000

    while time.monotonic() < end:
        human = _human_verification_message(page)
        if human:
            raise HumanVerificationRequired(
                f"Yêu cầu xác minh tương tác: {human}"
            )

        yes_button = page.get_by_role(
            "button",
            name=re.compile(r"^Yes$", re.I),
        )

        if _is_visible(yes_button):
            print("[LOGIN] Microsoft hỏi Stay signed in -> Yes")
            yes_button.first.click()
            page.wait_for_timeout(800)
            continue

        host = _host(page)

        if host == "qldt.hust.edu.vn":
            print("[LOGIN] Đã quay lại QLĐT.")
            return

        page.wait_for_timeout(200)

    raise PlaywrightTimeoutError(
        "Đã đăng nhập nhưng quá 120 giây "
        "vẫn chưa quay về qldt.hust.edu.vn.\n"
        f"URL cuối: {page.url}"
    )


# ============================================================
# LOGIN FLOW
# ============================================================

def _do_login(
    page: Page,
    email: str,
    password: str,
) -> None:
    print("[LOGIN] Mở trang đăng nhập QLĐT...")

    _safe_goto(
        page,
        LOGIN_URL,
        timeout=DEFAULT_TIMEOUT,
        label="QLDT-LOGIN",
    )

    page.wait_for_timeout(1200)
    _log_page("QLDT-LOGIN", page)

    # Chờ UI QLĐT render.
    end = time.monotonic() + 20

    while time.monotonic() < end:
        if _host(page) in (
            "login.microsoftonline.com",
            ADFS_HOST,
        ):
            break

        office = _find_office365(page)
        if office is not None:
            print("[LOGIN] Bấm Office 365...")
            office.click()
            break

        login_button = _find_login_button(page)
        if login_button is not None:
            print("[LOGIN] Bấm Đăng nhập...")
            login_button.click()
            page.wait_for_timeout(500)
            continue

        page.wait_for_timeout(200)

    # Sau khi bấm Office 365, có thể tới email hoặc thẳng ADFS.
    stage = _wait_for_email_or_adfs(page)
    _log_page("LOGIN-STAGE", page)

    if stage == "hust":
        return

    if stage == "email":
        email_box = _find_email_box(page)

        if email_box is None:
            raise AuthManagerError(
                "Không lấy được ô email Microsoft."
            )

        print("[LOGIN] Nhập email Microsoft...")
        email_box.fill(email)

        _click_next(page)

        print(
            "[LOGIN] Đã bấm Next. "
            "Bắt đầu chờ hostname sso.hust.edu.vn..."
        )

        # QUAN TRỌNG:
        # chỉ chờ hostname, không dùng client-request-id hay query string.
        _wait_until_adfs_host(page)

    # Nếu đã ở ADFS từ trước cũng đi vào đây.
    if _host(page) == ADFS_HOST:
        frame, password_box = _wait_for_adfs_password(page)

        # Có thể SSO tự hoàn tất trong lúc chờ.
        if password_box is None:
            return

        print("[LOGIN] Nhập mật khẩu HUST...")
        _fill_password(
            password_box,
            password,
        )

        print("[LOGIN] Bấm Sign in...")
        _click_adfs_sign_in(frame)

        _wait_after_sign_in(page)


# ============================================================
# STORAGE STATE
# ============================================================

def _save_storage_state(
    context: BrowserContext,
) -> None:
    try:
        context.storage_state(
            path=str(AUTH_FILE),
            indexed_db=True,
        )
    except TypeError:
        context.storage_state(
            path=str(AUTH_FILE)
        )


def refresh_auth(
    playwright,
    headless: bool = True,
) -> None:
    email, password = get_credentials()

    PROFILE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    context = None
    page = None

    try:
        print("[LOGIN] Mở Chromium...")

        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=headless,
            viewport={
                "width": 1440,
                "height": 900,
            },
        )

        context.set_default_timeout(DEFAULT_TIMEOUT)

        page = (
            context.pages[0]
            if context.pages
            else context.new_page()
        )

        print(
            "[LOGIN] Thử phiên đăng nhập đã lưu trong profile..."
        )

        if _goto_timetable_and_check(page):
            _save_storage_state(context)
            print(
                "[OK] Profile vẫn đăng nhập. "
                "Đã cập nhật auth.json."
            )
            return

        _do_login(
            page,
            email,
            password,
        )

        print(
            "[LOGIN] Kiểm tra timetable sau đăng nhập..."
        )

        if not _goto_timetable_and_check(page):
            raise AuthManagerError(
                "Đã đăng nhập nhưng vẫn không vào được timetable.\n"
                f"URL cuối: {page.url}"
            )

        _save_storage_state(context)

        print(
            f"[OK] Đã tạo auth.json mới: {AUTH_FILE}"
        )

    except Exception:
        if page is not None:
            try:
                page.screenshot(
                    path=str(ERROR_SCREENSHOT),
                    full_page=True,
                )
                print(
                    f"[INFO] Đã lưu ảnh lỗi: "
                    f"{ERROR_SCREENSHOT}"
                )
            except Exception:
                pass

        raise

    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass


def ensure_auth(
    force_refresh: bool = False,
    headless: bool = True,
) -> Path:
    with sync_playwright() as playwright:

        if not force_refresh:
            print("[AUTH] Đang kiểm tra auth.json...")

            if auth_is_valid(playwright):
                print(
                    "[AUTH] auth.json vẫn còn hiệu lực."
                )
                return AUTH_FILE

            print(
                "[AUTH] auth.json không tồn tại "
                "hoặc đã hết hiệu lực."
            )

        print(
            "[AUTH] Đang tự đăng nhập để "
            "tạo auth.json mới..."
        )

        refresh_auth(
            playwright,
            headless=headless,
        )

        print("[AUTH] Kiểm tra lại auth.json...")

        if not auth_is_valid(playwright):
            raise AuthManagerError(
                "auth.json vừa tạo nhưng kiểm tra lại "
                "vẫn không hợp lệ."
            )

        print("[AUTH] auth.json mới hợp lệ.")
        return AUTH_FILE


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
    )

    parser.add_argument(
        "--headed",
        action="store_true",
    )

    args = parser.parse_args()

    try:
        path = ensure_auth(
            force_refresh=args.force,
            headless=not args.headed,
        )

        print(f"[DONE] Có thể dùng: {path}")

    except HumanVerificationRequired as exc:
        print(
            f"\n[MFA/CAPTCHA] {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    except Exception as exc:
        print(
            f"\n[ERROR] {exc}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()