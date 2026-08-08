#Sequential-c: Đăng kí từng lớp rồi gửi đăng kí từng lớp, huỷ các lớp hết chỗ sau khi đăng kí (có 2 mode)
from pathlib import Path
import re

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
    CANCEL_MODE,
)


# =========================================================
# SEQUENTIAL
#
# CANCEL_MODE = 1:
#   đăng ký lớp nào xong -> nếu Hết chỗ -> hủy ngay
#   -> gửi thay đổi hủy -> rồi mới sang lớp tiếp theo.
#
# CANCEL_MODE = 2:
#   đăng ký xong toàn bộ CLASS_IDS
#   -> sau đó mới hủy tất cả lớp Hết chỗ.
#
# CONFIRM_CANCEL:
#   quyết định có gọi f() để gửi thay đổi hủy hay không.
#
# LƯU Ý:
#   CANCEL_MODE = 1 yêu cầu CONFIRM_CANCEL = True.
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


def select_class(page, class_id):

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

    print("[7] Đã click ô chọn.")

    # -----------------------------------------------------
    # Nút Xác nhận
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

    print("[8] Nút Xác nhận đã sẵn sàng.")

    confirm.click()

    print("[9] Đã bấm Xác nhận.")

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
        "[10] Đã chuyển lớp sang danh sách đăng ký."
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

    if CANCEL_MODE not in (1, 2):

        print(
            "ERROR: CANCEL_MODE chỉ được phép là 1 hoặc 2."
        )

        return

    if CANCEL_MODE == 1 and not CONFIRM_CANCEL:

        print(
            "ERROR: CANCEL_MODE = 1 cần CONFIRM_CANCEL = True."
        )

        print(
            "Nếu muốn CONFIRM_CANCEL = False, hãy dùng CANCEL_MODE = 2."
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

            wait_hust_ready(
                page
            )

            print(
                "[0] Trang đăng ký đã sẵn sàng."
            )

            # =================================================
            # ĐĂNG KÝ TỪNG MÃ
            # =================================================

            total = len(
                CLASS_IDS
            )

            for index, class_id in enumerate(
                CLASS_IDS,
                start=1
            ):

                print()
                print(
                    "======================================"
                )
                print(
                    f"SEQUENTIAL {index}/{total}: {class_id}"
                )
                print(
                    "======================================"
                )

                # =============================================
                # CHỌN + GỬI ĐĂNG KÝ LỚP NÀY
                # =============================================

                select_class(
                    page,
                    class_id
                )

                f(
                    page
                )

                wait_hust_ready(
                    page
                )

                # =============================================
                # CANCEL_MODE = 1
                #
                # Lớp nào vừa đăng ký xong mà Hết chỗ
                # -> hủy ngay
                # -> gửi thay đổi hủy ngay
                # -> rồi mới sang lớp tiếp theo.
                # =============================================

                if CANCEL_MODE == 1:

                    cancelled_ids = cancel_full_classes(
                        page,
                        [class_id]
                    )

                    if cancelled_ids:

                        f(
                            page
                        )

                        wait_hust_ready(
                            page
                        )

                # =============================================
                # Còn lớp tiếp theo -> quay lại Bước 1
                # =============================================

                if index < total:

                    back_to_step_1(
                        page
                    )

            # =================================================
            # CANCEL_MODE = 2
            #
            # Đăng ký xong toàn bộ CLASS_IDS
            # rồi mới hủy tất cả lớp Hết chỗ.
            # =================================================

            if CANCEL_MODE == 2:

                cancelled_ids = cancel_full_classes(
                    page,
                    CLASS_IDS
                )

                if cancelled_ids:

                    if CONFIRM_CANCEL:

                        print()
                        print(
                            "CONFIRM_CANCEL = True"
                        )

                        print(
                            "Gọi f() để gửi thay đổi hủy..."
                        )

                        f(
                            page
                        )

                        wait_hust_ready(
                            page
                        )

                    else:

                        print()
                        print(
                            "CONFIRM_CANCEL = False"
                        )

                        print(
                            "Không gọi f() cho phần hủy."
                        )

            print()
            print(
                "ĐÃ XỬ LÝ HẾT CLASS_IDS."
            )

        except PlaywrightTimeoutError as error:

            print()
            print("======================================")
            print("PLAYWRIGHT TIMEOUT")
            print("======================================")

            print(error)

            try:

                page.screenshot(
                    path="error.png",
                    full_page=True
                )

                print()
                print(
                    "Đã lưu ảnh lỗi: "
                    "error.png"
                )

            except Exception:
                pass

        except Exception as error:

            print()
            print("======================================")
            print("CÓ LỖI XẢY RA")
            print("======================================")

            print(error)

            try:

                page.screenshot(
                    path="error.png",
                    full_page=True
                )

                print()
                print(
                    "Đã lưu ảnh lỗi: "
                    "error.png"
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