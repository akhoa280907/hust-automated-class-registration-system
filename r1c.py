#Batch-c: Đăng kí hết tất cả các lớp rồi mới gửi đăng kí và huỷ các lớp hết chỗ.
from pathlib import Path
import re
import time

from playwright.sync_api import (
    sync_playwright,
    expect,
    TimeoutError as PlaywrightTimeoutError,
)

from config import (
    REGISTER_URL,
    CLASS_IDS,
    DEFAULT_TIMEOUT,
    SEARCH_TIMEOUT,
    CONFIRM_CANCEL,
    RETRY_LOOP,
    LOOP_LIMIT,
    RETRY_DELAY,
    SHOW_SUMMARY,
    SAVE_LOG,
    LOG_FILE,
    RETRY_FAILED_ONLY,
)



# =========================================================
# LOG + KẾT QUẢ
# =========================================================

def save_log(message):
    if not SAVE_LOG:
        return

    from datetime import datetime

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as log_file:

        log_file.write(
            f"[{timestamp}] {message}\n"
        )


def start_log_session(script_name):
    if not SAVE_LOG:
        return

    save_log(
        "=" * 50
    )
    save_log(
        f"START {script_name}"
    )


def print_final_summary(
    attempts,
    last_status,
    stopped_by_limit=False
):

    if not SHOW_SUMMARY:
        return

    print()
    print(
        "======================================"
    )
    print(
        "TÓM TẮT KẾT QUẢ CUỐI"
    )
    print(
        "======================================"
    )

    success_ids = []
    failed_ids = []
    unknown_ids = []

    for class_id in CLASS_IDS:

        status = last_status.get(
            class_id,
            "CHƯA XÁC ĐỊNH"
        )

        attempt_count = attempts.get(
            class_id,
            0
        )

        print(
            f"{class_id}: {status} "
            f"(đã thử {attempt_count} lần)"
        )

        if status == "THÀNH CÔNG":
            success_ids.append(
                class_id
            )

        elif status in (
            "HẾT CHỖ",
            "KHÔNG THÀNH CÔNG"
        ):
            failed_ids.append(
                class_id
            )

        else:
            unknown_ids.append(
                class_id
            )

    print()

    if success_ids:
        print(
            "Đăng ký thành công:"
        )

        for class_id in success_ids:
            print(
                f"    - {class_id}"
            )

    if failed_ids:
        print(
            "Chưa đăng ký thành công:"
        )

        for class_id in failed_ids:
            print(
                f"    - {class_id}"
            )

    if unknown_ids:
        print(
            "Trạng thái chưa xác định:"
        )

        for class_id in unknown_ids:
            print(
                f"    - {class_id}"
            )

    if stopped_by_limit:
        print()
        print(
            f"Đã đạt LOOP_LIMIT = {LOOP_LIMIT}."
        )

    save_log(
        "FINAL SUMMARY: "
        + ", ".join(
            f"{class_id}={last_status.get(class_id, 'CHƯA XÁC ĐỊNH')}"
            for class_id in CLASS_IDS
        )
    )


def get_retry_ids_from_statuses(
    class_ids,
    statuses,
    cancelled_ids
):

    if not RETRY_FAILED_ONLY:

        return list(
            dict.fromkeys(
                cancelled_ids
            )
        )

    retry_ids = []

    for class_id in class_ids:

        status = statuses.get(
            class_id,
            "CHƯA XÁC ĐỊNH"
        )

        if status == "HẾT CHỖ":

            # Chỉ retry HẾT CHỖ khi thao tác hủy
            # của lớp đó đã được thực hiện thành công.
            if class_id in cancelled_ids:
                retry_ids.append(
                    class_id
                )

        elif status == "KHÔNG THÀNH CÔNG":

            retry_ids.append(
                class_id
            )

    return list(
        dict.fromkeys(
            retry_ids
        )
    )



# =========================================================
# BATCH
#
# tìm mã 1 -> chọn -> Xác nhận
# tìm mã 2 -> chọn -> Xác nhận
# ...
# arrow-right
# -> f() gửi đăng ký 1 lần
#
# SAU KHI GỬI XONG TOÀN BỘ:
# -> hủy tất cả lớp Hết chỗ
# -> nếu CONFIRM_CANCEL = True
#    thì f() thêm 1 lần để gửi thay đổi hủy.
# =========================================================

def wait_hust_ready(page):
    loading = (
        page
        .locator("div")
        .filter(
            has_text=re.compile(
                r"^Đang tải\.\.\.$"
            )
        )
        .nth(1)
    )

    expect(loading).to_be_hidden(
        timeout=SEARCH_TIMEOUT
    )


def get_class_row(page, class_id):
    return (
        page
        .get_by_role("row")
        .filter(
            has=page.get_by_text(
                class_id,
                exact=True
            )
        )
        .first
    )


def search_class(page, class_id):

    print()
    print("======================================")
    print(f"TÌM LỚP {class_id}")
    print("======================================")

    search_box = page.get_by_role(
        "searchbox",
        name="Mã lớp, mã học phần"
    )

    search_button = page.get_by_role(
        "button",
        name="search"
    )

    print("[1] Chờ ô tìm kiếm...")

    expect(search_box).to_be_visible(
        timeout=30000
    )

    expect(search_box).to_be_enabled(
        timeout=30000
    )

    expect(search_button).to_be_visible(
        timeout=30000
    )

    expect(search_button).to_be_enabled(
        timeout=30000
    )

    # Xóa nội dung cũ
    search_box.fill("")

    # Nhập mã lớp
    search_box.fill(class_id)

    expect(search_box).to_have_value(
        class_id
    )

    print(f"[2] Đã nhập mã lớp {class_id}")

    # Chờ HUST load xong trước khi bấm Search
    wait_hust_ready(
        page
    )

    # Kiểm tra lại nút Search sau khi loading biến mất
    expect(search_button).to_be_visible(
        timeout=SEARCH_TIMEOUT
    )

    expect(search_button).to_be_enabled(
        timeout=SEARCH_TIMEOUT
    )

    # Bấm Search
    search_button.click()

    print("[3] Đã bấm Search.")
    print("[4] Đang chờ HUST trả kết quả...")

    # Chờ đúng mã lớp xuất hiện
    row = get_class_row(
        page,
        class_id
    )

    expect(row).to_be_visible(
        timeout=SEARCH_TIMEOUT
    )

    print(f"[5] Đã tìm thấy lớp {class_id}")

    return row


def select_class_and_confirm(page, class_id):

    search_class(
        page,
        class_id
    )

    # Lấy lại row mới nhất
    row = get_class_row(
        page,
        class_id
    )

    expect(row).to_be_visible(
        timeout=10000
    )

    print("[6] Đang tích chọn lớp...")

    checkbox = row.get_by_label(
        "",
        exact=True
    )

    expect(checkbox).to_be_visible(
        timeout=10000
    )

    expect(checkbox).to_be_enabled(
        timeout=10000
    )

    # -----------------------------------------------------
    # Không dùng .check()
    # vì HUST render lại DOM sau khi click.
    # -----------------------------------------------------

    checkbox.click()

    print(
        f"[7] Đã click ô chọn lớp {class_id}."
    )

    # -----------------------------------------------------
    # Nút Xác nhận
    #
    # QUAN TRỌNG:
    # Mỗi mã lớp sau khi tick đều phải bấm Xác nhận
    # trước khi tìm mã lớp tiếp theo.
    # -----------------------------------------------------

    confirm = page.get_by_role(
        "button",
        name="Xác nhận",
        exact=True
    )

    expect(confirm).to_be_visible(
        timeout=15000
    )

    expect(confirm).to_be_enabled(
        timeout=15000
    )

    print(
        f"[8] Nút Xác nhận cho lớp {class_id} "
        "đã sẵn sàng."
    )

    confirm.click()

    print(
        f"[9] Đã xác nhận chọn lớp {class_id}."
    )


def move_to_registration_list(page):

    # -----------------------------------------------------
    # Arrow right
    # -----------------------------------------------------

    arrow = page.get_by_role(
        "button",
        name="arrow-right"
    )

    expect(arrow).to_be_visible(
        timeout=20000
    )

    expect(arrow).to_be_enabled(
        timeout=20000
    )

    arrow.click()

    print(
        "[10] Đã chuyển các lớp sang danh sách đăng ký."
    )


def back_to_step_1(page):

    print()
    print(
        "Đang quay lại Bước 1: Chọn lớp..."
    )

    step_1_tab = page.get_by_role(
        "tab",
        name=re.compile(r"Bước 1:\s*Chọn lớp")
    )

    expect(step_1_tab).to_be_visible(
        timeout=30000
    )

    step_1_tab.click()

    search_box = page.get_by_role(
        "searchbox",
        name="Mã lớp, mã học phần"
    )

    expect(search_box).to_be_visible(
        timeout=30000
    )

    wait_hust_ready(
        page
    )

    print(
        "Đã quay lại Bước 1."
    )


def f(page):

    print()
    print("======================================")
    print("HÀM f - GỬI ĐĂNG KÝ")
    print("======================================")

    # =====================================================
    # BƯỚC 1
    #
    # Nút trên trang Bước 2:
    #
    # "Xác nhận đăng ký"
    #
    # Accessible name của Playwright:
    # "send Xác nhận đăng ký"
    # =====================================================

    print("[11] Chờ nút Gửi đăng ký...")

    send_button = page.get_by_role(
        "button",
        name="send Xác nhận đăng ký"
    )

    expect(send_button).to_be_visible(
        timeout=30000
    )

    expect(send_button).to_be_enabled(
        timeout=30000
    )

    send_button.click()

    print("[12] Đã bấm Gửi đăng ký.")

    # =====================================================
    # BƯỚC 2
    #
    # Sau bước trên HUST mở dialog:
    #
    # "Các lớp đăng ký"
    #
    # Trong dialog này có nút:
    #
    # "Xác nhận đăng ký"
    # =====================================================

    print(
        "[13] Đang chờ cửa sổ 'Các lớp đăng ký'..."
    )

    classes_dialog = page.get_by_role(
        "dialog",
        name="Các lớp đăng ký"
    )

    expect(classes_dialog).to_be_visible(
        timeout=30000
    )

    print(
        "[14] Cửa sổ 'Các lớp đăng ký' đã xuất hiện."
    )

    # Nút Xác nhận đăng ký bên trong đúng dialog
    register_confirm = classes_dialog.get_by_role(
        "button",
        name="Xác nhận đăng ký",
        exact=True
    )

    expect(register_confirm).to_be_visible(
        timeout=15000
    )

    expect(register_confirm).to_be_enabled(
        timeout=15000
    )

    print(
        "[15] Đang bấm Xác nhận đăng ký..."
    )

    register_confirm.click()

    print(
        "[16] Đã bấm Xác nhận đăng ký."
    )

    # =====================================================
    # BƯỚC 3 - POPUP CUỐI
    #
    # HUST mở dialog:
    #
    # "Xác nhận đăng ký"
    #
    # Nội dung:
    #
    # "Bạn chắc chắn muốn đăng ký?"
    #
    # Hai nút:
    #
    # Đóng
    # Xác nhận
    # =====================================================

    print(
        "[17] Đang chờ popup xác nhận cuối..."
    )

    final_dialog = page.get_by_role(
        "dialog",
        name="Xác nhận đăng ký"
    )

    expect(final_dialog).to_be_visible(
        timeout=30000
    )

    # Xác nhận đúng popup nhờ nội dung đặc trưng
    final_message = final_dialog.get_by_text(
        "Bạn chắc chắn muốn đăng ký?",
        exact=False
    )

    expect(final_message).to_be_visible(
        timeout=10000
    )

    print(
        "[18] Popup 'Bạn chắc chắn muốn đăng ký?' "
        "đã xuất hiện."
    )

    # =====================================================
    # NÚT XÁC NHẬN CUỐI
    #
    # QUAN TRỌNG:
    # Tên nút là "Xác nhận"
    # KHÔNG phải "Xác nhận đăng ký"
    # =====================================================

    final_confirm = final_dialog.get_by_role(
        "button",
        name="Xác nhận",
        exact=True
    )

    expect(final_confirm).to_be_visible(
        timeout=15000
    )

    expect(final_confirm).to_be_enabled(
        timeout=15000
    )

    final_confirm.scroll_into_view_if_needed()

    print(
        "[19] Đã tìm thấy nút Xác nhận cuối."
    )

    # -----------------------------------------------------
    # Click cuối
    # -----------------------------------------------------

    try:

        final_confirm.click(
            timeout=10000
        )

        print(
            "[20] ĐÃ BẤM XÁC NHẬN CUỐI."
        )

    except Exception as error:

        print(
            "[20] Click bình thường thất bại."
        )

        print(
            "Đang thử force click..."
        )

        final_confirm.click(
            force=True,
            timeout=5000
        )

        print(
            "[20] ĐÃ FORCE CLICK XÁC NHẬN CUỐI."
        )

    # =====================================================
    # KIỂM TRA POPUP ĐÓNG
    # =====================================================

    try:

        expect(final_dialog).to_be_hidden(
            timeout=30000
        )

        print(
            "[21] Popup cuối đã đóng."
        )

    except PlaywrightTimeoutError:

        print(
            "[21] Popup chưa đóng."
        )

        print(
            "HUST có thể đang xử lý hoặc "
            "đang hiển thị thông báo kết quả."
        )

    print()
    print("======================================")
    print("ĐÃ HOÀN THÀNH CHUỖI GỬI ĐĂNG KÝ")
    print("======================================")
    print()
    print(
        "Dòng trên chỉ xác nhận bot đã thực hiện "
        "đầy đủ các thao tác."
    )
    print(
        "Kết quả Thành công/Hết chỗ cần đọc "
        "từ phản hồi tiếp theo của HUST."
    )



def read_registration_status(page, class_id):

    rows = (
        page
        .get_by_role("row")
        .filter(
            has=page.get_by_text(
                class_id,
                exact=True
            )
        )
    )

    try:

        count = rows.count()

        for index in range(count):

            row = rows.nth(index)

            if not row.is_visible():
                continue

            text = row.inner_text()

            # Phải kiểm tra chuỗi âm trước,
            # vì "Không thành công" có chứa "Thành công".
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

    wait_hust_ready(
        page
    )

    statuses = {}

    for class_id in class_ids:

        statuses[class_id] = (
            read_registration_status(
                page,
                class_id
            )
        )

        save_log(
            f"STATUS {class_id}: "
            f"{statuses[class_id]}"
        )

    return statuses



def cancel_full_classes(page, class_ids):

    wait_hust_ready(
        page
    )

    print()
    print("======================================")
    print("HỦY CÁC LỚP HẾT CHỖ")
    print("======================================")

    cancelled_ids = []

    for class_id in class_ids:

        # -------------------------------------------------
        # Tìm đúng row:
        #
        # - có đúng class_id
        # - có chữ "Hết chỗ"
        #
        # Codegen đã xác nhận "Hết chỗ"
        # là text nằm trong cell.
        # -------------------------------------------------

        full_row = (
            page
            .get_by_role("row")
            .filter(
                has=page.get_by_text(
                    class_id,
                    exact=True
                )
            )
            .filter(
                has_text="Hết chỗ"
            )
            .first
        )

        try:

            if full_row.count() == 0:

                print(
                    f"[CANCEL] {class_id}: "
                    "không Hết chỗ."
                )

                continue

            if not full_row.is_visible():

                print(
                    f"[CANCEL] {class_id}: "
                    "row không hiển thị."
                )

                continue

        except Exception:

            print(
                f"[CANCEL] {class_id}: "
                "không tìm thấy row Hết chỗ."
            )

            continue

        print(
            f"[CANCEL] {class_id}: HẾT CHỖ."
        )

        # -------------------------------------------------
        # Nút Hủy nằm trong chính row đó.
        #
        # Không dùng nth() để tránh lệch index.
        # -------------------------------------------------

        cancel_button = full_row.get_by_role(
            "button",
            name="Hủy",
            exact=True
        )

        expect(cancel_button).to_be_visible(
            timeout=15000
        )

        expect(cancel_button).to_be_enabled(
            timeout=15000
        )

        cancel_button.click()

        print(
            f"[CANCEL] {class_id}: đã bấm Hủy."
        )

        # -------------------------------------------------
        # HUST hiện nút Xác nhận thao tác hủy.
        # -------------------------------------------------

        confirm_cancel = page.get_by_role(
            "button",
            name="Xác nhận",
            exact=True
        )

        expect(confirm_cancel).to_be_visible(
            timeout=15000
        )

        expect(confirm_cancel).to_be_enabled(
            timeout=15000
        )

        confirm_cancel.click()

        print(
            f"[CANCEL] {class_id}: "
            "đã Xác nhận hủy."
        )

        cancelled_ids.append(
            class_id
        )

    print()

    if cancelled_ids:

        print(
            "[CANCEL] Đã hủy trên giao diện:"
        )

        for class_id in cancelled_ids:

            print(
                f"    - {class_id}"
            )

    else:

        print(
            "[CANCEL] Không có lớp Hết chỗ."
        )

    return cancelled_ids



# =========================================================
# MAIN
# =========================================================

def main():

    auth_file = Path(
        "auth.json"
    )

    if not auth_file.exists():

        print(
            "ERROR: Không tìm thấy auth.json"
        )

        print(
            "Hãy chạy file trong thư mục "
            "hust-auto-register."
        )

        return

    if not CLASS_IDS:

        print(
            "ERROR: CLASS_IDS trong config.py đang trống."
        )

        return

    if RETRY_LOOP and not CONFIRM_CANCEL:

        print(
            "ERROR: RETRY_LOOP = True chỉ hoạt động "
            "khi CONFIRM_CANCEL = True."
        )

        return

    if not isinstance(LOOP_LIMIT, int) or LOOP_LIMIT < 1:

        print(
            "ERROR: LOOP_LIMIT phải là số nguyên >= 1."
        )

        return

    if RETRY_DELAY < 0:

        print(
            "ERROR: RETRY_DELAY phải >= 0."
        )

        return

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        context = browser.new_context(
            storage_state=str(auth_file)
        )

        page = context.new_page()

        page.set_default_timeout(
            DEFAULT_TIMEOUT
        )

        try:

            start_log_session(
                "batch.py"
            )

            # =================================================
            # MỞ TRANG
            # =================================================

            print(
                "[0] Đang mở trang đăng ký HUST..."
            )

            page.goto(
                REGISTER_URL,
                wait_until="domcontentloaded"
            )

            search_box = page.get_by_role(
                "searchbox",
                name="Mã lớp, mã học phần"
            )

            expect(search_box).to_be_visible(
                timeout=30000
            )

            # Ô tìm kiếm có thể đã xuất hiện nhưng HUST vẫn đang load.
            # Chờ "Đang tải..." biến mất trước khi bắt đầu.
            wait_hust_ready(
                page
            )

            print(
                "[0] Trang đăng ký đã sẵn sàng."
            )

            # =================================================
            # VÒNG ĐĂNG KÝ
            # =================================================

            pending_ids = list(
                dict.fromkeys(
                    CLASS_IDS
                )
            )

            attempts = {
                class_id: 0
                for class_id in CLASS_IDS
            }

            last_status = {
                class_id: "CHƯA XÁC ĐỊNH"
                for class_id in CLASS_IDS
            }

            round_number = 1
            stopped_by_limit = False

            while pending_ids:

                if RETRY_LOOP and round_number > LOOP_LIMIT:

                    stopped_by_limit = True
                    break

                current_ids = list(
                    pending_ids
                )

                save_log(
                    f"BATCH ROUND {round_number}: "
                    + ", ".join(current_ids)
                )

                print()
                print(
                    "######################################"
                )
                print(
                    f"BATCH ROUND {round_number}"
                )
                print(
                    "######################################"
                )

                total = len(
                    current_ids
                )

                for index, class_id in enumerate(
                    current_ids,
                    start=1
                ):

                    attempts[class_id] += 1

                    print()
                    print(
                        f"BATCH {index}/{total}: {class_id}"
                    )

                    save_log(
                        f"ATTEMPT {class_id}: "
                        f"{attempts[class_id]}"
                    )

                    select_class_and_confirm(
                        page,
                        class_id
                    )

                move_to_registration_list(
                    page
                )

                f(
                    page
                )

                wait_hust_ready(
                    page
                )

                # Đọc trạng thái TRƯỚC khi hủy.
                statuses = collect_statuses(
                    page,
                    current_ids
                )

                for class_id, status in statuses.items():
                    last_status[class_id] = status

                # Chỉ HẾT CHỖ mới có thao tác Hủy.
                cancelled_ids = cancel_full_classes(
                    page,
                    current_ids
                )

                if cancelled_ids and CONFIRM_CANCEL:

                    f(
                        page
                    )

                    wait_hust_ready(
                        page
                    )

                    save_log(
                        "CANCEL CONFIRMED: "
                        + ", ".join(cancelled_ids)
                    )

                if not RETRY_LOOP:
                    break

                pending_ids = get_retry_ids_from_statuses(
                    current_ids,
                    statuses,
                    cancelled_ids
                )

                if not pending_ids:
                    break

                if round_number >= LOOP_LIMIT:

                    stopped_by_limit = True
                    break

                print()
                print(
                    f"Chờ {RETRY_DELAY} giây "
                    "trước vòng tiếp theo..."
                )

                save_log(
                    f"RETRY NEXT: {pending_ids}; "
                    f"delay={RETRY_DELAY}s"
                )

                if RETRY_DELAY > 0:
                    time.sleep(
                        RETRY_DELAY
                    )

                back_to_step_1(
                    page
                )

                round_number += 1

            print_final_summary(
                attempts,
                last_status,
                stopped_by_limit=stopped_by_limit
            )

        except PlaywrightTimeoutError as error:

            print()
            print("======================================")
            print("PLAYWRIGHT TIMEOUT")
            print("======================================")

            print(error)
            save_log(
                f"PLAYWRIGHT TIMEOUT: {error}"
            )

            try:

                page.screenshot(
                    path="error.png",
                    full_page=True
                )

                print()
                print(
                    "Đã lưu ảnh lỗi: error.png"
                )

            except Exception:
                pass

        except Exception as error:

            print()
            print("======================================")
            print("CÓ LỖI XẢY RA")
            print("======================================")

            print(error)
            save_log(
                f"ERROR: {error}"
            )

            try:

                page.screenshot(
                    path="error.png",
                    full_page=True
                )

                print()
                print(
                    "Đã lưu ảnh lỗi: error.png"
                )

            except Exception:
                pass

        finally:

            print()

            input(
                "Nhấn Enter để đóng trình duyệt..."
            )

            context.close()
            browser.close()


if __name__ == "__main__":
    main()