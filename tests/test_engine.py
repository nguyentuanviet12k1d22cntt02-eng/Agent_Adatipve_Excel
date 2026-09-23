"""
Unit Test & Simulator: Kiểm tra tính đúng đắn của logic Sư phạm,
Đánh giá trạng thái và Sinh gợi ý cho Bài 07 & Bài 08.
"""

import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.state_evaluator import StateEvaluator, EvaluationResult
from src.core.prompting_engine import PromptingEngine
from src.ai.tutor_agent import TutorAgent


class MockExcelMonitor:
    def get_range_values(self, sheet, range_addr):
        return [["B7", "B", "7", "1988"]]


def test_evaluator_bai_07():
    print("=== TEST BÀI 07 ===")
    evaluator = StateEvaluator()
    engine = PromptingEngine(hesitation_threshold_seconds=2.0)
    mock_mon = MockExcelMonitor()

    # Tình huống 1: Học viên nhập sai cú pháp đảo ngược "8B" tại ô C8
    state_reversed = {
        "connected": True,
        "workbook": "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx",
        "sheet": "Bài 01",
        "cell_clean_address": "C8",
        "cell_value": "8B",
        "cell_format": "General",
        "cell_rect": (400, 300, 60, 25),
    }
    res = evaluator.evaluate(state_reversed, mock_mon)
    print("1. Phát hiện lỗi đảo ngược:", res.error_type == "REVERSED_ADDRESS")
    assert res.error_type == "REVERSED_ADDRESS"
    print("   Gợi ý Mức 1:", res.hint_level_1)

    info = engine.update(res, state_reversed)
    print("   Badge hiển thị:", info["mode_badge"])
    assert "MỨC 1" in info["mode_badge"]

    # Tình huống 2: Học viên sửa đúng "B8"
    state_correct = {
        "connected": True,
        "workbook": "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx",
        "sheet": "Bài 01",
        "cell_clean_address": "C8",
        "cell_value": "B8",
        "cell_format": "General",
        "cell_rect": (400, 300, 60, 25),
    }
    res_corr = evaluator.evaluate(state_correct, mock_mon)
    print("2. Đánh giá kết quả đúng:", res_corr.is_correct)
    assert res_corr.is_correct is True
    info_corr = engine.update(res_corr, state_correct)
    print("   Kích hoạt Teachable Agent:", info_corr["teachable_active"])
    assert info_corr["teachable_active"] is True
    print("   Câu hỏi phản biện:", info_corr["hint_text"])


def test_evaluator_bai_08():
    print("\n=== TEST BÀI 08 ===")
    evaluator = StateEvaluator()
    mock_mon = MockExcelMonitor()

    # Tình huống: Học viên gõ số điện thoại khi chưa định dạng Text -> mất số 0
    state_lost_zero = {
        "connected": True,
        "workbook": "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx",
        "sheet": "1. Thuc_Hanh_Tung_Buoc",
        "cell_clean_address": "F7",
        "cell_value": "908123456",  # Thiếu số 0
        "cell_format": "General",
        "cell_rect": (550, 320, 90, 25),
    }
    res = evaluator.evaluate(state_lost_zero, mock_mon)
    print("1. Phát hiện lỗi mất số 0:", res.error_type == "MISSING_LEADING_ZERO")
    assert res.error_type == "MISSING_LEADING_ZERO"
    print("   Gợi ý Mức 1:", res.hint_level_1)
    print("   Gợi ý Mức 3 (khoanh vùng):", res.hint_level_3)


def test_tutor_agent_reflection():
    print("\n=== TEST TUTOR AGENT REFLECTION ===")
    agent = TutorAgent()  # Offline mode fallback
    q = "Tại sao trong số điện thoại số 0 ở đầu lại bắt buộc phải giữ và phải chọn Text?"
    ans = "Vì nếu để số học thì số 0 ở đầu sẽ bị mất"
    feedback = agent.evaluate_reflection(q, ans)
    print("Nhận xét của AI:", feedback)
    assert "Chính xác" in feedback or "chuẩn" in feedback


if __name__ == "__main__":
    test_evaluator_bai_07()
    test_evaluator_bai_08()
    test_tutor_agent_reflection()
    print("\n✅ TẤT CẢ UNIT TESTS ĐỀU ĐÃ VƯỢT QUA!")
