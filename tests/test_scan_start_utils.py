import unittest

from scan_start_utils import (
    format_ranked_candidates,
    generate_start_frame_indices,
    resolve_scan_duration_hint,
)


class ScanStartUtilsTest(unittest.TestCase):
    def test_generate_start_frame_indices_uses_step_until_video_end(self):
        indices = generate_start_frame_indices(
            video_duration=100,
            start_step=12,
            start_max=0,
        )

        self.assertEqual(indices, [0, 12, 24, 36, 48, 60, 72, 84, 96])

    def test_generate_start_frame_indices_respects_start_max(self):
        indices = generate_start_frame_indices(
            video_duration=100,
            start_step=12,
            start_max=35,
        )

        self.assertEqual(indices, [0, 12, 24])

    def test_generate_start_frame_indices_requires_positive_step(self):
        with self.assertRaises(ValueError):
            generate_start_frame_indices(video_duration=120, start_step=0, start_max=0)

    def test_resolve_scan_duration_hint_uses_duration_hint_when_present(self):
        self.assertEqual(resolve_scan_duration_hint(120, 200), 200)

    def test_resolve_scan_duration_hint_falls_back_to_single_positional_arg(self):
        self.assertEqual(resolve_scan_duration_hint(120, None), 120)

    def test_format_ranked_candidates_outputs_ranked_lines(self):
        text = format_ranked_candidates(
            [
                {
                    "score": 0.0025,
                    "start_frame_idx": 24,
                    "end_frame_idx": 372,
                    "end_frame_position": 0.996,
                },
                {
                    "score": 0.0045,
                    "start_frame_idx": 0,
                    "end_frame_idx": 349,
                    "end_frame_position": 0.992,
                },
            ],
            top_n=2,
        )

        self.assertIn("Top 2 candidate loops (lower score is better):", text)
        self.assertIn("1. score=0.002500", text)
        self.assertIn("start=24", text)
        self.assertIn("2. score=0.004500", text)


if __name__ == "__main__":
    unittest.main()
