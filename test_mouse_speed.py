"""
Script Kiểm Thử & Trực Quan Hóa Tốc Độ Chuột Realtime Trong Excel.
Cách chạy:
  1. python test_mouse_speed.py         -> Khởi chạy Giao diện HUD nổi công nghệ cao (PyQt6)
  2. python test_mouse_speed.py --cli   -> Chạy trực tiếp trên Terminal với thanh đo ASCII
  3. python test_mouse_speed.py --sim   -> Chạy mô phỏng kiểm tra thuật toán đo tốc độ
"""

import sys
import os
import time

sys.stdout.reconfigure(encoding='utf-8')

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.core.mouse_tracker import MouseSpeedTracker
from src.core.excel_monitor import ExcelMonitor


def run_terminal_mode():
    """Chế độ hiển thị trực tiếp trên Terminal dạng bảng đo Telemetry."""
    print("=" * 65)
    print("🚀 BẮT ĐẦU ĐO TỐC ĐỘ CHUỘT REALTIME TRONG EXCEL (TERMINAL MODE)")
    print("   Nhấn Ctrl+C để dừng lại bất kỳ lúc nào.")
    print("=" * 65)

    excel_mon = ExcelMonitor()
    excel_mon.connect()
    tracker = MouseSpeedTracker(excel_monitor=excel_mon)

    bar_width = 30

    try:
        while True:
            data = tracker.update()
            speed = data["speed"]
            max_gauge = 1200.0
            filled_len = int(min(bar_width, (speed / max_gauge) * bar_width))
            bar = "█" * filled_len + "░" * (bar_width - filled_len)

            cell_str = f"[{data['hovered_cell']}]" if data['hovered_cell'] else "[N/A]"
            in_excel = "EXCEL ✓" if data["is_inside_excel"] else "OUTSIDE"

            # In dòng trạng thái ghi đè (In-place refresh)
            line = (
                f"\r🎯 {data['x']:4d},{data['y']:4d} | "
                f"Vận tốc: {speed:6.1f} px/s |{bar}| "
                f"{in_excel:7s} | Ô: {cell_str:7s} | {data['state_label'][:25]}"
            )
            sys.stdout.write(line)
            sys.stdout.flush()
            time.sleep(0.04)  # 25 FPS
    except KeyboardInterrupt:
        print("\n\n✅ Đã dừng đo tốc độ chuột.")


def run_sim_mode():
    """Chế độ kiểm thử toán học đo tốc độ bằng cách giả lập tọa độ di chuyển."""
    print("=" * 65)
    print("🧪 CHẠY KIỂM THỬ MÔ PHỎNG THUẬT TOÁN ĐO TỐC ĐỘ CHUỘT (SIMULATION)")
    print("=" * 65)

    tracker = MouseSpeedTracker(excel_monitor=None, smoothing_alpha=0.5)

    # 1. Kịch bản Đứng yên (Ngập ngừng)
    print("\n--- KỊCH BẢN 1: Chuột đứng yên 1 điểm (X=500, Y=300) trong 2.5s ---")
    start_sim = time.time()
    for _ in range(50):
        time.sleep(0.05)
        res = tracker.update(custom_pos=(500, 300))
    print(f"-> Vận tốc: {res['speed']} px/s | Thời gian ngập ngừng: {res['idle_duration']}s")
    print(f"-> Mã trạng thái: {res['state_code']} | Nhãn: {res['state_label']}")
    assert res['speed'] < 5.0, "Lỗi: Tốc độ khi đứng yên phải xấp xỉ 0"
    assert res['is_hesitating'] is True, "Lỗi: Đứng yên > 2s phải nhận diện là ngập ngừng"

    # 2. Kịch bản Rê chuột cẩn thận (Precision)
    print("\n--- KỊCH BẢN 2: Rê chuột chậm từng pixel (Chọn ô tính chính xác) ---")
    curr_x, curr_y = 500, 300
    for i in range(30):
        time.sleep(0.033)
        curr_x += 4
        curr_y += 2
        res = tracker.update(custom_pos=(curr_x, curr_y))
    print(f"-> Vận tốc: {res['speed']} px/s | Mã trạng thái: {res['state_code']} | Nhãn: {res['state_label']}")
    assert 50.0 < res['speed'] < 400.0, f"Lỗi tốc độ: {res['speed']} px/s không nằm trong dải Precision"

    # 3. Kịch bản Quét nhanh / Lắc chuột (Rapid Scanning)
    print("\n--- KỊCH BẢN 3: Lướt chuột nhanh quét toàn màn hình ---")
    for i in range(20):
        time.sleep(0.033)
        curr_x += 45
        curr_y += 30
        res = tracker.update(custom_pos=(curr_x, curr_y))
    print(f"-> Vận tốc: {res['speed']} px/s | Mã trạng thái: {res['state_code']} | Nhãn: {res['state_label']}")
    assert res['speed'] > 800.0, f"Lỗi: Tốc độ {res['speed']} phải thuộc dải quét nhanh"

    print("\n🎉 TẤT CẢ KIỂM THỬ THUẬT TOÁN ĐO TỐC ĐỘ ĐỀU ĐẠT CHÍNH XÁC 100%!")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--cli":
            run_terminal_mode()
            return
        elif sys.argv[1] == "--sim":
            run_sim_mode()
            return

    # Mặc định khởi chạy giao diện GUI HUD
    from PyQt6.QtWidgets import QApplication
    from src.gui.mouse_speed_hud import MouseSpeedHUD

    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    hud = MouseSpeedHUD()
    hud.show()
    print("✨ Cửa sổ Mouse Telemetry HUD đang hiển thị trên màn hình!")
    print("   (Di chuột qua lại màn hình hoặc trên Excel để thấy kim tốc độ nhảy realtime)")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
