"""
Gemini Key Manager: Quản lý hồ chứa API Key (Key Pool) cho Google Gemini.
Hỗ trợ tự động xoay vòng (Round-Robin), phát hiện quá tải (HTTP 429) và tự động chuyển sang key dự phòng.
"""

import os
import re
from typing import List, Optional


class GeminiKeyManager:
    """
    Quản lý danh sách các Gemini API Keys và tự động chuyển key khi gặp lỗi rate-limit.
    """
    def __init__(self, keys_file_path: Optional[str] = None):
        self.keys: List[str] = []
        self.current_idx = 0
        self.error_counts = {}

        if keys_file_path and os.path.exists(keys_file_path):
            self._load_from_keys_file(keys_file_path)
        else:
            # Tìm kiếm mặc định trong thư mục gốc
            default_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "keys.txt"))
            if os.path.exists(default_path):
                self._load_from_keys_file(default_path)

        # Kiểm tra biến môi trường
        env_key = os.environ.get("GEMINI_API_KEY")
        if env_key and env_key not in self.keys:
            self.keys.insert(0, env_key)

    def _load_from_keys_file(self, file_path: str):
        """Trích xuất tự động các key Gemini từ file keys.txt."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Bắt các key có định dạng của Google Gemini (AQ.Ab8RN6... hoặc AIzaSy...)
            matches = re.findall(r'(AQ\.Ab8RN6[a-zA-Z0-9_\-]+|AIzaSy[a-zA-Z0-9_\-]+)', content)
            # Loại bỏ trùng lặp và giữ nguyên thứ tự
            seen = set()
            for k in matches:
                clean_k = k.strip()
                if clean_k not in seen:
                    seen.add(clean_k)
                    self.keys.append(clean_k)
                    self.error_counts[clean_k] = 0

            # Ưu tiên đưa key chưa dùng (usageCount = 0) lên đầu
            unused_prefix = "AQ.Ab8RN6IAu"
            self.keys.sort(key=lambda x: 0 if x.startswith(unused_prefix) else 1)

        except Exception as e:
            print(f"[GeminiKeyManager] Lỗi đọc file keys: {e}")

    def get_current_key(self) -> str:
        """Lấy key đang hoạt động hiện tại."""
        if not self.keys:
            return ""
        return self.keys[self.current_idx]

    def get_masked_key(self) -> str:
        """Hiển thị key dạng che mờ bảo mật (VD: AQ.Ab...SsA)."""
        k = self.get_current_key()
        if len(k) > 12:
            return f"{k[:7]}...{k[-5:]}"
        return "NO_KEY"

    def rotate_next(self, reason: str = "") -> str:
        """Chuyển sang key tiếp theo trong hồ chứa."""
        if not self.keys:
            return ""
        old_k = self.get_current_key()
        self.error_counts[old_k] = self.error_counts.get(old_k, 0) + 1
        self.current_idx = (self.current_idx + 1) % len(self.keys)
        new_k = self.get_current_key()
        print(f"[GeminiKeyManager] Rotated API Key ({reason}). Active Key: {self.get_masked_key()} ({self.current_idx + 1}/{len(self.keys)})")
        return new_k

    def total_keys(self) -> int:
        return len(self.keys)
