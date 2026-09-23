"""
FastAPI Server: Cung cấp RESTful API cho ReactJS Dashboard
Kết nối trực tiếp tới MySQL Database (excel_adaptive_tutor) để hiển thị
dòng sự kiện telemetry, phiên học, nhãn nhận thức và dự đoán ML theo Phase 1.
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymysql

from src.config.db_config import (
    MYSQL_HOST,
    MYSQL_PORT,
    MYSQL_USER,
    MYSQL_PASSWORD,
    MYSQL_DATABASE,
)
from src.data_collection.db_manager import DatabaseManager

app = FastAPI(
    title="Excel Adaptive Tutor - Telemetry & ML API",
    description="API cung cấp dữ liệu cho ReactJS Dashboard (Phase 1 Data Collection)",
    version="1.0.0",
)

# Kích hoạt CORS cho React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db_manager = DatabaseManager()


def get_mysql_conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=3,
    )


def serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Chuyển đổi kiểu dữ liệu datetime hoặc json trong row để trả về JSON an toàn."""
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, (dict, list)):
            out[k] = v
        elif k == "metadata" and isinstance(v, str):
            try:
                out[k] = json.loads(v)
            except Exception:
                out[k] = v
        else:
            out[k] = v
    return out


# ==============================================================================
# 1. SYSTEM HEALTH & METRICS
# ==============================================================================


@app.get("/api/health")
def get_health():
    """Kiểm tra trạng thái kết nối MySQL và thông số hệ thống."""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION() AS version;")
            db_ver = cur.fetchone()["version"]
            cur.execute("SHOW TABLES;")
            tables = [list(r.values())[0] for r in cur.fetchall()]
        conn.close()
        return {
            "status": "online",
            "database_engine": "MySQL",
            "mysql_host": MYSQL_HOST,
            "mysql_port": MYSQL_PORT,
            "database_name": MYSQL_DATABASE,
            "server_version": db_ver,
            "tables": tables,
            "timestamp": time.time(),
        }
    except Exception as e:
        return {
            "status": "degraded",
            "database_engine": "SQLite Fallback",
            "error": str(e),
            "timestamp": time.time(),
        }


@app.get("/api/stats")
def get_stats():
    """Lấy tổng hợp chỉ số toàn hệ thống (Học viên, phiên, sự kiện, cảnh báo)."""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total_students FROM students;")
            total_students = cur.fetchone()["total_students"]

            cur.execute("SELECT COUNT(*) AS total_sessions FROM sessions;")
            total_sessions = cur.fetchone()["total_sessions"]

            cur.execute("SELECT COUNT(*) AS total_events FROM events;")
            total_events = cur.fetchone()["total_events"]

            cur.execute(
                "SELECT COUNT(*) AS active_sessions FROM sessions WHERE status = 'IN_PROGRESS';"
            )
            active_sessions = cur.fetchone()["active_sessions"]

            cur.execute(
                "SELECT COUNT(*) AS completed_sessions FROM sessions WHERE status = 'COMPLETED';"
            )
            completed_sessions = cur.fetchone()["completed_sessions"]

            cur.execute(
                "SELECT COUNT(*) AS hesitation_events FROM events WHERE event_type LIKE '%HESITATION%' OR event_type LIKE '%ERRATIC%';"
            )
            hesitation_events = cur.fetchone()["hesitation_events"]

            cur.execute(
                "SELECT COUNT(*) AS formula_errors FROM events WHERE event_type = 'FORMULA_ENTRY' AND (metadata LIKE '%error%' OR metadata LIKE '%#%');"
            )
            formula_errors = cur.fetchone()["formula_errors"]

        conn.close()
        return {
            "total_students": total_students,
            "total_sessions": total_sessions,
            "total_events": total_events,
            "active_sessions": active_sessions,
            "completed_sessions": completed_sessions,
            "hesitation_events": hesitation_events,
            "formula_errors": formula_errors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# 2. STUDENTS & SESSIONS
# ==============================================================================


@app.get("/api/students")
def get_students():
    """Danh sách học viên đã ghi danh."""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT student_id, name, email, created_at FROM students ORDER BY created_at DESC;")
            rows = [serialize_row(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
def get_sessions():
    """Danh sách các phiên học kèm thông tin học viên và số lượng sự kiện tương tác."""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cur:
            sql = """
            SELECT 
                s.session_id,
                s.student_id,
                st.name AS student_name,
                st.email AS student_email,
                s.lesson_id,
                s.started_at,
                s.ended_at,
                s.status,
                s.total_steps,
                s.completed_steps,
                COUNT(e.id) AS event_count
            FROM sessions s
            LEFT JOIN students st ON s.student_id = st.student_id
            LEFT JOIN events e ON s.session_id = e.session_id
            GROUP BY s.session_id
            ORDER BY s.started_at DESC;
            """
            cur.execute(sql)
            rows = [serialize_row(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
def get_session_detail(session_id: str):
    """Chi tiết một phiên học cụ thể."""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cur:
            sql = """
            SELECT 
                s.*,
                st.name AS student_name,
                st.email AS student_email
            FROM sessions s
            LEFT JOIN students st ON s.student_id = st.student_id
            WHERE s.session_id = %s;
            """
            cur.execute(sql, (session_id,))
            row = cur.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên học.")
        return serialize_row(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# 3. TELEMETRY EVENTS TIMELINE (PHASE 1 SENSORS)
# ==============================================================================


@app.get("/api/sessions/{session_id}/events")
def get_session_events(
    session_id: str,
    event_type: Optional[str] = Query(None, description="Lọc theo loại sự kiện"),
    limit: int = Query(200, description="Giới hạn số lượng sự kiện"),
):
    """Lấy danh sách dòng sự kiện tương tác thô của phiên học."""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cur:
            if event_type:
                sql = """
                SELECT id, session_id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata
                FROM events
                WHERE session_id = %s AND event_type = %s
                ORDER BY id ASC
                LIMIT %s;
                """
                cur.execute(sql, (session_id, event_type, limit))
            else:
                sql = """
                SELECT id, session_id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata
                FROM events
                WHERE session_id = %s
                ORDER BY id ASC
                LIMIT %s;
                """
                cur.execute(sql, (session_id, limit))
            rows = [serialize_row(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# 4. FEATURES & PREDICTIONS & FEEDBACK
# ==============================================================================


@app.get("/api/sessions/{session_id}/features")
def get_session_features(session_id: str):
    """Lấy các vector đặc trưng hành vi (Features) tính toán cho từng bước."""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cur:
            sql = "SELECT * FROM features WHERE session_id = %s ORDER BY step_index ASC;"
            cur.execute(sql, (session_id,))
            rows = [serialize_row(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/predictions")
def get_session_predictions(session_id: str):
    """Lấy lịch sử dự đoán trạng thái nhận thức của ML (Normal, Hesitating, Stuck...)."""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cur:
            sql = "SELECT * FROM predictions WHERE session_id = %s ORDER BY timestamp ASC;"
            cur.execute(sql, (session_id,))
            rows = [serialize_row(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/feedback")
def get_session_feedback(session_id: str):
    """Lấy lịch sử phản hồi và hỗ trợ thích ứng của AI Agent."""
    try:
        conn = get_mysql_conn()
        with conn.cursor() as cur:
            sql = "SELECT * FROM feedback WHERE session_id = %s ORDER BY timestamp ASC;"
            cur.execute(sql, (session_id,))
            rows = [serialize_row(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# 5. REALTIME EVENT SIMULATION (TESTING / DEMO PURPOSE)
# ==============================================================================


class SimulateEventPayload(BaseModel):
    event_type: str
    cell: Optional[str] = "C5"
    step_index: Optional[int] = 1
    metadata: Optional[Dict[str, Any]] = None


@app.post("/api/sessions/{session_id}/simulate-event")
def simulate_event(session_id: str, payload: SimulateEventPayload):
    """
    Ghi nhận một sự kiện mô phỏng từ giao diện trực tiếp vào MySQL.
    Giúp người dùng kiểm tra tức thì khả năng bắt sự kiện realtime.
    """
    try:
        now_ts = time.time()
        now_iso = datetime.now().isoformat()
        meta = payload.metadata or {}

        # Nếu là hesitation, tự sinh dữ liệu độ trễ
        if "HESITATION" in payload.event_type and "hesitation_duration_sec" not in meta:
            meta["hesitation_duration_sec"] = 4.25
            meta["status"] = "PROLONGED_PAUSE"

        conn = get_mysql_conn()
        with conn.cursor() as cur:
            # Kiểm tra session tồn tại
            cur.execute("SELECT lesson_id FROM sessions WHERE session_id = %s;", (session_id,))
            ses = cur.fetchone()
            lesson_id = ses["lesson_id"] if ses else "BAI_DEMO"

            sql = """
            INSERT INTO events (session_id, timestamp, iso_time, event_type, lesson_id, step_index, cell, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """
            cur.execute(
                sql,
                (
                    session_id,
                    now_ts,
                    now_iso,
                    payload.event_type,
                    lesson_id,
                    payload.step_index,
                    payload.cell,
                    json.dumps(meta, ensure_ascii=False),
                ),
            )
        conn.close()

        return {
            "status": "success",
            "message": f"Đã ghi nhận sự kiện {payload.event_type} vào MySQL thành công!",
            "session_id": session_id,
            "timestamp": now_iso,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
