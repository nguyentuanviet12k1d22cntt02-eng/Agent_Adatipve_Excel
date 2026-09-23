"""
Prompting Engine: Bộ điều phối gợi ý sư phạm phân cấp (Graduated Prompting)
và cơ chế Học bằng cách Giảng dạy (Teachable Agent).
"""

import time
from typing import Dict, Any, Optional
from src.core.state_evaluator import EvaluationResult


class PromptingEngine:
    def __init__(self, hesitation_threshold_seconds: float = 7.0):
        self.hesitation_threshold = hesitation_threshold_seconds
        self.current_hint_level = 1  # 1: Tư duy, 2: Công cụ, 3: Hành vi & Khoanh vùng
        self.last_state_signature = ""
        self.state_start_time = time.time()
        self.last_evaluation: Optional[EvaluationResult] = None
        self.teachable_active = False
        self.mastery_counts = {}  # {concept: success_count} for fading

    def _get_state_signature(self, eval_res: EvaluationResult, state: Dict[str, Any]) -> str:
        """Tạo chuỗi chữ ký đại diện cho trạng thái hiện tại để nhận biết sự thay đổi."""
        return f"{eval_res.exercise_id}|{eval_res.step_title}|{eval_res.error_type}|{state.get('cell_clean_address')}|{state.get('cell_value')}|{state.get('cell_format')}"

    def update(self, eval_res: EvaluationResult, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cập nhật trạng thái mới nhất từ Evaluator và quyết định:
        - Mức gợi ý hiển thị (Level 1, 2, hay 3)
        - Có kích hoạt khoanh vùng trên Overlay không (Level 3)
        - Có kích hoạt câu hỏi phản biện Teachable Agent không
        """
        now = time.time()
        sig = self._get_state_signature(eval_res, state)

        # Nếu trạng thái thay đổi (học viên chuyển ô hoặc gõ gì đó mới)
        if sig != self.last_state_signature:
            self.last_state_signature = sig
            self.state_start_time = now
            self.current_hint_level = 1  # Bắt đầu lại từ Mức 1
            self.teachable_active = False

            # Nếu vừa hoàn thành đúng một bước
            if eval_res.is_correct and eval_res.teachable_question:
                self.teachable_active = True
        else:
            # Nếu học viên giữ nguyên trạng thái (đang suy nghĩ hoặc ngập ngừng)
            elapsed = now - self.state_start_time
            if not eval_res.is_correct and not self.teachable_active:
                if elapsed > self.hesitation_threshold * 2:
                    self.current_hint_level = 3  # Đã chờ lâu -> Bật khoanh vùng trực quan
                elif elapsed > self.hesitation_threshold:
                    self.current_hint_level = 2  # Ngập ngừng -> Gợi ý công cụ

        self.last_evaluation = eval_res

        # Xác định nội dung phản hồi cho giao diện
        active_hint_text = ""
        show_overlay_rect = None

        if self.teachable_active:
            mode_badge = "HỌC TRÒ HỎI (TEACHABLE AGENT)"
            active_hint_text = eval_res.teachable_question
        elif eval_res.is_correct:
            mode_badge = "XUẤT SẮC"
            active_hint_text = eval_res.hint_level_1
        else:
            if self.current_hint_level == 1:
                mode_badge = "MỨC 1: ĐỊNH HƯỚNG TƯ DUY"
                active_hint_text = eval_res.hint_level_1
            elif self.current_hint_level == 2:
                mode_badge = "MỨC 2: CHỈ DẪN CÔNG CỤ"
                active_hint_text = eval_res.hint_level_2 or eval_res.hint_level_1
            elif self.current_hint_level == 3:
                mode_badge = "MỨC 3: KHOANH VÙNG TRỰC QUAN"
                active_hint_text = eval_res.hint_level_3 or eval_res.hint_level_2
                # Ở mức 3, gửi tọa độ cho lớp phủ Overlay
                show_overlay_rect = eval_res.target_rect

        return {
            "mode_badge": mode_badge,
            "hint_level": self.current_hint_level,
            "hint_text": active_hint_text,
            "step_title": eval_res.step_title,
            "is_correct": eval_res.is_correct,
            "error_type": eval_res.error_type,
            "target_rect": show_overlay_rect,
            "teachable_active": self.teachable_active,
            "target_cells": eval_res.target_cells,
        }

    def request_next_hint(self):
        """Học viên chủ động bấm nút 'Gợi ý tiếp'."""
        if self.current_hint_level < 3:
            self.current_hint_level += 1
            self.state_start_time = time.time()  # Reset timer
