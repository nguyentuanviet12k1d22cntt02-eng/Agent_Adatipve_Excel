"""
HỆ THỐNG THU THẬP DỮ LIỆU THAO TÁC HỌC VIÊN OFFLINE TRÊN MÁY TÍNH TRUNG TÂM
Chạy trên máy tính trung tâm:
1. Ghi nhận thông tin học viên & bài tập thực hành.
2. Khởi chạy Microsoft Excel và kích hoạt toàn bộ cảm biến Zero-Lag.
3. Thu thập mọi thao tác (chọn ô, nhập công thức, sửa dữ liệu, ngập ngừng chuột, lỗi sai cú pháp).
4. Lưu thời gian thực vào Cơ sở dữ liệu MySQL (chuẩn bị đồng bộ Supabase Cloud).
5. Tự động tính toán vector đặc trưng hành vi người học khi kết thúc.
"""

import os
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import time
import argparse
from datetime import datetime

# Thiết lập đường dẫn thư mục gốc
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from src.core.excel_worker import ExcelObserverWorker
from src.data_collection.db_manager import DatabaseManager
from src.data_collection.event_logger import EventLogger
from src.data_collection.feature_extractor import FeatureExtractor
from src.sensors.base_sensor import RawEvent


def print_banner():
    print("=" * 80)
    print("🎓 HỆ THỐNG GHI NHẬN DỮ LIỆU THỰC HÀNH EXCEL OFFLINE (PHASE 1 TELEMETRY)")
    print("   Trung tâm Đào tạo Tin học & Ứng dụng AI")
    print("   - Cơ sở dữ liệu: MySQL Community Server (Database: excel_adaptive_tutor)")
    print("   - Chuẩn bị đồng bộ: Supabase Cloud Realtime Engine")
    print("   - Giám sát thời gian thực: http://localhost:5173 (ReactJS Dashboard)")
    print("=" * 80)


def list_available_lessons():
    exercise_dir = os.path.join(ROOT_DIR, "bài tập")
    files = [f for f in os.listdir(exercise_dir) if f.endswith(".xlsx") and not f.startswith("~$")]
    return sorted(files)


def run_collection_session(student_id: str, student_name: str, lesson_code: str):
    db_mgr = DatabaseManager()
    if not db_mgr.mysql_available:
        print("⚠️ CẢNH BÁO: Không thể kết nối MySQL! Hệ thống sẽ tạm ghi vào SQLite.")
    else:
        print("✅ ĐÃ KẾT NỐI MYSQL THÀNH CÔNG (127.0.0.1:3306 - excel_adaptive_tutor)")

    # 1. Đăng ký học viên vào CSDL
    now_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if db_mgr.mysql_available:
        try:
            conn = db_mgr.get_mysql_connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO students (student_id, name, created_at)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE name=VALUES(name);
                    """,
                    (student_id, student_name, now_dt),
                )
            conn.close()
            print(f"👤 Học viên: {student_name} (Mã: {student_id}) đã sẵn sàng.")
        except Exception as e:
            print(f"Lỗi đăng ký học viên: {e}")

    session_id = f"SES_{lesson_code}_{student_id}_{int(time.time())}"
    print(f"📌 Khởi tạo Phiên thực hành: {session_id}")
    print(f"📖 Bài thực hành: {lesson_code}")
    print("-" * 80)

    # 2. Khởi tạo EventLogger
    logger = EventLogger(db_manager=db_mgr, batch_size=5, flush_interval=0.2)
    logger.start_session(session_id=session_id, student_id=student_id, lesson_id=lesson_code)

    # Ghi nhận sự kiện bắt đầu phiên
    logger.log_event(
        RawEvent(
            event_type="SESSION_STARTED",
            session_id=session_id,
            lesson_id=lesson_code,
            step_index=0,
            metadata={
                "student_name": student_name,
                "center_station": os.environ.get("COMPUTERNAME", "PC_STATION"),
                "started_at": now_dt,
            },
        )
    )

    print("🚀 Đang khởi động tiến trình giám sát cảm biến Excel...")
    print("💡 HỌC VIÊN CÓ THỂ BẮT ĐẦU MỞ EXCEL VÀ THỰC HÀNH BÌNH THƯỜNG!")
    print("   (Mọi thao tác chọn ô, gõ hàm, ngập ngừng, lỗi công thức sẽ được tự động ghi vào MySQL)")
    print("👉 Mở Dashboard xem trực tiếp: http://localhost:5173")
    print("   Nhấn Ctrl+C để kết thúc phiên và tự động trích xuất vector đặc trưng.")
    print("-" * 80)

    start_time = time.time()
    event_counter = 0

    try:
        # Vòng lặp giám sát (hoặc chạy cùng ExcelObserverWorker)
        # Trong chế độ thực tế: ExcelObserverWorker hoặc COM Sink sẽ liên tục đẩy sự kiện vào logger
        worker = ExcelObserverWorker(hesitation_threshold=3.5, poll_interval_ms=50)
        worker.student_id = student_id
        worker.current_session_id = session_id
        worker.event_logger = logger

        # Mở bài tập tương ứng
        lesson_num = lesson_code.replace("Bài ", "").split(".")[0].strip()
        worker.start()
        worker.post_open_exercise(lesson_num)

        while True:
            time.sleep(1)
            duration = int(time.time() - start_time)
            mins = duration // 60
            secs = duration % 60
            print(f"\r⏱️ Đang ghi nhận phiên [{session_id}]... Thời gian làm bài: {mins:02d}:{secs:02d}", end="", flush=True)

    except KeyboardInterrupt:
        print("\n\n🛑 ĐÃ NHẬN LỆNH KẾT THÚC PHIÊN TỪ GIẢNG VIÊN / HỌC VIÊN.")
    finally:
        total_duration = round(time.time() - start_time, 2)
        print("💾 Đang lưu toàn bộ sự kiện còn lại vào MySQL...")
        logger.end_session(session_id=session_id, status="COMPLETED")
        logger.close()

        # 3. Tự động tính toán vector đặc trưng (Feature Extraction)
        print("📊 Đang tính toán Vector 4 nhóm đặc trưng hành vi (Feature Extraction)...")
        extractor = FeatureExtractor(db_manager=db_mgr)
        features = extractor.compute_and_save_session_features(session_id=session_id, step_index=0)

        print("=" * 80)
        print("🎉 TỔNG KẾT PHIÊN THỰC HÀNH OFFLINE ĐÃ HOÀN TẤT:")
        print(f"   - Mã phiên: {session_id}")
        print(f"   - Học viên: {student_name} ({student_id})")
        print(f"   - Tổng thời gian làm bài: {total_duration} giây")
        print(f"   - Khoảng ngập ngừng lớn nhất: {features.get('mouse_idle_max', 0)}s")
        print(f"   - Tốc độ di chuột trung bình: {features.get('mouse_speed_mean', 0)} px/s")
        print(f"   - Số lần đổi ô thao tác: {features.get('selection_changes', 0)} lần")
        print(f"   - Số lỗi công thức phát hiện: {features.get('formula_errors', 0)}")
        print("   -> Toàn bộ dữ liệu đã nằm sẵn sàng trong MySQL!")
        print("   -> Bạn có thể kiểm tra trực tiếp trên React Dashboard hoặc xuất ra Supabase.")
        print("=" * 80)


def main():
    print_banner()

    lessons = list_available_lessons()

    parser = argparse.ArgumentParser(description="Chương trình thu thập dữ liệu học viên Excel offline tại trung tâm")
    parser.add_argument("--student-id", default=None, help="Mã học viên (VD: ST_VIET_01)")
    parser.add_argument("--name", default=None, help="Họ và tên học viên")
    parser.add_argument("--lesson", default=None, help="Mã hoặc tên bài tập (VD: 07 hoặc 08)")

    args = parser.parse_args()

    # Nhập thông tin nếu chưa truyền cờ
    student_id = args.student_id
    if not student_id:
        default_id = f"ST_{int(time.time()) % 10000:04d}"
        user_input = input(f"Nhập Mã học viên [Mặc định: {default_id}]: ").strip()
        student_id = user_input if user_input else default_id

    student_name = args.name
    if not student_name:
        default_name = f"Học viên {student_id}"
        user_input = input(f"Nhập Họ và tên học viên [Mặc định: {default_name}]: ").strip()
        student_name = user_input if user_input else default_name

    lesson_code = args.lesson
    if not lesson_code:
        print("\nDanh sách bài tập thực hành sẵn có:")
        for idx, f in enumerate(lessons, 1):
            print(f"   [{idx}] {f}")
        choice = input(f"Chọn bài tập thực hành (1-{len(lessons)}) [Mặc định: 3 - Bài 07]: ").strip()
        try:
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(lessons):
                lesson_code = lessons[choice_idx]
            else:
                lesson_code = "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx"
        except Exception:
            lesson_code = "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx"

    run_collection_session(student_id, student_name, lesson_code)


if __name__ == "__main__":
    main()
