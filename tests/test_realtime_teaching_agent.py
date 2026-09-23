"""Kiểm thử vòng lặp agentic realtime không phụ thuộc Excel đang mở."""

from datetime import datetime
import unittest

from src.core.lesson_models import SessionStatus
from src.core.realtime_teaching_agent import RealtimeTeachingAgent


class FakeExcelTools:
    def __init__(self):
        self.ranges = {}
        self.rect_calls = []

    def set_range(self, sheet, address, values, formats="General"):
        self.ranges[(sheet, address)] = {"values": values, "formats": formats}

    def read(self, sheet, address):
        return self.ranges.get((sheet, address), {"values": None, "formats": None})

    def rect(self, address, sheet):
        self.rect_calls.append((sheet, address))
        return {"success": True, "x": 100, "y": 200, "width": 240, "height": 80}


def excel_state(
    workbook,
    sheet,
    active="C8",
    selection="C8",
    selection_area_count=1,
    selection_rect=(100, 200, 240, 80),
    ribbon_available=False,
    ribbon_tab_id="",
    number_format_expanded=False,
    number_format_focused=False,
):
    return {
        "connected": True,
        "workbook": workbook,
        "sheet": sheet,
        "active_cell": active,
        "selection_address": selection,
        "selection_area_count": selection_area_count,
        "selection_rect": selection_rect,
        "ribbon_available": ribbon_available,
        "ribbon_tab_id": ribbon_tab_id,
        "number_format_expanded": number_format_expanded,
        "number_format_focused": number_format_focused,
    }


class TestRealtimeTeachingAgent(unittest.TestCase):
    def make_agent(self, threshold=8.0):
        self.tools = FakeExcelTools()
        return RealtimeTeachingAgent(self.tools.read, self.tools.rect, threshold)

    def test_bai_07_observes_then_verifies_first_step(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_07", now=0)
        self.tools.set_range("Bài 01", "C8", None)
        state = excel_state(
            "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx", "Bài 01"
        )

        waiting = agent.observe(state, now=0)
        self.assertEqual(waiting["agent_status"], "observing")
        self.assertEqual(waiting["step_position"], "Bước 1/7")
        self.assertFalse(waiting["is_correct"])

        self.tools.set_range("Bài 01", "C8", "B8")
        correct = agent.observe(state, now=1)
        self.assertTrue(correct["is_correct"])
        self.assertEqual(correct["agent_status"], "step_correct")
        self.assertTrue(correct["can_continue"])

        next_step = agent.acknowledge_step(now=2)
        self.assertEqual(next_step["step_id"], "07_details_b8")
        self.assertEqual(next_step["step_position"], "Bước 2/7")

    def test_hesitation_escalates_to_overlay_without_llm(self):
        agent = self.make_agent(threshold=4.0)
        agent.start_lesson("BAI_07", now=0)
        self.tools.set_range("Bài 01", "C8", None)
        state = excel_state(
            "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx", "Bài 01"
        )

        level_1 = agent.observe(state, now=0)
        level_2 = agent.observe(state, now=4.1)
        level_3 = agent.observe(state, now=9.1)

        self.assertEqual(level_1["hint_level"], 1)
        self.assertEqual(level_2["hint_level"], 2)
        self.assertEqual(level_3["hint_level"], 3)
        self.assertEqual(level_3["target_rect"], (100, 200, 240, 80))
        # Khi Selection đã đúng, ưu tiên geometry Excel vừa đo thay vì gọi lại
        # resolver; cách này tránh chênh lệch một polling tick khi đang cuộn.
        self.assertEqual(self.tools.rect_calls, [])

    def test_agent_waits_for_correct_workbook_and_sheet(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_08", now=0)

        wrong_file = agent.observe(excel_state("Book1.xlsx", "Sheet1"), now=1)
        self.assertEqual(wrong_file["agent_status"], "waiting_for_workbook")

        wrong_sheet = agent.observe(
            excel_state(
                "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx",
                "2. Bang_Tong_Hop",
            ),
            now=2,
        )
        self.assertEqual(wrong_sheet["agent_status"], "waiting_for_sheet")

    def test_bai_08_detects_zero_loss_and_text_format(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_08", now=0)
        sheet = "1. Thuc_Hanh_Tung_Buoc"
        state = excel_state(
            "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx",
            sheet,
            active="E7",
            selection="E7",
        )
        self.tools.set_range(sheet, "D7", "0358945333")
        self.tools.set_range(sheet, "E7", 358945333)

        observed = agent.observe(state, now=1)
        self.assertTrue(observed["is_correct"])
        self.assertEqual(observed["step_id"], "08_observe_zero_loss")

        agent.acknowledge_step(now=2)
        self.tools.set_range(
            sheet,
            "F7:F10",
            ((None,), (None,), (None,), (None,)),
            (("General",), ("General",), ("General",), ("General",)),
        )
        selected = agent.observe(
            excel_state(state["workbook"], sheet, active="F7", selection="F7:F10"),
            now=3,
        )
        self.assertFalse(selected["is_correct"])
        self.assertEqual(selected["action_position"], "2/4")
        self.assertEqual(selected["action_title"], "Mở thẻ Home")
        self.assertTrue(selected["can_advance_action"])

        number_format = agent.acknowledge_step(now=4)
        self.assertEqual(number_format["action_position"], "3/4")
        self.assertEqual(number_format["action_title"], "Mở danh sách Number Format")

        choose_text = agent.acknowledge_step(now=5)
        self.assertFalse(choose_text["is_correct"])
        self.assertEqual(choose_text["action_position"], "4/4")

        self.tools.set_range(
            sheet,
            "F7:F10",
            ((None,), (None,), (None,), (None,)),
            (("@",), ("@",), ("@",), ("@",)),
        )
        formatted = agent.observe(
            excel_state(state["workbook"], sheet, active="F7", selection="F7:F10"),
            now=6,
        )
        self.assertTrue(formatted["is_correct"])
        self.assertEqual(formatted["step_id"], "08_format_phone")
        self.assertEqual(formatted["action_position"], "4/4")

    def test_exact_selection_is_a_hard_gate_for_procedure(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_08", now=0)
        sheet = "1. Thuc_Hanh_Tung_Buoc"
        workbook = "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx"
        self.tools.set_range(sheet, "D7", "0358945333")
        self.tools.set_range(sheet, "E7", 358945333)
        first = agent.observe(
            excel_state(workbook, sheet, active="E7", selection="E7"), now=1
        )
        self.assertTrue(first["is_correct"])
        agent.acknowledge_step(now=2)
        self.tools.set_range(
            sheet,
            "F7:F10",
            ((None,), (None,), (None,), (None,)),
            (("General",), ("General",), ("General",), ("General",)),
        )

        for selection, area_count in (
            ("F7:F9", 1),
            ("F7:G10", 1),
            ("F7:F10", 2),
        ):
            result = agent.observe(
                excel_state(
                    workbook,
                    sheet,
                    active="F7",
                    selection=selection,
                    selection_area_count=area_count,
                ),
                now=3,
            )
            self.assertEqual(result["action_position"], "1/4")
            self.assertFalse(result["selection_is_exact"])
            self.assertEqual(result["verification_state"], "wrong")
            self.assertEqual(result["target_range"], "F7:F10")
            self.assertEqual(result["target_rect"], (100, 200, 240, 80))

        exact = agent.observe(
            excel_state(
                workbook,
                sheet,
                active="F7",
                selection="$F$10:$F$7",
            ),
            now=4,
        )
        self.assertEqual(exact["action_position"], "2/4")
        self.assertTrue(exact["selection_is_exact"])
        self.assertEqual(exact["next_action_preview"], "Mở danh sách Number Format")

    def test_home_tab_is_detected_and_advances_automatically(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_08", now=0)
        sheet = "1. Thuc_Hanh_Tung_Buoc"
        workbook = "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx"
        self.tools.set_range(sheet, "D7", "0358945333")
        self.tools.set_range(sheet, "E7", 358945333)
        agent.observe(excel_state(workbook, sheet, selection="E7"), now=1)
        agent.acknowledge_step(now=2)
        self.tools.set_range(
            sheet,
            "F7:F10",
            ((None,), (None,), (None,), (None,)),
            (("General",), ("General",), ("General",), ("General",)),
        )

        selected = agent.observe(
            excel_state(workbook, sheet, selection="F7:F10"),
            now=3,
        )
        self.assertEqual(selected["action_position"], "2/4")

        first_sample = agent.observe(
            excel_state(
                workbook,
                sheet,
                selection="F7:F10",
                ribbon_available=True,
                ribbon_tab_id="TabHome",
            ),
            now=3.3,
        )
        self.assertEqual(first_sample["action_position"], "2/4")
        self.assertEqual(first_sample["verification_state"], "correct")

        confirmed = agent.observe(
            excel_state(
                workbook,
                sheet,
                selection="F7:F10",
                ribbon_available=True,
                ribbon_tab_id="TabHome",
            ),
            now=3.6,
        )
        self.assertEqual(confirmed["action_position"], "3/4")
        self.assertEqual(confirmed["action_title"], "Mở danh sách Number Format")

    def test_wrong_ribbon_tab_does_not_advance_home_action(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_08", now=0)
        agent.session.current_step_index = 1
        agent.session.status = SessionStatus.OBSERVING
        agent.session.procedure_action_index = 1
        sheet = "1. Thuc_Hanh_Tung_Buoc"
        workbook = "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx"
        self.tools.set_range(
            sheet,
            "F7:F10",
            ((None,), (None,), (None,), (None,)),
            (("General",), ("General",), ("General",), ("General",)),
        )

        result = agent.observe(
            excel_state(
                workbook,
                sheet,
                selection="F7:F10",
                ribbon_available=True,
                ribbon_tab_id="TabInsert",
            ),
            now=1,
        )
        self.assertEqual(result["action_position"], "2/4")
        self.assertEqual(result["verification_state"], "waiting")
        self.assertFalse(result["can_advance_action"])
        still_waiting = agent.acknowledge_step(now=1.1)
        self.assertEqual(still_waiting["action_position"], "2/4")

    def test_number_format_control_can_advance_from_accessibility_signal(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_08", now=0)
        agent.session.current_step_index = 1
        agent.session.status = SessionStatus.OBSERVING
        agent.session.procedure_action_index = 2
        sheet = "1. Thuc_Hanh_Tung_Buoc"
        workbook = "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx"
        self.tools.set_range(
            sheet,
            "F7:F10",
            ((None,), (None,), (None,), (None,)),
            (("General",), ("General",), ("General",), ("General",)),
        )

        result = agent.observe(
            excel_state(
                workbook,
                sheet,
                selection="F7:F10",
                ribbon_available=True,
                ribbon_tab_id="TabHome",
                number_format_expanded=True,
            ),
            now=1,
        )
        self.assertEqual(result["action_position"], "4/4")
        self.assertEqual(result["action_title"], "Chọn Text")

    def test_correct_text_result_cannot_get_stuck_on_missed_dropdown_popup(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_08", now=0)
        agent.session.current_step_index = 1
        agent.session.status = SessionStatus.OBSERVING
        agent.session.procedure_action_index = 2
        sheet = "1. Thuc_Hanh_Tung_Buoc"
        workbook = "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx"
        self.tools.set_range(
            sheet,
            "F7:F10",
            ((None,), (None,), (None,), (None,)),
            (("@",), ("@",), ("@",), ("@",)),
        )

        result = agent.observe(
            excel_state(
                workbook,
                sheet,
                selection="F7:F10",
                ribbon_available=True,
                ribbon_tab_id="TabHome",
                number_format_expanded=False,
                number_format_focused=False,
            ),
            now=1,
        )

        self.assertTrue(result["is_correct"])
        self.assertEqual(result["action_position"], "4/4")
        self.assertEqual(result["agent_status"], "step_correct")
        number_format_row = next(
            row
            for row in result["procedure_actions"]
            if row["title"] == "Mở danh sách Number Format"
        )
        self.assertEqual(number_format_row["status"], "inferred")

    def test_correct_final_state_cannot_skip_required_actions(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_08", now=0)
        sheet = "1. Thuc_Hanh_Tung_Buoc"
        workbook = "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx"
        self.tools.set_range(sheet, "D7", "0358945333")
        self.tools.set_range(sheet, "E7", 358945333)
        agent.observe(excel_state(workbook, sheet, active="E7", selection="E7"), now=1)
        agent.acknowledge_step(now=2)
        self.tools.set_range(
            sheet,
            "F7:F10",
            ((None,), (None,), (None,), (None,)),
            (("@",), ("@",), ("@",), ("@",)),
        )

        wrong_selection = agent.observe(
            excel_state(workbook, sheet, active="F7", selection="F7:F9"), now=3
        )
        self.assertFalse(wrong_selection["is_correct"])
        self.assertEqual(wrong_selection["agent_status"], "observing")
        self.assertEqual(wrong_selection["action_position"], "1/4")

        selected = agent.observe(
            excel_state(workbook, sheet, active="F7", selection="F7:F10"), now=4
        )
        self.assertFalse(selected["is_correct"])
        self.assertEqual(selected["action_position"], "2/4")

    def test_verified_step_without_reflection_auto_advances(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_07", now=0)
        agent.session.current_step_index = 1
        agent.session.status = SessionStatus.OBSERVING
        sheet = "Bài 01"
        workbook = "Bài 07. Các thao tác cơ bản với địa chỉ ô.xlsx"
        self.tools.set_range(sheet, "D8:F8", (("B", 8, "Rồng"),))

        correct = agent.observe(
            excel_state(workbook, sheet, active="D8", selection="D8:F8"),
            now=1,
        )
        self.assertEqual(correct["agent_status"], "step_correct")
        self.assertTrue(correct["auto_advance"])

        advanced = agent.observe(
            excel_state(workbook, sheet, active="C9", selection="C9:F9"),
            now=2.3,
        )
        self.assertEqual(advanced["step_id"], "07_row_9")
        self.assertEqual(advanced["agent_status"], "observing")

    def test_pause_stops_observation_until_resumed(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_07", now=0)
        paused = agent.pause()
        self.assertEqual(paused["agent_status"], "paused")
        self.assertEqual(agent.session.status, SessionStatus.PAUSED)

        result = agent.observe({"connected": False}, now=5)
        self.assertEqual(result["agent_status"], "paused")

        resumed = agent.resume(now=6)
        self.assertEqual(resumed["agent_status"], "observing")

    def test_bai_08_validates_dates_as_real_excel_dates(self):
        agent = self.make_agent()
        agent.start_lesson("BAI_08", now=0)
        agent.session.current_step_index = 6
        sheet = "1. Thuc_Hanh_Tung_Buoc"
        self.tools.set_range(
            sheet,
            "E22:E24",
            (
                (datetime(2024, 12, 15),),
                (datetime(2025, 2, 28),),
                (datetime(2024, 9, 5),),
            ),
            (("mm-dd-yy",), ("mm-dd-yy",), ("mm-dd-yy",)),
        )
        result = agent.observe(
            excel_state(
                "Bài 08. Các bước cần thực hiện trước khi nhập dữ liệu.xlsx",
                sheet,
                active="E22",
                selection="E22:E24",
            ),
            now=1,
        )
        self.assertTrue(result["is_correct"])
        self.assertEqual(result["step_id"], "08_date_values")


if __name__ == "__main__":
    unittest.main()
