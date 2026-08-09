from datetime import datetime
import re
import time

from playwright.sync_api import (
    sync_playwright,
    expect,
    TimeoutError as PlaywrightTimeoutError,
)

from auth_manager import ensure_auth

from config import (
    REGISTER_URL,
    SEND_MARKER,
    PLAN,
    CANCEL_IF_FULL,
    CANCEL_MODE,
    RETRY_LOOP,
    LOOP_LIMIT,
    RETRY_DELAY,
    RETRY_FAILED_ONLY,
    STOP_ON_FIRST_SUCCESS,
    VERIFY_AUTH,
    SHOW_SUMMARY,
    SAVE_LOG,
    LOG_FILE,
    DEFAULT_TIMEOUT,
    SEARCH_TIMEOUT,
    UI_TIMEOUT,
    HEADLESS,
)


# =========================================================
# LOG
# =========================================================

def log(message):
    if not SAVE_LOG:
        return

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file.write(f"[{now}] {message}\n")


# =========================================================
# HELPER
# =========================================================

def any_visible(locator):
    try:
        for i in range(min(locator.count(), 20)):
            if locator.nth(i).is_visible():
                return True
    except Exception:
        pass

    return False


# =========================================================
# WAIT / CLICK
# =========================================================

def wait_visible(page, locator, timeout, description):
    try:
        expect(locator).to_be_visible(timeout=timeout)
    except PlaywrightTimeoutError:
        raise PlaywrightTimeoutError(
            f"Timeout khi chờ {description}"
        )


def click(page, locator, timeout, description, force=False):
    wait_visible(page, locator, timeout, description)

    expect(locator).to_be_enabled(timeout=timeout)

    try:
        locator.click(timeout=timeout)

    except PlaywrightTimeoutError:
        if force:
            locator.click(force=True, timeout=5000)
        else:
            raise


def wait_hust_ready(page):
    loading = (
        page
        .locator("div")
        .filter(
            has_text=re.compile(
                r"^Đang tải\.\.\.$"
            )
        )
    )

    end = time.monotonic() + SEARCH_TIMEOUT / 1000

    while True:
        if not any_visible(loading):
            return

        if time.monotonic() >= end:
            raise PlaywrightTimeoutError(
                "Timeout khi chờ HUST tải xong."
            )

        page.wait_for_timeout(100)


# =========================================================
# PLAN
# =========================================================

def parse_plan():
    if not PLAN:
        raise ValueError("PLAN đang trống.")

    marker = SEND_MARKER.strip()

    groups = []
    group = []
    seen = set()

    for item in PLAN:
        if not isinstance(item, str):
            raise ValueError("Mọi phần tử PLAN phải là chuỗi.")

        item = item.strip()

        # "" = tín hiệu gửi đăng ký.
        if item == marker:
            if group:
                groups.append(group)
                group = []
            continue

        if not item.isdigit():
            raise ValueError(
                f"'{item}' không phải mã lớp."
            )

        if item in seen:
            raise ValueError(f"Mã lớp {item} bị lặp.")

        seen.add(item)
        group.append(item)

    # Hết PLAN mà vẫn còn lớp -> tự gửi lần cuối.
    if group:
        groups.append(group)

    if not groups:
        raise ValueError("PLAN không có mã lớp.")

    return groups


def filter_groups(groups, pending_ids):
    pending = set(pending_ids)

    return [
        filtered
        for group in groups
        if (filtered := [x for x in group if x in pending])
    ]


def flatten(groups):
    return [x for group in groups for x in group]


# =========================================================
# CAPTCHA - CHỈ NHẬN KHI CÓ THAY ĐỔI SAU XÁC NHẬN CUỐI
# =========================================================

CAPTCHA_SELECTORS = [
    'iframe[src*="recaptcha" i]',
    'iframe[src*="hcaptcha" i]',
    'iframe[src*="turnstile" i]',
    'iframe[src*="challenges.cloudflare.com" i]',
    'iframe[title*="captcha" i]',
    '.g-recaptcha',
    '.h-captcha',
    '.cf-turnstile',
]


def captcha_visible_state(page):
    """
    Trả về số phần tử CAPTCHA đang visible cho từng selector.

    Hàm này KHÔNG quyết định có CAPTCHA hay không.
    Nó chỉ chụp trạng thái để so sánh trước/sau click cuối.
    """
    state = {}

    for selector in CAPTCHA_SELECTORS:
        visible_count = 0

        try:
            locator = page.locator(selector)

            for i in range(min(locator.count(), 10)):
                try:
                    if locator.nth(i).is_visible():
                        visible_count += 1
                except Exception:
                    pass

        except Exception:
            pass

        state[selector] = visible_count

    return state


def captcha_appeared_after_final(page, before_state):
    """
    Chỉ trả True nếu sau click Xác nhận cuối có CAPTCHA
    mới xuất hiện so với trạng thái ngay trước click.

    Nhờ vậy iframe/challenge tồn tại sẵn trên trang
    sẽ KHÔNG làm bot báo CAPTCHA nhầm.
    """
    end = time.monotonic() + 2.0

    while time.monotonic() < end:
        after_state = captcha_visible_state(page)

        for selector in CAPTCHA_SELECTORS:
            if (
                after_state.get(selector, 0)
                > before_state.get(selector, 0)
            ):
                log(
                    "CAPTCHA APPEARED AFTER FINAL CONFIRM: "
                    + selector
                )
                return True

        page.wait_for_timeout(100)

    return False


# =========================================================
# HUST - TÌM / CHỌN
# =========================================================

def get_class_row(page, class_id):
    return (
        page
        .get_by_role("row")
        .filter(
            has=page.get_by_text(class_id, exact=True)
        )
        .first
    )


def search_class(page, class_id):
    search_box = page.get_by_role(
        "searchbox",
        name="Mã lớp, mã học phần",
    )

    search_button = page.get_by_role(
        "button",
        name="search",
    )

    wait_visible(
        page,
        search_box,
        UI_TIMEOUT,
        "ô tìm kiếm",
    )

    expect(search_box).to_be_enabled(timeout=UI_TIMEOUT)

    search_box.fill("")
    search_box.fill(class_id)

    expect(search_box).to_have_value(class_id)

    wait_hust_ready(page)

    click(
        page,
        search_button,
        SEARCH_TIMEOUT,
        f"Search lớp {class_id}",
    )

    row = get_class_row(page, class_id)

    wait_visible(
        page,
        row,
        SEARCH_TIMEOUT,
        f"kết quả lớp {class_id}",
    )

    return row


def select_class(page, class_id):
    search_class(page, class_id)

    row = get_class_row(page, class_id)

    checkbox = row.get_by_label("", exact=True)

    # Không dùng .check() vì HUST rerender DOM.
    click(
        page,
        checkbox,
        UI_TIMEOUT,
        f"checkbox lớp {class_id}",
    )

    confirm = page.get_by_role(
        "button",
        name="Xác nhận",
        exact=True,
    )

    click(
        page,
        confirm,
        UI_TIMEOUT,
        f"Xác nhận lớp {class_id}",
    )

    print(f"Đã chọn {class_id}")
    log(f"SELECT {class_id}")


def back_to_step_1(page):
    tab = page.get_by_role(
        "tab",
        name=re.compile(r"Bước 1:\s*Chọn lớp"),
    )

    click(
        page,
        tab,
        UI_TIMEOUT,
        "Bước 1: Chọn lớp",
    )

    search_box = page.get_by_role(
        "searchbox",
        name="Mã lớp, mã học phần",
    )

    wait_visible(
        page,
        search_box,
        UI_TIMEOUT,
        "ô tìm kiếm Bước 1",
    )

    wait_hust_ready(page)


# =========================================================
# f() = GỬI ĐĂNG KÝ
# =========================================================

def f(page):
    send_button = page.get_by_role(
        "button",
        name="send Xác nhận đăng ký",
    )

    click(
        page,
        send_button,
        UI_TIMEOUT,
        "Gửi đăng ký",
    )

    classes_dialog = page.get_by_role(
        "dialog",
        name="Các lớp đăng ký",
    )

    wait_visible(
        page,
        classes_dialog,
        UI_TIMEOUT,
        "dialog Các lớp đăng ký",
    )

    register_confirm = classes_dialog.get_by_role(
        "button",
        name="Xác nhận đăng ký",
        exact=True,
    )

    click(
        page,
        register_confirm,
        UI_TIMEOUT,
        "Xác nhận đăng ký",
    )

    final_dialog = page.get_by_role(
        "dialog",
        name="Xác nhận đăng ký",
    )

    wait_visible(
        page,
        final_dialog,
        UI_TIMEOUT,
        "popup xác nhận cuối",
    )

    message = final_dialog.get_by_text(
        "Bạn chắc chắn muốn đăng ký?",
        exact=False,
    )

    wait_visible(
        page,
        message,
        UI_TIMEOUT,
        "nội dung xác nhận cuối",
    )

    final_confirm = final_dialog.get_by_role(
        "button",
        name="Xác nhận",
        exact=True,
    )

    final_confirm.scroll_into_view_if_needed()

    # Chụp trạng thái CAPTCHA NGAY TRƯỚC click cuối.
    # Các iframe/challenge đã tồn tại sẵn sẽ bị bỏ qua.
    captcha_before = captcha_visible_state(page)

    click(
        page,
        final_confirm,
        UI_TIMEOUT,
        "Xác nhận cuối",
        force=True,
    )

    print("Đã bấm Xác nhận cuối.")
    log("FINAL CONFIRM CLICKED")

    # Chỉ dừng nếu có CAPTCHA MỚI xuất hiện sau click.
    if captcha_appeared_after_final(
        page,
        captcha_before,
    ):
        print()
        print("========== CAPTCHA ==========")
        print("CAPTCHA mới xuất hiện sau Xác nhận cuối.")
        print("Hãy tự giải CAPTCHA trên trình duyệt.")
        input("Giải xong rồi nhấn Enter để automation tiếp tục...")

        log("MANUAL CAPTCHA STEP COMPLETED")

    print("Đã gửi đăng ký.")
    log("SUBMIT")


def g(page):
    arrow = page.get_by_role(
        "button",
        name="arrow-right",
    )

    click(
        page,
        arrow,
        UI_TIMEOUT,
        "arrow-right",
    )

    f(page)
    wait_hust_ready(page)


# =========================================================
# TRẠNG THÁI
# =========================================================

def read_status(page, class_id):
    rows = (
        page
        .get_by_role("row")
        .filter(
            has=page.get_by_text(class_id, exact=True)
        )
    )

    try:
        for i in range(rows.count()):
            row = rows.nth(i)

            if not row.is_visible():
                continue

            text = row.inner_text()

            if "Không thành công" in text:
                return "KHÔNG THÀNH CÔNG"

            if "Hết chỗ" in text:
                return "HẾT CHỖ"

            if "Thành công" in text:
                return "THÀNH CÔNG"

            if "Đã chọn" in text:
                return "ĐÃ CHỌN"

        return "CHƯA XÁC ĐỊNH"

    except Exception:
        return "KHÔNG ĐỌC ĐƯỢC"


def collect_statuses(page, class_ids):
    wait_hust_ready(page)

    result = {}

    for class_id in class_ids:
        status = read_status(page, class_id)
        result[class_id] = status

        print(f"{class_id}: {status}")
        log(f"STATUS {class_id}: {status}")

    return result


# =========================================================
# HỦY HẾT CHỖ
# =========================================================

def cancel_full(page, class_ids):
    if not CANCEL_IF_FULL:
        return []

    cancelled = []

    for class_id in class_ids:
        row = (
            page
            .get_by_role("row")
            .filter(
                has=page.get_by_text(class_id, exact=True)
            )
            .filter(has_text="Hết chỗ")
            .first
        )

        try:
            if row.count() == 0 or not row.is_visible():
                continue
        except Exception:
            continue

        cancel_button = row.get_by_role(
            "button",
            name="Hủy",
            exact=True,
        )

        click(
            page,
            cancel_button,
            UI_TIMEOUT,
            f"Hủy lớp {class_id}",
        )

        confirm = page.get_by_role(
            "button",
            name="Xác nhận",
            exact=True,
        )

        click(
            page,
            confirm,
            UI_TIMEOUT,
            f"Xác nhận hủy {class_id}",
        )

        cancelled.append(class_id)

        print(f"Đã hủy lớp Hết chỗ {class_id}")
        log(f"CANCEL {class_id}")

    return cancelled


# =========================================================
# RETRY
# =========================================================

def get_retry_ids(class_ids, statuses, cancelled):
    if not RETRY_FAILED_ONLY:
        return list(dict.fromkeys(cancelled))

    retry = []

    for class_id in class_ids:
        status = statuses.get(
            class_id,
            "CHƯA XÁC ĐỊNH",
        )

        if (
            status == "HẾT CHỖ"
            and class_id in cancelled
        ):
            retry.append(class_id)

        elif status == "KHÔNG THÀNH CÔNG":
            retry.append(class_id)

    return list(dict.fromkeys(retry))


# =========================================================
# 1 VÒNG
# =========================================================

def run_round(
    page,
    base_groups,
    pending_ids,
    attempts,
    last_status,
):
    groups = filter_groups(base_groups, pending_ids)

    round_ids = flatten(groups)
    round_status = {}
    cancelled_all = []
    retry_ids = []

    for group_index, group in enumerate(groups):
        print()
        print("Nhóm:", ", ".join(group))

        for class_id in group:
            attempts[class_id] += 1
            log(
                f"ATTEMPT {class_id}: "
                f"{attempts[class_id]}"
            )
            select_class(page, class_id)

        # Đây chính là marker "".
        g(page)

        statuses = collect_statuses(page, group)

        round_status.update(statuses)
        last_status.update(statuses)

        # Nếu bật chế độ dừng khi có 1 lớp thành công,
        # dừng ngay sau khi đọc thấy THÀNH CÔNG.
        if (
            STOP_ON_FIRST_SUCCESS
            and "THÀNH CÔNG" in statuses.values()
        ):
            success_id = next(
                class_id
                for class_id, status in statuses.items()
                if status == "THÀNH CÔNG"
            )

            print()
            print(
                f"{success_id} đã THÀNH CÔNG "
                "-> dừng toàn bộ quá trình."
            )

            log(
                "STOP ON FIRST SUCCESS: "
                + success_id
            )

            return [], True

        # Mode 1: hủy ngay sau lần gửi hiện tại.
        if CANCEL_IF_FULL and CANCEL_MODE == 1:
            cancelled = cancel_full(page, group)
            cancelled_all.extend(cancelled)

            if cancelled:
                f(page)
                wait_hust_ready(page)

            retry_ids.extend(
                get_retry_ids(
                    group,
                    statuses,
                    cancelled,
                )
            )

        if group_index < len(groups) - 1:
            back_to_step_1(page)

    # Mode 2: hết cả vòng mới hủy.
    if CANCEL_IF_FULL and CANCEL_MODE == 2:
        cancelled_all = cancel_full(page, round_ids)

        if cancelled_all:
            f(page)
            wait_hust_ready(page)

        retry_ids = get_retry_ids(
            round_ids,
            round_status,
            cancelled_all,
        )

    if not CANCEL_IF_FULL:
        retry_ids = []

    return list(dict.fromkeys(retry_ids)), False


# =========================================================
# SUMMARY
# =========================================================

def summary(
    class_ids,
    attempts,
    last_status,
    rounds,
    hit_limit,
):
    if not SHOW_SUMMARY:
        return

    print()
    print("========== TÓM TẮT ==========")

    for class_id in class_ids:
        status = last_status.get(
            class_id,
            "CHƯA XÁC ĐỊNH",
        )

        print(
            f"{class_id}: {status} "
            f"(thử {attempts[class_id]} lần)"
        )

    print(f"Số vòng: {rounds}")

    if hit_limit:
        print(f"Đã đạt LOOP_LIMIT = {LOOP_LIMIT}")

    log(
        "SUMMARY: "
        + ", ".join(
            f"{class_id}="
            f"{last_status.get(class_id, 'CHƯA XÁC ĐỊNH')}"
            for class_id in class_ids
        )
    )


# =========================================================
# MAIN
# =========================================================

def validate():
    if CANCEL_MODE not in (1, 2):
        raise ValueError(
            "CANCEL_MODE chỉ được là 1 hoặc 2."
        )

    if RETRY_LOOP and not CANCEL_IF_FULL:
        raise ValueError(
            "RETRY_LOOP=True yêu cầu "
            "CANCEL_IF_FULL=True."
        )

    if (
        not isinstance(LOOP_LIMIT, int)
        or isinstance(LOOP_LIMIT, bool)
        or LOOP_LIMIT < 1
    ):
        raise ValueError(
            "LOOP_LIMIT phải là số nguyên >= 1."
        )

    if (
        not isinstance(RETRY_DELAY, (int, float))
        or isinstance(RETRY_DELAY, bool)
        or RETRY_DELAY < 0
    ):
        raise ValueError(
            "RETRY_DELAY phải >= 0."
        )


def main():
    try:
        validate()
        base_groups = parse_plan()

    except ValueError as error:
        print(f"CONFIG ERROR: {error}")
        return

    class_ids = flatten(base_groups)

  # =====================================================
  # AUTH - TỰ KIỂM TRA / TỰ TẠO LẠI auth.json NẾU HẾT HẠN
  # =====================================================
    try:
        if VERIFY_AUTH:
            print()
            print("========== KIỂM TRA ĐĂNG NHẬP ==========")

            auth = ensure_auth(headless=HEADLESS)

            print(f"[AUTH] Sẵn sàng dùng: {auth}")

        else:
            auth = "auth.json"

    except Exception as error:
        print()
        print("AUTH ERROR")
        print(error)
        log(f"AUTH ERROR: {error}")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS
        )

        context = browser.new_context(
            storage_state=str(auth)
        )

        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)

        attempts = {
            class_id: 0
            for class_id in class_ids
        }

        last_status = {
            class_id: "CHƯA XÁC ĐỊNH"
            for class_id in class_ids
        }

        rounds = 0
        hit_limit = False

        try:
            log("=" * 50)
            log("START register.py")

            page.goto(
                REGISTER_URL,
                wait_until="domcontentloaded",
            )

            search_box = page.get_by_role(
                "searchbox",
                name="Mã lớp, mã học phần",
            )

            wait_visible(
                page,
                search_box,
                UI_TIMEOUT,
                "trang đăng ký HUST",
            )

            wait_hust_ready(page)

            pending = list(class_ids)
            round_number = 1

            while pending:
                rounds = round_number

                print()
                print(
                    f"========== VÒNG {round_number} =========="
                )

                retry, stop_success = run_round(
                    page,
                    base_groups,
                    pending,
                    attempts,
                    last_status,
                )

                if stop_success:
                    break

                if not RETRY_LOOP:
                    break

                pending = retry

                if not pending:
                    break

                if round_number >= LOOP_LIMIT:
                    hit_limit = True
                    break

                print(
                    f"Chờ {RETRY_DELAY}s trước vòng tiếp..."
                )

                log(
                    "RETRY: "
                    + ", ".join(pending)
                )

                if RETRY_DELAY > 0:
                    time.sleep(RETRY_DELAY)

                back_to_step_1(page)

                round_number += 1

            summary(
                class_ids,
                attempts,
                last_status,
                rounds,
                hit_limit,
            )

        except PlaywrightTimeoutError as error:
            print("PLAYWRIGHT TIMEOUT")
            print(error)

            log(f"TIMEOUT: {error}")

            try:
                page.screenshot(
                    path="error.png",
                    full_page=True,
                )
            except Exception:
                pass

        except Exception as error:
            print("CÓ LỖI XẢY RA")
            print(error)

            log(f"ERROR: {error}")

            try:
                page.screenshot(
                    path="error.png",
                    full_page=True,
                )
            except Exception:
                pass

        finally:
            input(
                "Nhấn Enter để đóng trình duyệt..."
            )

            context.close()
            browser.close()


if __name__ == "__main__":
    main()