"""
KÍCH HOẠT GHI NHẬN THAO TÁC EXCEL - 1 CLICK RUNNER
Dành cho học viên / phòng máy trung tâm:
- Chỉ cần nhấp đúp chuột để chạy.
- Không cần chọn bài, không hiển thị gợi ý làm phiền.
- Mở file Excel bất kỳ lên là tự động ghi nhận toàn bộ thao tác vào Cơ sở dữ liệu.
"""

import os
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import socket

# Thiết lập đường dẫn thư mục gốc
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)

from src.data_collection.universal_recorder import UniversalExcelRecorder


def main():
    pc_name = os.environ.get("COMPUTERNAME", socket.gethostname())
    default_id = f"MAY_{pc_name}"

    print("=" * 75)
    print("      🎯 HỆ THỐNG GHI NHẬN THAO TÁC THỰC HÀNH EXCEL TỰ ĐỘNG")
    print("=" * 75)
    print(f"🖥️  MÁY TÍNH HIỆN TẠI : {pc_name}")
    print("📋  CHẾ ĐỘ HOẠT ĐỘNG  : Tự động ghi ngầm mọi file Excel")
    print("-" * 75)

    name_input = input("👉 Nhập Tên của bạn (hoặc nhấn ENTER để dùng mặc định): ").strip()
    student_name = name_input if name_input else f"Học viên {pc_name}"
    student_id = f"HS_{pc_name}_{int(time.time()) % 10000}" if not name_input else f"HS_{name_input.replace(' ', '_')}"

    recorder = UniversalExcelRecorder(student_id=student_id, student_name=student_name)
    recorder.start()

    print("\n🟢 HỆ THỐNG ĐANG HOẠT ĐỘNG...")
    print("   👉 Bạn hãy mở bất kỳ file Excel nào để làm bài!")
    print("   👉 Nhấn tổ hợp phím Ctrl + C khi muốn kết thúc buổi thực hành.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        recorder.stop()
        print("\n🎉 Buổi thực hành đã kết thúc. Dữ liệu đã được lưu an toàn!")
        time.sleep(2)


if __name__ == "__main__":
    main()
