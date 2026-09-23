"""
Tutor Agent: Tích hợp mô hình ngôn ngữ lớn Google Gemini (Gemini 3.6 Flash)
thông qua bộ quản lý xoay vòng API Keys (GeminiKeyManager).
Sinh câu hỏi kích hoạt tư duy (Socratic Hint) và đánh giá phản biện (Teachable Agent).
Tự động fallback sang phân tích quy tắc sư phạm cục bộ nếu không có mạng.
"""

import os
import json
import requests
from typing import Dict, Any, Optional
from src.ai.key_manager import GeminiKeyManager


class TutorAgent:
    def __init__(self, key_manager: Optional[GeminiKeyManager] = None):
        self.key_manager = key_manager or GeminiKeyManager()
        self.model_name = "gemini-3.6-flash"

    def _call_gemini(self, system_instruction: str, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Gọi API Google Gemini với cơ chế tự động xoay vòng key khi quá tải."""
        if self.key_manager.total_keys() == 0:
            return None

        payload = {
            "contents": [{"parts": [{"text": f"{system_instruction}\n\n{prompt}"}]}],
            "generationConfig": {"temperature": 0.35, "maxOutputTokens": 200}
        }

        for attempt in range(max_retries):
            current_key = self.key_manager.get_current_key()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={current_key}"
            try:
                res = requests.post(url, json=payload, timeout=6)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        return text
                elif res.status_code in [429, 503]:
                    # Quá tải quota -> Tự động xoay key tiếp theo
                    self.key_manager.rotate_next(f"HTTP {res.status_code} Quota/Overload")
                else:
                    print(f"[TutorAgent] Gemini API Error {res.status_code}: {res.text[:120]}")
                    self.key_manager.rotate_next(f"HTTP {res.status_code}")
            except Exception as e:
                print(f"[TutorAgent] Request timeout/network error: {e}")
                self.key_manager.rotate_next("Timeout")

        return None

    def evaluate_reflection(self, question: str, student_answer: str, context: str = "") -> str:
        """
        Đánh giá câu trả lời giải thích của học viên cho câu hỏi của Teachable Agent.
        """
        if not student_answer.strip():
            return "Hãy thử gõ câu trả lời theo cách hiểu của bạn nhé!"

        sys_inst = (
            "Bạn là Gia Sư AI Excel trong một hệ thống sư phạm tương tác thông minh. "
            "Học viên vừa trả lời câu hỏi giải thích bản chất (Teachable Agent). "
            "Nhiệm vụ của bạn: "
            "1. Nhận xét xem câu trả lời của học viên đã nắm đúng bản chất chưa (khen ngợi nếu đúng, sửa nhẹ nhàng nếu chưa chuẩn). "
            "2. Luôn trả lời bằng TIẾNG VIỆT thân thiện, ấm áp, khích lệ, súc tích trong 2-3 câu."
        )

        user_prompt = (
            f"Bối cảnh bài học: {context}\n"
            f"Câu hỏi của AI: {question}\n"
            f"Câu trả lời của học viên: {student_answer}\n\n"
            f"Hãy đưa ra lời nhận xét sư phạm:"
        )

        gemini_res = self._call_gemini(sys_inst, user_prompt)
        if gemini_res:
            return gemini_res

        # Fallback phân tích thông minh cục bộ (Offline Mode)
        ans_lower = student_answer.lower()

        # Kiểm tra ngữ cảnh Bài 08: Mất số 0 / Text / Number
        if any(k in question.lower() for k in ["số 0", "text", "toán học", "sđt", "cccd"]):
            if any(k in ans_lower for k in ["mất", "xóa", "không có nghĩa", "vô nghĩa", "text", "chữ", "ký tự", "số học"]):
                return "🌟 Chính xác tuyệt đối! Bạn giải thích rất chuẩn: Trong toán học số 0 ở đầu không có giá trị nên Excel sẽ tự bỏ đi, vì vậy SĐT/CCCD phải định dạng Text."
            else:
                return "💡 Ý của bạn khá thú vị! Hãy nhớ thêm rằng: Excel coi ô là Number thì số 0 ở đầu sẽ bị coi là vô nghĩa, chỉ khi ở dạng Text thì số 0 mới được giữ nguyên nhé!"

        # Kiểm tra ngữ cảnh Bài 07: Địa chỉ ô / Cột / Dòng
        if any(k in question.lower() for k in ["b8", "b7", "cột", "dòng", "tên ô", "địa chỉ"]):
            if any(k in ans_lower for k in ["cột trước", "chữ trước", "dòng sau", "giao", "bản đồ", "tọa độ"]):
                return "🌟 Rất chuẩn! Tọa độ ô luôn là [Tên Cột][Số Dòng]. Bạn nắm bài rất chắc đấy!"
            else:
                return "💡 Bạn hãy nhớ nguyên tắc cốt lõi: Tên Cột (Chữ cái) luôn luôn đi trước, Số Dòng (Con số) đi sau để tạo thành địa chỉ ô duy nhất nhé!"

        return "👍 Cảm ơn bạn đã chia sẻ câu trả lời! Hãy tiếp tục thực hành các ô tiếp theo nhé!"

    def generate_socratic_hint(self, step_title: str, current_issue: str, hint_level: int) -> str:
        """Sinh gợi ý sư phạm gợi mở theo phương pháp Socratic qua Gemini."""
        sys_inst = (
            "Bạn là Gia Sư AI Excel thông minh. Học viên đang thực hành trên Microsoft Excel và đang ngập ngừng hoặc gặp khó khăn. "
            "Nhiệm vụ: Tạo một gợi ý sư phạm ngắn gọn (1-2 câu). "
            "- Mức 1: Đặt câu hỏi gợi mở tư duy, không đưa đáp án. "
            "- Mức 2: Nhắc lại công cụ hoặc quy ước chuẩn. "
            "- Mức 3: Chỉ dẫn hành vi cụ thể cần làm."
        )

        prompt = (
            f"Bước học: {step_title}\n"
            f"Vấn đề hiện tại: {current_issue}\n"
            f"Cấp độ gợi ý yêu cầu: Mức {hint_level}\n"
            f"Nội dung gợi ý:"
        )

        res = self._call_gemini(sys_inst, prompt)
        return res or ""
