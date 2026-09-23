"""Giáo án thử nghiệm cho Bài 07 và Bài 08."""

from typing import Dict, Optional
import unicodedata

from src.core.lesson_models import (
    CheckKind,
    LessonPlan,
    LessonStep,
    ProcedureAction,
    ProcedureActionKind,
)


def _action(action_id, title, instruction, kind, target="", ui_target=""):
    return ProcedureAction(
        id=action_id,
        title=title,
        instruction=instruction,
        kind=ProcedureActionKind(kind),
        target_range=target,
        ui_target=ui_target,
    )


def _format_text_actions(prefix: str, target: str):
    """Quy trình chuẩn để định dạng một vùng Excel thành Text."""
    return (
        _action(
            f"{prefix}_select",
            f"Chọn chính xác {target}",
            f"Kéo chọn đúng vùng {target}. Không chọn thừa hàng hoặc cột.",
            "select_range",
            target,
        ),
        _action(
            f"{prefix}_home",
            "Mở thẻ Home",
            "Trên thanh Ribbon, bấm thẻ Home. Gia sư sẽ tự nhận biết và chuyển sang thao tác tiếp theo.",
            "ribbon_tab",
            target,
            "TabHome",
        ),
        _action(
            f"{prefix}_number_format",
            "Mở danh sách Number Format",
            "Trong nhóm Number của thẻ Home, bấm vào danh sách đang hiển thị General. Gia sư sẽ quan sát control này; nút xác nhận bên dưới luôn là phương án dự phòng.",
            "ribbon_control",
            target,
            "NumberFormat",
        ),
        _action(
            f"{prefix}_text",
            "Chọn Text",
            "Trong danh sách Number Format, chọn Text. Gia sư sẽ tự đọc lại định dạng của từng ô trong vùng.",
            "verify_result",
            target,
        ),
    )


def _step(
    *,
    step_id,
    title,
    instruction,
    sheet,
    target,
    check,
    hints,
    success,
    expected=None,
    source_sheet="",
    source_range="",
    reflection="",
    errors=None,
    metadata=None,
    actions=(),
):
    return LessonStep(
        id=step_id,
        title=title,
        instruction=instruction,
        sheet=sheet,
        target_range=target,
        check_kind=check,
        hints=tuple(hints),
        success_message=success,
        expected=expected,
        source_sheet=source_sheet,
        source_range=source_range,
        reflection_question=reflection,
        error_messages=errors or {},
        metadata=metadata or {},
        procedure_actions=tuple(actions),
    )


BAI_07 = LessonPlan(
    id="BAI_07",
    code="07",
    title="Các thao tác cơ bản với địa chỉ ô",
    workbook_tokens=("bai 07", "dia chi o"),
    steps=(
        _step(
            step_id="07_address_b8",
            title="Xác định địa chỉ ô chứa chữ Rồng",
            instruction="Quan sát ô B8, sau đó nhập địa chỉ của ô này vào C8.",
            sheet="Bài 01",
            target="C8",
            check=CheckKind.VALUE_MATRIX,
            expected=[["B8"]],
            hints=(
                "Tên ô được ghép từ tên cột và số dòng. Ô chứa chữ Rồng nằm ở cột nào, dòng nào?",
                "Hãy đọc tên cột trước, rồi đọc số dòng: cột B và dòng 8.",
                "Chọn ô C8 và nhập B8.",
            ),
            success="Đúng rồi! Địa chỉ ô chứa chữ Rồng là B8.",
            reflection="Vì sao phải viết B8 mà không phải 8B?",
            errors={"reversed_address": "Bạn đang đặt số dòng trước tên cột. Excel luôn viết tên cột trước."},
        ),
        _step(
            step_id="07_details_b8",
            title="Hoàn thiện thông tin của ô B8",
            instruction="Điền lần lượt Cột, Dòng và Giá trị của ô B8 vào vùng D8:F8.",
            sheet="Bài 01",
            target="D8:F8",
            check=CheckKind.VALUE_MATRIX,
            expected=[["B", 8, "Rồng"]],
            hints=(
                "Ba ô cần điền lần lượt là tên cột, số dòng và nội dung đang có trong B8.",
                "D8 nhập B, E8 nhập 8; F8 sao chép đúng giá trị đang thấy trong B8.",
                "Điền D8:F8 lần lượt là B, 8, Rồng.",
            ),
            success="Bạn đã mô tả đầy đủ ô B8: cột B, dòng 8, giá trị Rồng.",
        ),
        _step(
            step_id="07_row_9",
            title="Hoàn thiện thông tin của ô B9",
            instruction="Làm tương tự cho ô B9 và điền toàn bộ vùng C9:F9.",
            sheet="Bài 01",
            target="C9:F9",
            check=CheckKind.VALUE_MATRIX,
            expected=[["B9", "B", 9, 38]],
            hints=(
                "Áp dụng đúng thứ tự như dòng 8: địa chỉ, cột, dòng, giá trị.",
                "B9 nằm ở cột B, dòng 9 và đang chứa số 38.",
                "Điền C9:F9 lần lượt là B9, B, 9, 38.",
            ),
            success="Chính xác! Bạn đã hoàn thành bảng thông tin theo cột.",
            reflection="Điểm nào giống nhau giữa địa chỉ B8 và B9?",
        ),
        _step(
            step_id="07_row_addresses",
            title="Xác định địa chỉ theo dòng",
            instruction="Quan sát hai giá trị Rồng và 38 ở dòng 12, rồi điền địa chỉ của chúng vào D13:E13.",
            sheet="Bài 01",
            target="D13:E13",
            check=CheckKind.VALUE_MATRIX,
            expected=[["D12", "E12"]],
            hints=(
                "Hai giá trị nằm cùng dòng 12 nhưng ở hai cột khác nhau.",
                "Rồng nằm ở D12 và số 38 nằm ở E12.",
                "Điền D13:E13 lần lượt là D12 và E12.",
            ),
            success="Đúng! Hai địa chỉ cần tìm là D12 và E12.",
        ),
        _step(
            step_id="07_row_columns",
            title="Xác định tên cột",
            instruction="Điền tên cột của hai ô D12 và E12 vào D14:E14.",
            sheet="Bài 01",
            target="D14:E14",
            check=CheckKind.VALUE_MATRIX,
            expected=[["D", "E"]],
            hints=(
                "Tên cột là phần chữ cái trong địa chỉ ô.",
                "D12 thuộc cột D; E12 thuộc cột E.",
                "Điền D14:E14 lần lượt là D và E.",
            ),
            success="Bạn đã xác định đúng hai cột D và E.",
        ),
        _step(
            step_id="07_row_numbers",
            title="Xác định số dòng",
            instruction="Điền số dòng của hai ô D12 và E12 vào D15:E15.",
            sheet="Bài 01",
            target="D15:E15",
            check=CheckKind.VALUE_MATRIX,
            expected=[[12, 12]],
            hints=(
                "Số dòng là phần số trong địa chỉ ô.",
                "Cả D12 và E12 đều nằm trên cùng dòng 12.",
                "Điền số 12 vào cả D15 và E15.",
            ),
            success="Đúng! Cả hai ô đều thuộc dòng 12.",
        ),
        _step(
            step_id="07_row_values",
            title="Hoàn thành giá trị theo dòng",
            instruction="Điền đúng giá trị của D12 và E12 vào D16:E16.",
            sheet="Bài 01",
            target="D16:E16",
            check=CheckKind.VALUE_MATRIX,
            expected=[["Rồng", 38]],
            hints=(
                "Đọc nguyên nội dung đang hiển thị trong D12 và E12.",
                "D12 chứa chữ Rồng, E12 chứa số 38.",
                "Điền D16:E16 lần lượt là Rồng và 38.",
            ),
            success="Hoàn thành! Bạn đã hiểu cách xác định địa chỉ, cột, dòng và giá trị ô.",
            reflection="Nếu một ô có địa chỉ F20 thì tên cột và số dòng của nó là gì?",
        ),
    ),
)


BAI_08 = LessonPlan(
    id="BAI_08",
    code="08",
    title="Các bước cần thực hiện trước khi nhập dữ liệu",
    workbook_tokens=("bai 08", "nhap du lieu"),
    steps=(
        _step(
            step_id="08_observe_zero_loss",
            title="Quan sát hiện tượng mất số 0",
            instruction="Tại E7, hãy gõ thử số điện thoại đang có ở D7 mà chưa đổi định dạng Text.",
            sheet="1. Thuc_Hanh_Tung_Buoc",
            target="E7",
            check=CheckKind.DEMONSTRATE_LEADING_ZERO_LOSS,
            source_sheet="1. Thuc_Hanh_Tung_Buoc",
            source_range="D7",
            hints=(
                "Hãy nhập đúng dãy số nhìn thấy ở D7 và quan sát ký tự đầu tiên sau khi nhấn Enter.",
                "Ô E7 đang ở định dạng General nên Excel sẽ coi số điện thoại là một con số.",
                "Chọn E7, gõ 0358945333 rồi nhấn Enter để quan sát số 0 đầu bị mất.",
            ),
            success="Bạn đã quan sát được hiện tượng: định dạng General làm mất số 0 ở đầu.",
            reflection="Vì sao số 0 đầu không quan trọng trong phép tính nhưng lại quan trọng với số điện thoại?",
        ),
        _step(
            step_id="08_format_phone",
            title="Định dạng vùng số điện thoại thành Text",
            instruction="Quét chọn F7:F10 và chuyển Number Format sang Text trước khi nhập dữ liệu.",
            sheet="1. Thuc_Hanh_Tung_Buoc",
            target="F7:F10",
            check=CheckKind.TEXT_FORMAT,
            hints=(
                "Cần định dạng cả vùng trước khi nhập để Excel giữ nguyên số 0 đầu.",
                "Chọn F7:F10, vào Home, mở danh sách Number Format và tìm Text.",
                "Khoanh chọn F7:F10 rồi chọn Home → Number Format → Text.",
            ),
            success="F7:F10 đã được định dạng Text. Bây giờ số 0 đầu sẽ được giữ nguyên.",
            actions=_format_text_actions("08_phone", "F7:F10"),
        ),
        _step(
            step_id="08_enter_phone",
            title="Nhập số điện thoại không mất số 0",
            instruction="Nhập các số điện thoại từ D7:D10 sang F7:F10.",
            sheet="1. Thuc_Hanh_Tung_Buoc",
            target="F7:F10",
            check=CheckKind.MATCH_SOURCE,
            source_sheet="1. Thuc_Hanh_Tung_Buoc",
            source_range="D7:D10",
            hints=(
                "Nhập lần lượt từng số và kiểm tra chúng vẫn bắt đầu bằng 0.",
                "Bạn có thể sao chép D7:D10 rồi dán Values vào vùng đã định dạng Text.",
                "Điền F7:F10 giống hệt D7:D10 và bảo đảm cả bốn số đều còn số 0 đầu.",
            ),
            success="Đúng! Toàn bộ số điện thoại đã giữ nguyên số 0 đầu.",
        ),
        _step(
            step_id="08_format_citizen_id",
            title="Định dạng vùng CCCD thành Text",
            instruction="Quét chọn H7:H10 và chuyển sang định dạng Text.",
            sheet="1. Thuc_Hanh_Tung_Buoc",
            target="H7:H10",
            check=CheckKind.TEXT_FORMAT,
            hints=(
                "CCCD là mã định danh, không phải dữ liệu dùng để tính toán.",
                "Chọn H7:H10 và đổi Number Format từ General sang Text.",
                "Khoanh H7:H10 rồi chọn Home → Number Format → Text.",
            ),
            success="H7:H10 đã sẵn sàng để nhập CCCD mà không mất số 0.",
            actions=_format_text_actions("08_citizen", "H7:H10"),
        ),
        _step(
            step_id="08_enter_citizen_id",
            title="Nhập CCCD đúng chuẩn",
            instruction="Nhập các số CCCD từ G7:G10 sang H7:H10.",
            sheet="1. Thuc_Hanh_Tung_Buoc",
            target="H7:H10",
            check=CheckKind.MATCH_SOURCE,
            source_sheet="1. Thuc_Hanh_Tung_Buoc",
            source_range="G7:G10",
            hints=(
                "Đối chiếu từng dòng và chú ý số 0 ở đầu.",
                "Giá trị H7:H10 phải giống chính xác G7:G10.",
                "Sao chép G7:G10 sang H7:H10 và kiểm tra cả bốn CCCD vẫn đủ 12 chữ số.",
            ),
            success="Chính xác! Các số CCCD được lưu dưới dạng Text và không mất số 0.",
        ),
        _step(
            step_id="08_decimal_separator",
            title="Xác định dấu thập phân của máy",
            instruction="Điền cả hai cách dùng dấu chấm và dấu phẩy vào D15:E17; quan sát cách nào được Excel hiểu là số.",
            sheet="1. Thuc_Hanh_Tung_Buoc",
            target="D15:E17",
            check=CheckKind.DECIMAL_SEPARATOR_TEST,
            hints=(
                "Mỗi dòng hãy thử một giá trị với dấu chấm và một giá trị với dấu phẩy.",
                "Cách được Excel hiểu là Number thường tự căn phải.",
                "Điền đủ D15:E17; mỗi dòng phải có ít nhất một ô được Excel nhận là số.",
            ),
            success="Tốt! Bạn đã thử cả hai dấu và Excel đã nhận diện được cách nhập số hợp lệ.",
        ),
        _step(
            step_id="08_date_values",
            title="Nhập ngày tháng đúng chuẩn hệ thống",
            instruction="Nhập ba ngày được yêu cầu vào E22:E24 và kiểm tra Excel nhận chúng là Date.",
            sheet="1. Thuc_Hanh_Tung_Buoc",
            target="E22:E24",
            check=CheckKind.DATE_VALUES,
            expected=[(2024, 12, 15), (2025, 2, 28), (2024, 9, 5)],
            hints=(
                "Nhập theo thứ tự ngày, tháng, năm mà hệ thống của bạn đang sử dụng.",
                "Ngày hợp lệ thường được Excel lưu như Date và tự căn phải.",
                "E22:E24 cần lần lượt là 15/12/2024, 28/02/2025 và 05/09/2024 dưới dạng ngày hợp lệ.",
            ),
            success="Đúng! Cả ba giá trị đã được Excel nhận là ngày tháng hợp lệ.",
        ),
        _step(
            step_id="08_summary_employee_id_format",
            title="Chuẩn bị cột Mã nhân viên",
            instruction="Chuyển sang sheet 2. Bang_Tong_Hop và định dạng C11:C15 thành Text.",
            sheet="2. Bang_Tong_Hop",
            target="C11:C15",
            check=CheckKind.TEXT_FORMAT,
            hints=(
                "Mã nhân viên là mã định danh nên cần giữ nguyên mọi ký tự.",
                "Chọn C11:C15 rồi đổi Number Format sang Text.",
                "Tại sheet 2, khoanh C11:C15 và chọn Home → Number Format → Text.",
            ),
            success="Cột Mã nhân viên đã được chuẩn bị đúng định dạng Text.",
            actions=_format_text_actions("08_summary_employee", "C11:C15"),
        ),
        _step(
            step_id="08_summary_id_formats",
            title="Chuẩn bị SĐT và CCCD trong bảng tổng hợp",
            instruction="Định dạng vùng E11:F15 thành Text trước khi nhập.",
            sheet="2. Bang_Tong_Hop",
            target="E11:F15",
            check=CheckKind.TEXT_FORMAT,
            hints=(
                "Hai cột Số điện thoại và CCCD đều là mã, không phải số dùng để tính.",
                "Quét chọn E11:F15 rồi chọn định dạng Text.",
                "Khoanh E11:F15 và chọn Home → Number Format → Text.",
            ),
            success="Hai cột SĐT và CCCD đã được định dạng Text.",
            actions=_format_text_actions("08_summary_ids", "E11:F15"),
        ),
        _step(
            step_id="08_summary_complete",
            title="Hoàn thành bảng dữ liệu tổng hợp",
            instruction="Nhập đầy đủ dữ liệu C11:H15 theo bảng đáp án mẫu, giữ đúng kiểu Text, Date và Number.",
            sheet="2. Bang_Tong_Hop",
            target="C11:H15",
            check=CheckKind.MATCH_SOURCE,
            source_sheet="3. Dap_An_Mau",
            source_range="C6:H10",
            hints=(
                "Đối chiếu từng dòng: Mã NV, Họ tên, SĐT, CCCD, Ngày vào làm và Hệ số lương.",
                "Kiểm tra ba nhóm quan trọng: mã ở dạng Text, ngày ở dạng Date và hệ số ở dạng Number.",
                "Hoàn thiện C11:H15 sao cho khớp C6:H10 của sheet 3. Dap_An_Mau.",
            ),
            success="Xuất sắc! Bạn đã hoàn thành bảng tổng hợp với dữ liệu và định dạng chuẩn.",
            reflection="Ba loại dữ liệu nào cần được kiểm tra trước khi nhập trong bài này?",
        ),
    ),
)


LESSONS: Dict[str, LessonPlan] = {BAI_07.id: BAI_07, BAI_08.id: BAI_08}


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def get_lesson(lesson_id: str) -> LessonPlan:
    normalized = str(lesson_id or "").strip().upper().replace(" ", "_")
    if normalized in {"07", "7"}:
        normalized = "BAI_07"
    elif normalized in {"08", "8"}:
        normalized = "BAI_08"
    if normalized not in LESSONS:
        raise KeyError(f"Không tìm thấy giáo án {lesson_id}")
    return LESSONS[normalized]


def identify_lesson(workbook_name: str) -> Optional[LessonPlan]:
    normalized = normalize_text(workbook_name)
    for lesson in LESSONS.values():
        if any(normalize_text(token) in normalized for token in lesson.workbook_tokens):
            return lesson
    return None
