"""
Excel MCP Server: Máy chủ Giao thức Bối cảnh Mô hình (Model Context Protocol - MCP)
Cung cấp các công cụ (Tools) và tài nguyên (Resources) chuẩn hóa cho AI Tutor Agent
để giám sát, điều khiển và trích xuất dữ liệu từ Microsoft Excel theo thời gian thực.
"""

import os
import sys
from typing import Dict, Any, Optional, List
from mcp.server.mcpserver import MCPServer

# Đảm bảo đường dẫn import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.core.excel_monitor import ExcelMonitor
from src.core.mouse_tracker import MouseSpeedTracker
from src.core.state_evaluator import StateEvaluator

# Khởi tạo MCP Server chuẩn công nghiệp
mcp_server = MCPServer(
    name="excel-adaptive-tutor-mcp",
    version="1.0.0",
    description="Model Context Protocol Server for Excel Skills Intelligent Tutoring System"
)

# Khởi tạo các bộ điều phối phần cứng và ứng dụng
excel_monitor = ExcelMonitor()
mouse_tracker = MouseSpeedTracker(excel_monitor=excel_monitor)
state_evaluator = StateEvaluator()


# ==============================================================================
# MCP TOOLS: BỘ CÔNG CỤ CHUẨN HÓA CHO AI AGENT
# ==============================================================================

@mcp_server.tool(
    name="excel_get_cell_rect",
    description="Lấy tọa độ pixel màn hình chính xác (x, y, width, height) của một ô tính Excel bất kỳ, tự động bù trừ tỷ lệ zoom, cuộn trang và thanh Ribbon."
)
def excel_get_cell_rect(cell_address: str, sheet_name: str = "") -> Dict[str, Any]:
    """
    Truy vấn tọa độ pixel của một ô tính trên màn hình.
    :param cell_address: Địa chỉ ô (VD: 'C8', 'F7')
    :param sheet_name: Tên sheet (Tùy chọn, mặc định lấy sheet hiện tại)
    """
    cell_address = str(cell_address or "").strip().replace("$", "").upper()
    if not cell_address:
        return {
            "success": False,
            "cell_address": "",
            "error": "Địa chỉ ô đang trống. Vui lòng nhập địa chỉ như C8."
        }

    rect = excel_monitor.get_cell_rect_by_address(cell_address, sheet_name)
    if rect:
        x, y, w, h = rect
        return {
            "success": True,
            "cell_address": cell_address,
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "is_live_excel": True,
            "message": f"Đã bắt dính tọa độ ô {cell_address} từ Excel thực tế: ({x}, {y})"
        }
    return {
        "success": False,
        "cell_address": cell_address,
        "error": (
            f"Không thể xác định tọa độ hiển thị của ô {cell_address}. "
            "Hãy bảo đảm Excel đang mở, đúng sheet và ô đang nằm trong vùng nhìn thấy."
        )
    }


@mcp_server.tool(
    name="excel_get_active_state",
    description="Đọc toàn bộ trạng thái làm việc hiện tại của Excel: workbook, sheet, ô đang chọn, giá trị và định dạng ô."
)
def excel_get_active_state() -> Dict[str, Any]:
    """Lấy trạng thái tức thời của Excel."""
    state = excel_monitor.get_state()
    return {
        "connected": state.get("connected", False),
        "workbook": state.get("workbook", ""),
        "sheet": state.get("sheet", ""),
        "active_cell": state.get("cell_clean_address", ""),
        "cell_value": str(state.get("cell_value") or ""),
        "cell_format": state.get("cell_format", ""),
        "cell_rect": state.get("cell_rect"),
        "selection_address": state.get("selection_address", ""),
        "selection_rect": state.get("selection_rect"),
        "selection_rows": state.get("selection_rows", 1),
        "selection_columns": state.get("selection_columns", 1),
        "selection_area_count": state.get("selection_area_count", 1),
        "is_range_selection": state.get("is_range_selection", False),
        "ribbon_available": state.get("ribbon_available", False),
        "ribbon_tab_id": state.get("ribbon_tab_id", ""),
        "ribbon_tab_name": state.get("ribbon_tab_name", ""),
        "number_format_expanded": state.get("number_format_expanded", False),
        "number_format_focused": state.get("number_format_focused", False),
    }


@mcp_server.tool(
    name="mouse_get_telemetry",
    description="Đọc thông số tốc độ chuột thời gian thực (pixels/s), thời gian ngập ngừng liên tục và phân loại trạng thái nhận thức của học viên."
)
def mouse_get_telemetry() -> Dict[str, Any]:
    """Đo vận tốc chuột và nhận biết ngập ngừng/bế tắc."""
    data = mouse_tracker.update()
    return {
        "speed": data["speed"],
        "acceleration": data["acceleration"],
        "idle_duration": data["idle_duration"],
        "is_hesitating": data["is_hesitating"],
        "state_code": data["state_code"],
        "state_label": data["state_label"],
        "state_color": data["state_color"],
        "is_inside_excel": data["is_inside_excel"],
        "hovered_cell": data["hovered_cell"],
        "cell_value": str(data["cell_value"] or "")
    }


@mcp_server.tool(
    name="excel_read_range",
    description="Đọc ma trận giá trị và định dạng của một vùng ô tính (Range) để kiểm định toàn diện bài làm."
)
def excel_read_range(range_address: str, sheet_name: str = "") -> Dict[str, Any]:
    """Đọc dữ liệu vùng ô tính."""
    values = excel_monitor.get_range_values(sheet_name, range_address)
    formats = excel_monitor.get_range_formats(sheet_name, range_address)
    return {
        "range": range_address,
        "sheet": sheet_name,
        "values": values,
        "formats": formats
    }


@mcp_server.tool(
    name="excel_write_cell",
    description="Ghi dữ liệu (text/number/công thức) vào một ô tính cụ thể trong Excel qua giao thức MCP."
)
def excel_write_cell(cell_address: str, value: str, sheet_name: str = "") -> Dict[str, Any]:
    """Ghi trực tiếp vào ô Excel qua MCP."""
    success = excel_monitor.write_cell(cell_address, value, sheet_name)
    if success:
        return {
            "success": True,
            "cell_address": cell_address,
            "written_value": value,
            "sheet_name": sheet_name,
            "message": f"Đã ghi thành công '{value}' vào ô {cell_address} qua MCP!"
        }
    return {
        "success": False,
        "cell_address": cell_address,
        "error": f"Không thể ghi vào ô {cell_address}. Vui lòng kiểm tra Excel có đang mở không."
    }


@mcp_server.tool(
    name="excel_launch_exercise",
    description="Khởi chạy trực tiếp file bài tập thực hành Excel (Bài 07 hoặc Bài 08)."
)
def excel_launch_exercise(exercise_code: str) -> Dict[str, Any]:
    """Khởi chạy file bài tập và liên kết tự động."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "bài tập"))
    if exercise_code in ["07", "7"]:
        fpath = os.path.join(base_dir, "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx")
    elif exercise_code in ["08", "8"]:
        fpath = os.path.join(base_dir, "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu 10092026 (1).xlsx")
    else:
        return {"success": False, "error": f"Không tìm thấy bài tập mã '{exercise_code}'"}

    success = excel_monitor.launch_exercise(fpath)
    return {
        "success": success,
        "exercise_code": exercise_code,
        "file_path": fpath,
        "message": f"Đã mở file Bài {exercise_code} và kết nối Live Handle thành công." if success else "Không thể mở file Excel."
    }


@mcp_server.tool(
    name="pedagogy_evaluate_step",
    description="Đánh giá tính đúng đắn về mặt sư phạm của thao tác hiện tại và tự động sinh 3 cấp độ gợi ý (Tư duy, Công cụ, Khoanh vùng)."
)
def pedagogy_evaluate_step(exercise_id: str, cell_address: str, cell_value: str = "", cell_format: str = "") -> Dict[str, Any]:
    """Đánh giá logic bài tập và sinh gợi ý."""
    mock_state = {
        "connected": True,
        "workbook": "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx" if exercise_id == "BAI_07" else "Bài 08...",
        "sheet": "Bài 01" if exercise_id == "BAI_07" else "1. Thuc_Hanh_Tung_Buoc",
        "cell_clean_address": cell_address,
        "cell_value": cell_value,
        "cell_format": cell_format,
        "cell_rect": None
    }
    eval_res = state_evaluator.evaluate(mock_state, excel_monitor)
    return eval_res.to_dict()


@mcp_server.tool(
    name="ai_evaluate_reflection",
    description="Sử dụng Google Gemini 3.6 Flash để chấm điểm và đưa ra nhận xét sư phạm phản biện cho câu trả lời của học viên (Teachable Agent)."
)
def ai_evaluate_reflection(question: str, student_answer: str, context: str = "") -> Dict[str, Any]:
    """Chấm điểm câu trả lời giải thích của học viên bằng Gemini."""
    from src.ai.tutor_agent import TutorAgent
    agent = TutorAgent()
    feedback = agent.evaluate_reflection(question, student_answer, context)
    return {
        "success": True,
        "feedback": feedback,
        "question": question,
        "student_answer": student_answer
    }


# ==============================================================================
# MCP RESOURCES: TÀI NGUYÊN THÔNG TIN HỆ THỐNG
# ==============================================================================

@mcp_server.resource(
    uri="excel://system_status",
    name="Trạng Thái Hệ Thống Excel & Gia Sư",
    description="Cung cấp trạng thái kết nối và tiến trình bài học hiện hành."
)
def get_system_status() -> str:
    conn = "ĐÃ KẾT NỐI (Live)" if excel_monitor.excel_app else "CHƯA KẾT NỐI"
    return f"Trạng thái Excel: {conn} | Tọa độ chuẩn hóa: Bật | Protocol: Model Context Protocol 2.x"


if __name__ == "__main__":
    # Khởi chạy server qua giao thức chuẩn STDIO
    mcp_server.run(transport="stdio")
