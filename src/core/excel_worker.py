"""
Excel Observer Worker: Luồng xử lý bất đồng bộ (Dedicated Background QThread)
chuyên trách giao tiếp COM và vòng lặp Tác tử, giải phóng Main GUI Thread đạt 60 FPS.
"""

import time
import queue
from typing import Any, Dict, Optional
from PyQt6.QtCore import QThread, pyqtSignal
import pythoncom

from src.excel_mcp.agent_client import AITutorMCPAgent
from src.excel_mcp.server import excel_monitor


class ExcelObserverWorker(QThread):
    """
    Worker Thread chạy độc lập với Main GUI Thread:
    - Khởi tạo Single Threaded Apartment (STA) qua pythoncom.CoInitialize()
    - Lắng nghe COM Push Events từ Excel (< 5ms phản hồi)
    - Xử lý các yêu cầu từ giao diện qua Thread-safe Queue
    - Phát tín hiệu guidance_ready(dict) về Main GUI Thread để render
    """

    guidance_ready = pyqtSignal(dict)
    exercise_launched = pyqtSignal(dict)
    worker_error = pyqtSignal(str)

    def __init__(self, hesitation_threshold: float = 3.5, poll_interval_ms: int = 50, parent=None):
        super().__init__(parent)
        self.hesitation_threshold = hesitation_threshold
        self.poll_interval = poll_interval_ms / 1000.0  # chuyển sang giây (50ms)
        self._running = True
        self._action_queue = queue.Queue()
        self._event_triggered = False
        self.agent: Optional[AITutorMCPAgent] = None
        self._last_guidance_signature = None

    def stop(self):
        """Dừng worker thread an toàn."""
        self._running = False
        self.wait(2000)

    # =========================================================================
    # THREAD-SAFE ACTIONS (Được gọi từ Main GUI Thread)
    # =========================================================================

    def post_open_exercise(self, exercise_code: str):
        self._action_queue.put(("OPEN_EXERCISE", exercise_code))

    def post_request_hint(self):
        self._action_queue.put(("REQUEST_HINT", None))

    def post_repeat_instruction(self):
        self._action_queue.put(("REPEAT_INSTRUCTION", None))

    def post_toggle_pause(self):
        self._action_queue.put(("TOGGLE_PAUSE", None))

    def post_continue_step(self):
        self._action_queue.put(("CONTINUE_STEP", None))

    def post_submit_reflection(self, question: str, answer: str):
        self._action_queue.put(("SUBMIT_REFLECTION", (question, answer)))

    # =========================================================================
    # VÒNG LẶP NỘI TẠI TRONG LUỒNG WORKER (COM STA)
    # =========================================================================

    def _on_excel_com_event(self, event_name: str, *args):
        """Bắt sự kiện đẩy tức thời (Push Event) từ Excel COM Event Sink."""
        self._event_triggered = True

    def run(self):
        """Entry point của luồng Worker."""
        pythoncom.CoInitialize()
        try:
            # 1. Khởi tạo Agent bên trong STA Apartment của Worker Thread
            self.agent = AITutorMCPAgent(hesitation_threshold=self.hesitation_threshold)

            # 2. Đăng ký nhận sự kiện đẩy từ ExcelMonitor
            excel_monitor.register_event_callback(self._on_excel_com_event)

            last_step_time = time.perf_counter()

            # Phát thông tin khởi đầu
            initial_guidance = self.agent.runtime.last_guidance
            if initial_guidance:
                self.guidance_ready.emit(initial_guidance)

            while self._running:
                # A. Xử lý các yêu cầu thao tác từ GUI Thread
                while not self._action_queue.empty():
                    try:
                        action, payload = self._action_queue.get_nowait()
                        self._process_action(action, payload)
                    except queue.Empty:
                        break
                    except Exception as e:
                        self.worker_error.emit(str(e))

                # B. Bơm thông điệp COM (Pump Waiting Messages) để nhận event callbacks
                try:
                    pythoncom.PumpWaitingMessages()
                except Exception:
                    pass

                # C. Kiểm tra xem có cần thực hiện bước quan sát hay không
                now = time.perf_counter()
                time_elapsed = now - last_step_time
                should_step = self._event_triggered or (time_elapsed >= self.poll_interval)

                if should_step:
                    self._event_triggered = False
                    last_step_time = now
                    try:
                        guidance = self.agent.step()
                        if guidance:
                            sig = (
                                guidance.get("agent_status", ""),
                                guidance.get("step_title", ""),
                                guidance.get("hint_text", ""),
                                str(guidance.get("target_rect")),
                                guidance.get("badge_text", ""),
                                guidance.get("action_title", ""),
                                guidance.get("hint_level", 1),
                                round(guidance.get("mouse_speed", 0.0), -1),
                            )
                            if sig != self._last_guidance_signature or time_elapsed >= 0.2:
                                self._last_guidance_signature = sig
                                self.guidance_ready.emit(guidance)
                    except Exception:
                        pass

                # D. Nghỉ ngắn 15ms (vừa giữ CPU < 1%, vừa phản hồi < 15ms khi có event)
                self.msleep(15)

        finally:
            pythoncom.CoUninitialize()

    def _process_action(self, action: str, payload: Any):
        if not self.agent:
            return

        if action == "OPEN_EXERCISE":
            res = self.agent.set_exercise(payload)
            self.exercise_launched.emit(res)
            guidance = res.get("guidance")
            if guidance:
                self.guidance_ready.emit(guidance)

        elif action == "REQUEST_HINT":
            guidance = self.agent.request_next_hint()
            if guidance:
                self.guidance_ready.emit(guidance)

        elif action == "REPEAT_INSTRUCTION":
            guidance = self.agent.repeat_instruction()
            if guidance:
                self.guidance_ready.emit(guidance)

        elif action == "TOGGLE_PAUSE":
            guidance = self.agent.toggle_pause()
            if guidance:
                self.guidance_ready.emit(guidance)

        elif action == "CONTINUE_STEP":
            guidance = self.agent.continue_lesson()
            if guidance:
                self.guidance_ready.emit(guidance)

        elif action == "SUBMIT_REFLECTION":
            question, answer = payload
            self.agent.evaluate_student_reflection(question=question, answer=answer)
            guidance = self.agent.runtime.last_guidance
            if guidance:
                self.guidance_ready.emit(guidance)
