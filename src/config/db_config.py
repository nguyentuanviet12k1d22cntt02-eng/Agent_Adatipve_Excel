"""
Database Configuration: Cấu hình kết nối Supabase Cloud (chính), MySQL (cục bộ) và SQLite dự phòng.
Đọc cấu hình từ biến môi trường hoặc cấu hình mặc định.
"""

import os

# Cấu hình Supabase Cloud (PostgreSQL + Realtime)
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cxjhnsvzacqlfbpcnkrh.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_publishable_F_v1G9WDNfWUyL61P5j1HA_iB5pdERf")
SUPABASE_HOST = os.getenv("SUPABASE_HOST", "aws-0-ap-northeast-1.pooler.supabase.com")
SUPABASE_PORT = int(os.getenv("SUPABASE_PORT", 5432))
SUPABASE_USER = os.getenv("SUPABASE_USER", "postgres.cxjhnsvzacqlfbpcnkrh")
SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD", "Viet.10092004@")
SUPABASE_DATABASE = os.getenv("SUPABASE_DATABASE", "postgres")
USE_SUPABASE = os.getenv("USE_SUPABASE", "true").lower() in ("true", "1")

# Cấu hình MySQL cục bộ
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "10092004")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "excel_adaptive_tutor")

# Cấu hình SQLite fallback
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "data", "excel_tutor.db")
