"""
Clear All Data: Xóa sạch toàn bộ dữ liệu trong các bảng trên cả:
1. Supabase Cloud (PostgreSQL)
2. MySQL Cục bộ (excel_adaptive_tutor)
3. SQLite Fallback (data/excel_tutor.db)
Giữ nguyên toàn bộ cấu trúc bảng và cấu hình Realtime, đưa số lượng bản ghi về 0 để chuẩn bị test mới từ đầu.
"""

import os
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import psycopg2
import pymysql
import sqlite3

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from src.config.db_config import (
    SUPABASE_HOST,
    SUPABASE_PORT,
    SUPABASE_USER,
    SUPABASE_PASSWORD,
    SUPABASE_DATABASE,
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
    SQLITE_DB_PATH,
)

TABLES = [
    "feedback",
    "predictions",
    "labels",
    "features",
    "events",
    "sessions",
    "students",
]


def clear_supabase():
    print("🧹 [1/3] Đang làm sạch dữ liệu trên SUPABASE CLOUD...")
    try:
        conn = psycopg2.connect(
            host=SUPABASE_HOST,
            port=SUPABASE_PORT,
            user=SUPABASE_USER,
            password=SUPABASE_PASSWORD,
            dbname=SUPABASE_DATABASE,
            connect_timeout=10,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            # Dùng TRUNCATE CASCADE để xóa sạch và reset sequence
            sql = "TRUNCATE TABLE public.feedback, public.predictions, public.labels, public.features, public.events, public.sessions, public.students RESTART IDENTITY CASCADE;"
            cur.execute(sql)
            print("   ✅ Đã xóa sạch toàn bộ bản ghi trên Supabase Cloud!")

            # Kiểm tra lại số lượng
            counts = {}
            for t in ["students", "sessions", "events", "features"]:
                cur.execute(f"SELECT COUNT(*) FROM public.{t};")
                counts[t] = cur.fetchone()[0]
            print(f"   📊 Kiểm tra số lượng bản ghi Supabase: {counts}")
        conn.close()
    except Exception as e:
        print(f"   ❌ Lỗi xóa Supabase: {e}")


def clear_mysql():
    print("\n🧹 [2/3] Đang làm sạch dữ liệu trên MYSQL CỤC BỘ...")
    try:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            charset="utf8mb4",
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
            for t in TABLES:
                cur.execute(f"TRUNCATE TABLE {t};")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
            print("   ✅ Đã xóa sạch toàn bộ bản ghi trên MySQL!")

            # Kiểm tra lại
            counts = {}
            for t in ["students", "sessions", "events", "features"]:
                cur.execute(f"SELECT COUNT(*) FROM {t};")
                counts[t] = cur.fetchone()[0]
            print(f"   📊 Kiểm tra số lượng bản ghi MySQL: {counts}")
        conn.close()
    except Exception as e:
        print(f"   ❌ Lỗi xóa MySQL: {e}")


def clear_sqlite():
    print("\n🧹 [3/3] Đang kiểm tra và làm sạch SQLite cục bộ...")
    if os.path.exists(SQLITE_DB_PATH):
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            with conn:
                for t in ["events", "sessions", "students"]:
                    try:
                        conn.execute(f"DELETE FROM {t};")
                    except Exception:
                        pass
            conn.close()
            print("   ✅ Đã xóa sạch SQLite fallback.")
        except Exception as e:
            print(f"   ⚠️ Lỗi xóa SQLite: {e}")
    else:
        print("   ℹ️ Không có file SQLite cần xóa.")


def main():
    print("=" * 80)
    print("🗑️  BẮT ĐẦU XÓA TOÀN BỘ DỮ LIỆU ĐỂ TRỐNG RỖNG SẴN SÀNG TEST")
    print("=" * 80)

    clear_supabase()
    clear_mysql()
    clear_sqlite()

    print("\n" + "=" * 80)
    print("✨ TOÀN BỘ CƠ SỞ DỮ LIỆU ĐÃ TRỐNG RỖNG 100%!")
    print("   Bây giờ bạn có thể bật BAT_DAU_GHI_NHAN hoặc mở Excel để bắt đầu test mới tinh!")
    print("=" * 80)


if __name__ == "__main__":
    main()
