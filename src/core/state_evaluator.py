"""
State Evaluator: Đánh giá trạng thái thao tác của học viên trên Bài 07 và Bài 08.
Xác định lỗi sai (Buggy States), mức độ hoàn thành và sinh các mức gợi ý sư phạm.
"""

from typing import Dict, Any, Optional, List


class EvaluationResult:
    def __init__(
        self,
        exercise_id: str,
        step_title: str,
        is_correct: bool,
        error_type: Optional[str] = None,
        target_cells: Optional[List[str]] = None,
        target_rect: Optional[tuple] = None,
        hint_level_1: str = "",
        hint_level_2: str = "",
        hint_level_3: str = "",
        teachable_question: str = "",
        completion_percent: float = 0.0,
    ):
        self.exercise_id = exercise_id
        self.step_title = step_title
        self.is_correct = is_correct
        self.error_type = error_type
        self.target_cells = target_cells or []
        self.target_rect = target_rect
        self.hint_level_1 = hint_level_1
        self.hint_level_2 = hint_level_2
        self.hint_level_3 = hint_level_3
        self.teachable_question = teachable_question
        self.completion_percent = completion_percent

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exercise_id": self.exercise_id,
            "step_title": self.step_title,
            "is_correct": self.is_correct,
            "error_type": self.error_type,
            "target_cells": self.target_cells,
            "target_rect": self.target_rect,
            "hint_level_1": self.hint_level_1,
            "hint_level_2": self.hint_level_2,
            "hint_level_3": self.hint_level_3,
            "teachable_question": self.teachable_question,
            "completion_percent": self.completion_percent,
        }


class StateEvaluator:
    def __init__(self):
        pass

    def identify_exercise(self, workbook_name: str) -> Optional[str]:
        """Xác định bài tập đang mở dựa trên tên file."""
        wb_lower = workbook_name.lower()
        if "bài 07" in wb_lower or "bai 07" in wb_lower or "địa chỉ ô" in wb_lower or "dia chi o" in wb_lower:
            return "BAI_07"
        if "bài 08" in wb_lower or "bai 08" in wb_lower or "nhập dữ liệu" in wb_lower or "nhap du lieu" in wb_lower:
            return "BAI_08"
        return None

    def evaluate(self, state: Dict[str, Any], excel_monitor) -> EvaluationResult:
        """Đánh giá toàn diện trạng thái hiện tại."""
        if not state.get("connected"):
            return EvaluationResult(
                exercise_id="NONE",
                step_title="Chưa kết nối Excel",
                is_correct=False,
                hint_level_1="Bạn hãy mở Microsoft Excel và mở file Bài 07 hoặc Bài 08 lên nhé!",
                hint_level_2="Bấm nút 'Mở Bài 07' hoặc 'Mở Bài 08' trên giao diện Gia Sư AI.",
            )

        wb_name = state.get("workbook", "")
        exercise_id = self.identify_exercise(wb_name)

        if exercise_id == "BAI_07":
            return self._evaluate_bai_07(state, excel_monitor)
        elif exercise_id == "BAI_08":
            return self._evaluate_bai_08(state, excel_monitor)
        else:
            return EvaluationResult(
                exercise_id="UNKNOWN",
                step_title="Chưa nhận diện bài tập",
                is_correct=False,
                hint_level_1=f"Đang mở file '{wb_name}'. Gia Sư AI hiện hỗ trợ kiểm định chuyên sâu cho Bài 07 và Bài 08.",
                hint_level_2="Vui lòng mở file 'Bài 07. Các thao tác cơ bản với địa chỉ ô' hoặc 'Bài 08...'",
            )

    # -------------------------------------------------------------
    # ĐÁNH GIÁ BÀI 07: THAO TÁC VỚI ĐỊA CHỈ Ô
    # -------------------------------------------------------------
    def _evaluate_bai_07(self, state: Dict[str, Any], excel_monitor) -> EvaluationResult:
        sheet = state.get("sheet", "")
        active_cell = state.get("cell_clean_address", "")
        cell_val = str(state.get("cell_value") or "").strip()
        cell_rect = state.get("cell_rect")

        # Đọc dữ liệu vùng bảng mẫu sheet Bài 01
        data_col = excel_monitor.get_range_values(sheet, "B6:F9")
        data_row = excel_monitor.get_range_values(sheet, "B12:E16")

        # Kiểm tra hoàn thành bảng 1 (cột C8:F9)
        # Bảng 1:
        # Row 8: B8="Rồng", C8="B8", D8="B", E8="8", F8="Rồng"
        # Row 9: B9="38", C9="B9", D9="B", E9="9", F9="38"
        total_cells_p1 = 8
        correct_cells_p1 = 0

        # Kiểm tra ô học viên đang thao tác hoặc vừa nhập
        if active_cell in ["C8", "C9"]:
            expected = active_cell.replace("C", "B")  # B8 hoặc B9
            if cell_val:
                # Bắt lỗi đảo ngược (VD: gõ 8B thay vì B8)
                if cell_val.upper() in ["8B", "9B"]:
                    return EvaluationResult(
                        exercise_id="BAI_07",
                        step_title="Sai quy ước gọi tên địa chỉ ô",
                        is_correct=False,
                        error_type="REVERSED_ADDRESS",
                        target_cells=[active_cell],
                        target_rect=cell_rect,
                        hint_level_1="Tên của một ô tính trong Excel bắt đầu bằng Tên Cột (Chữ cái) hay Số Dòng (Con số) trước bạn nhỉ?",
                        hint_level_2="Quy ước chuẩn: [Tên Cột][Số Dòng]. Ví dụ: Cột B, Dòng 8 thì ghép lại là B8.",
                        hint_level_3=f"Hãy sửa ô {active_cell} thành '{expected}' (Chữ B viết hoa trước, số {active_cell[1]} viết sau).",
                        teachable_question="Bạn có biết tại sao Excel lại quy ước Tên Cột đứng trước Số Dòng không?",
                    )
                elif cell_val.upper() == expected:
                    return EvaluationResult(
                        exercise_id="BAI_07",
                        step_title="Chính xác địa chỉ ô!",
                        is_correct=True,
                        target_cells=[active_cell],
                        hint_level_1=f"Xuất sắc! Ô {active_cell} đã điền đúng địa chỉ '{expected}'.",
                        teachable_question=f"Tại sao ô chứa chữ '{'Rồng' if active_cell=='C8' else '38'}' lại có địa chỉ là {expected} mà không phải địa chỉ khác?",
                    )

        # Kiểm tra lỗi điền nhầm cột và dòng (D8, E8, D9, E9)
        if active_cell in ["D8", "D9"] and cell_val:
            if cell_val.isdigit():
                return EvaluationResult(
                    exercise_id="BAI_07",
                    step_title="Nhầm lẫn giữa Cột và Dòng",
                    is_correct=False,
                    error_type="ROW_COL_CONFUSION",
                    target_cells=[active_cell],
                    target_rect=cell_rect,
                    hint_level_1="Cột trong Excel được đánh số bằng chữ cái (A, B, C...) hay bằng số (1, 2, 3...)?",
                    hint_level_2="Cột luôn là chữ cái. Cột chứa ô này là Cột B.",
                    hint_level_3="Hãy điền chữ 'B' vào ô này.",
                )

        if active_cell in ["E8", "E9"] and cell_val:
            if cell_val.isalpha():
                return EvaluationResult(
                    exercise_id="BAI_07",
                    step_title="Nhầm lẫn giữa Dòng và Cột",
                    is_correct=False,
                    error_type="ROW_COL_CONFUSION",
                    target_cells=[active_cell],
                    target_rect=cell_rect,
                    hint_level_1="Dòng trong Excel được đánh số thứ tự từ trên xuống dưới bằng chữ hay số bạn nhỉ?",
                    hint_level_2="Dòng luôn là con số. Dòng này có số thứ tự là " + active_cell[1],
                    hint_level_3=f"Hãy điền số '{active_cell[1]}' vào ô này.",
                )

        # Trạng thái tổng quan khi học viên đang đứng ở ô chưa làm
        target = "C8"
        return EvaluationResult(
            exercise_id="BAI_07",
            step_title="Thực hành xác định Địa chỉ ô",
            is_correct=False,
            target_cells=["C8", "D8", "E8", "F8", "C9", "D9", "E9", "F9"],
            target_rect=cell_rect,
            hint_level_1="Quan sát dòng số 7 đã làm mẫu: Từ giá trị '1988' ở ô B7, ta bóc tách thành Địa chỉ: B7, Cột: B, Dòng: 7.",
            hint_level_2="Hãy làm tương tự cho ô B8 (chứa chữ 'Rồng') và B9 (chứa số '38') ở các ô C8 đến F9.",
            hint_level_3="Chọn ô C8 và điền vào 'B8'.",
            teachable_question="Khi bạn bấm chọn một ô bất kỳ trên bảng tính, góc trên bên trái (Name Box) sẽ hiển thị thông tin gì?",
        )

    # -------------------------------------------------------------
    # ĐÁNH GIÁ BÀI 08: CÁC BƯỚC THỰC HIỆN TRƯỚC KHI NHẬP LIỆU
    # -------------------------------------------------------------
    def _evaluate_bai_08(self, state: Dict[str, Any], excel_monitor) -> EvaluationResult:
        sheet = state.get("sheet", "")
        active_cell = state.get("cell_clean_address", "")
        cell_val = str(state.get("cell_value") or "").strip()
        cell_fmt = state.get("cell_format", "")
        cell_rect = state.get("cell_rect")

        # Trường hợp 1: Học viên đang ở Cột F (SĐT) hoặc H (CCCD) trong sheet 1. Thuc_Hanh_Tung_Buoc
        if "Thuc_Hanh" in sheet or "1." in sheet:
            col_letter = active_cell[0] if active_cell else ""
            row_idx = int(active_cell[1:]) if active_cell and active_cell[1:].isdigit() else 0

            # Học viên đang ở cột SĐT (F)
            if col_letter == "F" and 7 <= row_idx <= 10:
                # Kiểm tra định dạng trước khi gõ hoặc sau khi gõ
                is_text_format = (cell_fmt == "@")
                has_leading_zero = cell_val.startswith("0")

                # LỖI KINH ĐIỂN: Gõ số điện thoại khi cột chưa định dạng Text -> mất số 0
                if cell_val and not has_leading_zero and cell_val.isdigit():
                    return EvaluationResult(
                        exercise_id="BAI_08",
                        step_title="Lỗi mất số 0 ở đầu số điện thoại",
                        is_correct=False,
                        error_type="MISSING_LEADING_ZERO",
                        target_cells=[active_cell],
                        target_rect=cell_rect,
                        hint_level_1="Hãy nhìn kỹ số điện thoại vừa gõ: Bạn có phát hiện số 0 ở đầu tiên đã bị biến mất không?",
                        hint_level_2="Excel đang hiểu đây là một con số toán học (Number/General) nên tự xóa số 0 ở đầu. Cần chuyển định dạng sang Text (@) trước khi nhập.",
                        hint_level_3="1. Nhấn chuột vào cột F\n2. Trên thanh Ribbon (Thẻ Home), tại mục Number, chọn 'Text'\n3. Gõ lại số điện thoại có số 0 ở đầu.",
                        teachable_question="Tại sao trong toán học số 0 ở đầu lại vô nghĩa, nhưng trong số điện thoại và CCCD số 0 lại bắt buộc phải giữ?",
                    )
                
                # Chưa định dạng Text mà chuẩn bị gõ (phòng ngừa trước)
                if not is_text_format and not cell_val:
                    return EvaluationResult(
                        exercise_id="BAI_08",
                        step_title="Cần định dạng Text trước khi gõ SĐT",
                        is_correct=False,
                        error_type="PREVENT_FORMAT_TEXT",
                        target_cells=[active_cell],
                        target_rect=cell_rect,
                        hint_level_1="Trước khi gõ số điện thoại vào ô này, bạn cần thực hiện thao tác quan trọng gì để không bị mất số 0?",
                        hint_level_2="Hãy quét chọn các ô cần nhập và chuyển định dạng từ 'General' sang 'Text' trên thanh công cụ Number.",
                        hint_level_3="Chọn dải ô F7:F10 -> Tại thẻ Home, bấm vào hộp chọn General -> Chọn 'Text' dưới cùng.",
                    )

                # Đã định dạng đúng và có số 0
                if is_text_format and has_leading_zero:
                    return EvaluationResult(
                        exercise_id="BAI_08",
                        step_title="Định dạng SĐT chuẩn xác!",
                        is_correct=True,
                        target_cells=[active_cell],
                        hint_level_1="Rất tốt! Số điện thoại đã giữ nguyên số 0 ở đầu và tự động căn sát lề trái chuẩn dữ liệu Text.",
                        teachable_question="Bạn có nhận thấy dữ liệu dạng Text và dạng Number tự động căn lề về phía nào của ô không?",
                    )

            # Học viên đang ở cột CCCD (H)
            if col_letter == "H" and 7 <= row_idx <= 10:
                is_text_format = (cell_fmt == "@")
                has_leading_zero = cell_val.startswith("0")

                if cell_val and not has_leading_zero and cell_val.isdigit():
                    return EvaluationResult(
                        exercise_id="BAI_08",
                        step_title="Lỗi mất số 0 ở đầu CCCD",
                        is_correct=False,
                        error_type="MISSING_LEADING_ZERO",
                        target_cells=[active_cell],
                        target_rect=cell_rect,
                        hint_level_1="Số CCCD 12 chữ số luôn bắt đầu bằng số 0 (như 079...). Hiện tại ô này đang bị mất số 0.",
                        hint_level_2="Cần định dạng cột H sang kiểu Text trước khi gõ.",
                        hint_level_3="Chọn cột H -> Thẻ Home -> Nhóm Number -> Chọn 'Text' -> Nhập lại CCCD.",
                    )

        # Trường hợp 2: Sheet 2. Bang_Tong_Hop (Kiểm tra 3 tiêu chí tổng hợp)
        if "Bang_Tong_Hop" in sheet or "2." in sheet:
            return EvaluationResult(
                exercise_id="BAI_08",
                step_title="Bài tập tổng hợp: Quản lý nhân sự & Hệ số lương",
                is_correct=False,
                target_cells=["C11:H15"],
                target_rect=cell_rect,
                hint_level_1="Hãy nhớ 3 quy tắc trước khi nhập liệu:\n1. Mã NV, SĐT, CCCD: Phải là TEXT.\n2. Ngày vào làm: Chuẩn DATE (tự căn phải).\n3. Hệ số lương: Chuẩn NUMBER với đúng dấu thập phân của máy.",
                hint_level_2="Hãy quét chọn toàn bộ cột C, E, F chuyển sang Text trước khi gõ thông tin các nhân viên.",
                hint_level_3="Chọn Cột C, E, F -> Thẻ Home -> Number -> Chọn Text.",
                teachable_question="Nếu đồng hồ máy tính của bạn đang hiển thị dạng Tháng/Ngày/Năm mà bạn lại gõ 15/01/2023 thì Excel sẽ hiểu là gì?",
            )

        # Mặc định
        return EvaluationResult(
            exercise_id="BAI_08",
            step_title="Bài 08: Kỹ năng nhập liệu chuẩn",
            is_correct=False,
            target_rect=cell_rect,
            hint_level_1="Mục tiêu của bài 08 là nắm vững cách giữ số 0 ở đầu (Text), nhập đúng ngày (Date) và dấu thập phân (Number).",
            hint_level_2="Mời bạn mở sheet '1. Thuc_Hanh_Tung_Buoc' để bắt đầu thực hành từng cột.",
        )
