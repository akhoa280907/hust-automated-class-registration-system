#Mở nhiều tab 1 lúc và đăng kí song song tất cả các mã lớp.
from pathlib import Path
import re
from multiprocessing import Event, Process, Queue, freeze_support
from queue import Empty

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
)


# =========================================================
# CẤU HÌNH
# =========================================================
#
# REGISTER_URL
# CLASS_IDS
# DEFAULT_TIMEOUT
# SEARCH_TIMEOUT
#
# được import trực tiếp từ hust_config_v2.py.
# =========================================================


# =========================================================
# CHỜ HUST LOAD XONG
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


# =========================================================
# TÌM DÒNG CHỨA MÃ LỚP
# =========================================================

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


# =========================================================
# TÌM LỚP
# =========================================================

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

    # Chờ HUST xử lý/loading xong trước khi bấm Search
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


# =========================================================
# CHỌN LỚP - BATCH
# =========================================================
#
# Flow batch:
#   tìm mã 1 -> chọn mã 1 -> Xác nhận
#   tìm mã 2 -> chọn mã 2 -> Xác nhận
#   tìm mã 3 -> chọn mã 3 -> Xác nhận
#   ...
# Sau khi xác nhận chọn hết các mã:
#   arrow-right -> Gửi đăng ký
#
# Selector và cách click giữ nguyên từ code gốc.
# =========================================================

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


# =========================================================
# SAU KHI ĐÃ XÁC NHẬN CHỌN HẾT CLASS_IDS
# MỚI CHUYỂN SANG DANH SÁCH ĐĂNG KÝ
# =========================================================
#
# Chỉ còn phần arrow-right của code gốc.
# =========================================================

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


# =========================================================
# GỬI ĐĂNG KÝ
# =========================================================

def submit_registration(page):

    print()
    print("======================================")
    print("GỬI ĐĂNG KÝ")
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


# =========================================================
# CHẠY 1 MÃ LỚP TRÊN 1 PROCESS / 1 CỬA SỔ PLAYWRIGHT
# =========================================================

def run_one_class(worker_id, class_id, close_event, result_queue):

    class_id = str(class_id).strip()

    auth_file = Path("auth.json")

    browser = None
    context = None
    page = None
    status = "UNKNOWN"

    safe_class_id = re.sub(
        r"[^0-9A-Za-z_-]+",
        "_",
        class_id
    )

    error_image = f"error_r1_{safe_class_id}.png"

    try:

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

            print()
            print(
                f"[{class_id}] Đang mở trang đăng ký HUST..."
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
                f"[{class_id}] Trang đăng ký đã sẵn sàng."
            )

            print()
            print("======================================")
            print(f"R1 SONG SONG: {class_id}")
            print("======================================")

            # Mỗi process chỉ xử lý đúng 1 mã lớp.
            select_class_and_confirm(
                page,
                class_id
            )

            move_to_registration_list(
                page
            )

            submit_registration(
                page
            )

            status = "ĐÃ HOÀN THÀNH CHUỖI GỬI ĐĂNG KÝ"

    except PlaywrightTimeoutError as error:

        status = f"PLAYWRIGHT TIMEOUT: {error}"

        print()
        print("======================================")
        print(f"[{class_id}] PLAYWRIGHT TIMEOUT")
        print("======================================")
        print(error)

        if page is not None:

            try:

                page.screenshot(
                    path=error_image,
                    full_page=True
                )

                print(
                    f"[{class_id}] Đã lưu ảnh lỗi: {error_image}"
                )

            except Exception:
                pass

    except Exception as error:

        status = f"CÓ LỖI: {error}"

        print()
        print("======================================")
        print(f"[{class_id}] CÓ LỖI XẢY RA")
        print("======================================")
        print(error)

        if page is not None:

            try:

                page.screenshot(
                    path=error_image,
                    full_page=True
                )

                print(
                    f"[{class_id}] Đã lưu ảnh lỗi: {error_image}"
                )

            except Exception:
                pass

    finally:

        # Báo kết quả về process chính.
        try:

            result_queue.put(
                (
                    worker_id,
                    class_id,
                    status
                )
            )

        except Exception:
            pass

        print()
        print(
            f"[{class_id}] Đã chạy xong. "
            "Đang giữ cửa sổ Chromium mở..."
        )

        # Đợi process chính cho phép đóng.
        close_event.wait()

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


# =========================================================
# MAIN
# =========================================================

def main():

    auth_file = Path("auth.json")

    if not auth_file.exists():

        print(
            "ERROR: Không tìm thấy auth.json"
        )

        print(
            "Hãy chạy file trong thư mục hust-auto-register."
        )

        return

    class_ids = [
        str(class_id).strip()
        for class_id in CLASS_IDS
        if str(class_id).strip()
    ]

    if not class_ids:

        print(
            "ERROR: CLASS_IDS trong config.py đang trống."
        )

        return

    print()
    print("======================================")
    print("R1 - CHẠY SONG SONG THEO MÃ LỚP")
    print("======================================")

    print(
        f"Số mã lớp: {len(class_ids)}"
    )

    for index, class_id in enumerate(
        class_ids,
        start=1
    ):

        print(
            f"  {index}. {class_id}"
        )

    print()
    print(
        "Mỗi mã lớp sẽ mở một cửa sổ Chromium riêng."
    )
    print(
        "Các cửa sổ chạy đồng thời và dùng cùng auth.json."
    )
    print()

    close_event = Event()
    result_queue = Queue()

    workers = []

    try:

        for worker_id, class_id in enumerate(
            class_ids,
            start=1
        ):

            process = Process(
                target=run_one_class,
                args=(
                    worker_id,
                    class_id,
                    close_event,
                    result_queue,
                ),
                name=f"r1-{class_id}",
            )

            process.start()

            workers.append(
                (
                    worker_id,
                    class_id,
                    process
                )
            )

        print(
            f"Đã mở {len(workers)} worker."
        )

        print(
            "Đang chờ tất cả worker chạy xong..."
        )

        results = {}

        while len(results) < len(workers):

            try:

                worker_id, class_id, status = result_queue.get(
                    timeout=0.5
                )

                if worker_id not in results:

                    results[worker_id] = (
                        class_id,
                        status
                    )

                    print()
                    print(
                        f"[KẾT QUẢ] {class_id}: {status}"
                    )

            except Empty:

                # Tránh main bị treo nếu một process con chết bất thường.
                for worker_id, class_id, process in workers:

                    if (
                        worker_id not in results
                        and not process.is_alive()
                    ):

                        results[worker_id] = (
                            class_id,
                            "PROCESS KẾT THÚC BẤT THƯỜNG "
                            f"(exit code {process.exitcode})"
                        )

                        print()
                        print(
                            f"[KẾT QUẢ] {class_id}: "
                            "process kết thúc bất thường "
                            f"(exit code {process.exitcode})"
                        )

        print()
        print("======================================")
        print("TẤT CẢ WORKER ĐÃ CHẠY XONG")
        print("======================================")

        for worker_id in sorted(results):

            class_id, status = results[worker_id]

            print(
                f"{class_id}: {status}"
            )

        print()

        input(
            "Nhấn Enter để đóng TẤT CẢ cửa sổ Chromium..."
        )

    except KeyboardInterrupt:

        print()
        print(
            "Đã nhận Ctrl+C. Đang đóng tất cả worker..."
        )

    finally:

        close_event.set()

        for worker_id, class_id, process in workers:

            process.join(
                timeout=10
            )

            if process.is_alive():

                process.terminate()

                process.join(
                    timeout=5
                )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    freeze_support()

    main()