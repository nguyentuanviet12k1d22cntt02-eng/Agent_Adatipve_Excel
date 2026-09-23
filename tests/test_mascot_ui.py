import unittest

from PIL import Image

from src.gui.mascot_assets import (
    MASCOT_STYLES,
    mascot_asset_path,
    visual_state_for_guidance,
)
from src.gui.overlay_window import calculate_callout_rect


class MascotVisualStateTests(unittest.TestCase):
    def test_guidance_states_choose_semantic_pose(self):
        self.assertEqual(
            visual_state_for_guidance({"agent_status": "waiting_for_excel"}),
            "welcome",
        )
        self.assertEqual(
            visual_state_for_guidance({"agent_status": "observing", "hint_level": 1}),
            "thinking",
        )
        self.assertEqual(
            visual_state_for_guidance({"agent_status": "observing", "hint_level": 3}),
            "teaching",
        )
        self.assertEqual(
            visual_state_for_guidance(
                {
                    "agent_status": "observing",
                    "hint_level": 3,
                    "error_type": "incorrect_value",
                }
            ),
            "warning",
        )
        self.assertEqual(
            visual_state_for_guidance({"agent_status": "step_correct", "is_correct": True}),
            "success",
        )

    def test_all_pose_assets_are_real_transparent_pngs(self):
        for state in MASCOT_STYLES:
            path = mascot_asset_path(state)
            self.assertTrue(path.exists(), state)
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                alpha_min, alpha_max = image.getchannel("A").getextrema()
                self.assertEqual(alpha_min, 0)
                self.assertEqual(alpha_max, 255)


class CalloutPlacementTests(unittest.TestCase):
    def test_callout_sits_above_range_when_there_is_space(self):
        callout = calculate_callout_rect((120, 300, 500, 80), 1280, 720)
        self.assertLess(callout.bottom(), 300)

    def test_callout_moves_below_range_near_top_edge(self):
        callout = calculate_callout_rect((120, 10, 500, 80), 1280, 720)
        self.assertGreater(callout.top(), 10 + 80)

    def test_callout_is_clamped_inside_right_edge(self):
        callout = calculate_callout_rect((1220, 300, 40, 30), 1280, 720)
        self.assertLessEqual(callout.right(), 1272)
        self.assertGreaterEqual(callout.left(), 8)


if __name__ == "__main__":
    unittest.main()
