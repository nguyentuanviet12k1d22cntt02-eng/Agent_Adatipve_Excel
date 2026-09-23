"""
Database Configuration: Cấu hình kết nối MySQL và SQLite dự phòng.
Đọc cấu hình từ biến môi trường hoặc file .env cục bộ.
"""

import os

# Cấu hình MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "10092004")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "excel_adaptive_tutor")

# Cấu hình SQLite fallback
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "data", "excel_tutor.db")
