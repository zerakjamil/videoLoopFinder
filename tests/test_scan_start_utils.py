import unittest

from scan_start_utils import (
    format_ranked_candidates,
    generate_engine_bridge_plan,
    generate_start_frame_indices,
    is_loop_candidate_valid,
    rank_loop_candidates,
    resolve_engine_blend_frames,
    resolve_engine_switch_margin,
    resolve_scan_duration_hint,
    select_engine_bridge_style,
    select_backoff_candidate,
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
                    "rank_score": 0.0025,
                    "start_frame_idx": 24,
                    "end_frame_idx": 372,
                    "end_frame_position": 0.996,
                },
                {
                    "score": 0.0045,
                    "rank_score": 0.0045,
                    "start_frame_idx": 0,
                    "end_frame_idx": 349,
                    "end_frame_position": 0.992,
                },
            ],
            top_n=2,
        )

        self.assertIn("Top 2 candidate loops (lower rank score is better):", text)
        self.assertIn("1. score=0.002500", text)
        self.assertIn("rank=0.002500", text)
        self.assertIn("start=24", text)
        self.assertIn("2. score=0.004500", text)

    def test_rank_loop_candidates_penalises_degenerate_loops(self):
        ranked = rank_loop_candidates(
            [
                {
                    "score": 0.0001,
                    "start_frame_idx": 132,
                    "end_frame_idx": 132,
                    "end_frame_position": float("nan"),
                },
                {
                    "score": 0.0003,
                    "start_frame_idx": 96,
                    "end_frame_idx": 113,
                    "end_frame_position": 0.971,
                },
            ],
            duration_hint=None,
            minimum_loop_frames=12,
        )

        self.assertEqual(ranked[0]["start_frame_idx"], 96)
        self.assertGreater(ranked[1]["rank_score"], ranked[0]["rank_score"])

    def test_rank_loop_candidates_prefers_duration_consistency(self):
        ranked = rank_loop_candidates(
            [
                {
                    "score": 0.0004,
                    "start_frame_idx": 24,
                    "end_frame_idx": 84,
                    "end_frame_position": 0.99,
                },
                {
                    "score": 0.0004,
                    "start_frame_idx": 24,
                    "end_frame_idx": 40,
                    "end_frame_position": 0.99,
                },
            ],
            duration_hint=60,
            minimum_loop_frames=5,
        )

        self.assertEqual(ranked[0]["end_frame_idx"], 84)

    def test_rank_loop_candidates_handles_missing_end_position(self):
        ranked = rank_loop_candidates(
            [
                {
                    "score": 0.0002,
                    "start_frame_idx": 20,
                    "end_frame_idx": 52,
                    "end_frame_position": None,
                },
                {
                    "score": 0.0003,
                    "start_frame_idx": 24,
                    "end_frame_idx": 60,
                    "end_frame_position": 0.98,
                },
            ],
            duration_hint=None,
            minimum_loop_frames=5,
        )

        self.assertEqual(ranked[0]["start_frame_idx"], 24)

    def test_rank_loop_candidates_prefers_longer_clip_when_no_hint(self):
        ranked = rank_loop_candidates(
            [
                {
                    "score": 0.0001,
                    "start_frame_idx": 90,
                    "end_frame_idx": 110,
                    "end_frame_position": 0.99,
                },
                {
                    "score": 0.0003,
                    "start_frame_idx": 0,
                    "end_frame_idx": 110,
                    "end_frame_position": 0.99,
                },
            ],
            duration_hint=None,
            minimum_loop_frames=5,
            video_duration=120,
        )

        self.assertEqual(ranked[0]["start_frame_idx"], 0)

    def test_rank_loop_candidates_ignores_impossible_duration_hint(self):
        ranked = rank_loop_candidates(
            [
                {
                    "score": 0.2,
                    "start_frame_idx": 0,
                    "end_frame_idx": 40,
                    "end_frame_position": 0.99,
                },
                {
                    "score": 1.0,
                    "start_frame_idx": 0,
                    "end_frame_idx": 100,
                    "end_frame_position": 0.99,
                },
            ],
            duration_hint=360,
            minimum_loop_frames=5,
            video_duration=120,
        )

        self.assertEqual(ranked[0]["end_frame_idx"], 100)

    def test_is_loop_candidate_valid_accepts_boundary_length(self):
        candidate = {
            "start_frame_idx": 10,
            "end_frame_idx": 14,
            "end_frame_position": 0.8,
        }

        self.assertTrue(is_loop_candidate_valid(candidate, minimum_loop_frames=4))

    def test_is_loop_candidate_valid_rejects_short_loop(self):
        candidate = {
            "start_frame_idx": 10,
            "end_frame_idx": 13,
            "end_frame_position": 0.8,
        }

        self.assertFalse(is_loop_candidate_valid(candidate, minimum_loop_frames=4))

    def test_is_loop_candidate_valid_rejects_nan_end_position(self):
        candidate = {
            "start_frame_idx": 10,
            "end_frame_idx": 14,
            "end_frame_position": float("nan"),
        }

        self.assertFalse(is_loop_candidate_valid(candidate, minimum_loop_frames=4))

    def test_is_loop_candidate_valid_rejects_non_positive_end_position(self):
        candidate = {
            "start_frame_idx": 10,
            "end_frame_idx": 14,
            "end_frame_position": 0.0,
        }

        self.assertFalse(is_loop_candidate_valid(candidate, minimum_loop_frames=4))

    def test_select_backoff_candidate_picks_second_when_first_invalid(self):
        candidates = [
            {
                "start_frame_idx": 0,
                "end_frame_idx": 3,
                "end_frame_position": 0.9,
            },
            {
                "start_frame_idx": 0,
                "end_frame_idx": 4,
                "end_frame_position": 0.9,
            },
        ]

        selected = select_backoff_candidate(candidates, minimum_loop_frames=4)
        self.assertEqual(selected["end_frame_idx"], 4)

    def test_select_backoff_candidate_prefers_lowest_backoff_score(self):
        candidates = [
            {
                "start_frame_idx": 0,
                "end_frame_idx": 6,
                "end_frame_position": 0.95,
                "backoff_score": 1.5,
            },
            {
                "start_frame_idx": 0,
                "end_frame_idx": 5,
                "end_frame_position": 0.97,
                "backoff_score": 0.7,
            },
        ]

        selected = select_backoff_candidate(candidates, minimum_loop_frames=4)
        self.assertEqual(selected["end_frame_idx"], 5)

    def test_select_backoff_candidate_falls_back_to_first_valid_when_scores_invalid(self):
        candidates = [
            {
                "start_frame_idx": 0,
                "end_frame_idx": 6,
                "end_frame_position": 0.95,
                "backoff_score": float("nan"),
            },
            {
                "start_frame_idx": 0,
                "end_frame_idx": 5,
                "end_frame_position": 0.97,
                "backoff_score": "invalid",
            },
        ]

        selected = select_backoff_candidate(candidates, minimum_loop_frames=4)
        self.assertIs(selected, candidates[0])

    def test_select_backoff_candidate_returns_first_when_none_valid(self):
        candidates = [
            {
                "start_frame_idx": 0,
                "end_frame_idx": 3,
                "end_frame_position": 0.0,
            },
            {
                "start_frame_idx": 0,
                "end_frame_idx": 3,
                "end_frame_position": float("nan"),
            },
        ]

        selected = select_backoff_candidate(candidates, minimum_loop_frames=4)
        self.assertIs(selected, candidates[0])

    def test_select_backoff_candidate_raises_on_empty(self):
        with self.assertRaises(ValueError):
            select_backoff_candidate([], minimum_loop_frames=4)

    def test_resolve_engine_blend_frames_respects_explicit_request(self):
        candidate = {
            "start_frame_idx": 0,
            "end_frame_idx": 90,
            "end_frame_position": 0.99,
            "score": 0.0002,
        }

        frames = resolve_engine_blend_frames(
            candidate,
            requested_blend_frames=6,
            min_blend_frames=4,
            max_blend_frames=24,
        )

        self.assertEqual(frames, 6)

    def test_resolve_engine_blend_frames_auto_increases_for_bad_seam(self):
        clean_candidate = {
            "start_frame_idx": 0,
            "end_frame_idx": 90,
            "end_frame_position": 0.999,
            "score": 0.0001,
        }
        rough_candidate = {
            "start_frame_idx": 0,
            "end_frame_idx": 90,
            "end_frame_position": 0.85,
            "score": 0.004,
        }

        clean_frames = resolve_engine_blend_frames(
            clean_candidate,
            requested_blend_frames=0,
            min_blend_frames=4,
            max_blend_frames=24,
        )
        rough_frames = resolve_engine_blend_frames(
            rough_candidate,
            requested_blend_frames=0,
            min_blend_frames=4,
            max_blend_frames=24,
        )

        self.assertGreater(rough_frames, clean_frames)

    def test_resolve_engine_blend_frames_clamps_to_loop_length_safety(self):
        candidate = {
            "start_frame_idx": 0,
            "end_frame_idx": 8,
            "end_frame_position": 0.8,
            "score": 0.01,
        }

        frames = resolve_engine_blend_frames(
            candidate,
            requested_blend_frames=0,
            min_blend_frames=4,
            max_blend_frames=24,
        )

        self.assertLessEqual(frames, 3)

    def test_generate_engine_bridge_plan_reverses_head_window(self):
        plan = generate_engine_bridge_plan(loop_frame_count=12, blend_frames=4)

        self.assertEqual([step["tail_index"] for step in plan], [8, 9, 10, 11])
        self.assertEqual([step["head_index"] for step in plan], [3, 2, 1, 0])
        self.assertEqual(plan[-1]["progress"], 1.0)

    def test_generate_engine_bridge_plan_clamps_to_loop_size(self):
        plan = generate_engine_bridge_plan(loop_frame_count=5, blend_frames=20)

        self.assertEqual(len(plan), 4)
        self.assertEqual(plan[0]["tail_index"], 1)
        self.assertEqual(plan[-1]["head_index"], 0)

    def test_generate_engine_bridge_plan_rejects_too_short_loop(self):
        with self.assertRaises(ValueError):
            generate_engine_bridge_plan(loop_frame_count=1, blend_frames=2)

    def test_select_engine_bridge_style_prefers_lower_score_without_history(self):
        style = select_engine_bridge_style(
            blend_score=10.0,
            flow_score=8.0,
            previous_style=None,
            switch_margin=0.05,
        )

        self.assertEqual(style, "flow")

    def test_select_engine_bridge_style_holds_previous_style_on_small_delta(self):
        style = select_engine_bridge_style(
            blend_score=9.7,
            flow_score=10.0,
            previous_style="flow",
            switch_margin=0.05,
        )

        self.assertEqual(style, "flow")

    def test_select_engine_bridge_style_switches_on_clear_improvement(self):
        style = select_engine_bridge_style(
            blend_score=9.0,
            flow_score=10.0,
            previous_style="flow",
            switch_margin=0.05,
        )

        self.assertEqual(style, "blend")

    def test_select_engine_bridge_style_handles_invalid_scores(self):
        style = select_engine_bridge_style(
            blend_score=float("nan"),
            flow_score=4.0,
            previous_style="blend",
            switch_margin=0.05,
        )

        self.assertEqual(style, "flow")

    def test_resolve_engine_switch_margin_uses_default_when_none(self):
        margin = resolve_engine_switch_margin(None, default_margin=0.2)
        self.assertEqual(margin, 0.2)

    def test_resolve_engine_switch_margin_clamps_to_zero(self):
        margin = resolve_engine_switch_margin(-0.4, default_margin=0.05)
        self.assertEqual(margin, 0.0)

    def test_resolve_engine_switch_margin_clamps_to_one(self):
        margin = resolve_engine_switch_margin(2.0, default_margin=0.05)
        self.assertEqual(margin, 1.0)

    def test_resolve_engine_switch_margin_rejects_nan(self):
        with self.assertRaises(ValueError):
            resolve_engine_switch_margin(float("nan"), default_margin=0.05)


if __name__ == "__main__":
    unittest.main()
