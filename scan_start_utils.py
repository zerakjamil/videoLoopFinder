"""Utility functions for multi-start loop scanning."""

import math
import statistics


def resolve_scan_duration_hint(start_frame_idx, duration_hint):
    """Resolve duration hint when --scan-starts is enabled.

    In scan mode, a single positional integer is interpreted as DURATION_HINT to
    keep CLI usage concise and backward compatible with docopt parsing.
    """
    if duration_hint is not None:
        return duration_hint
    return start_frame_idx


def generate_start_frame_indices(video_duration, start_step, start_max):
    """Generate candidate start frame indices for scan mode.

    Args:
        video_duration: Number of frames in the source video.
        start_step: Step size between candidate starts.
        start_max: Highest candidate start frame index (inclusive). A value of 0 means
            "scan as far as possible".

    Returns:
        A list of candidate start frame indices.
    """
    if start_step <= 0:
        raise ValueError("start_step must be > 0")
    if video_duration <= 0:
        raise ValueError("video_duration must be > 0")

    max_valid_start = max(0, video_duration - 2)
    if start_max is None or start_max <= 0:
        effective_max = max_valid_start
    else:
        effective_max = min(start_max, max_valid_start)

    return list(range(0, effective_max + 1, start_step))


def is_loop_candidate_valid(candidate, minimum_loop_frames):
    """Return True when candidate is loopable enough to export.

    A candidate is considered valid when it has a sufficient positive loop
    length and a finite relative end-frame position in the open interval (0, 1].
    """
    if minimum_loop_frames < 1:
        raise ValueError("minimum_loop_frames must be >= 1")

    start_frame_idx = int(candidate["start_frame_idx"])
    end_frame_idx = int(candidate["end_frame_idx"])
    loop_length = end_frame_idx - start_frame_idx
    if loop_length < minimum_loop_frames:
        return False

    try:
        end_frame_position = float(candidate.get("end_frame_position"))
    except (TypeError, ValueError):
        return False

    if not math.isfinite(end_frame_position):
        return False

    return 0.0 < end_frame_position <= 1.0


def select_backoff_candidate(candidates, minimum_loop_frames):
    """Select the best valid candidate in backoff order.

    The input must already be ordered from preferred to less-preferred end
    frame indices (e.g. N-1, N-2, N-3, ...).

    Selection strategy:
    1) choose the valid candidate with lowest finite ``backoff_score`` when present
    2) otherwise choose the first valid candidate in order
    3) if none are valid, return the first entry for deterministic fallback
    """
    if len(candidates) == 0:
        raise ValueError("candidates must not be empty")

    first_valid_idx = None
    best_scored_idx = None
    best_scored_rank = None

    for idx, candidate in enumerate(candidates):
        if is_loop_candidate_valid(candidate, minimum_loop_frames):
            if first_valid_idx is None:
                first_valid_idx = idx

            try:
                candidate_score = float(candidate.get("backoff_score"))
            except (TypeError, ValueError):
                continue

            if not math.isfinite(candidate_score):
                continue

            rank = (candidate_score, idx)
            if best_scored_rank is None or rank < best_scored_rank:
                best_scored_rank = rank
                best_scored_idx = idx

    if best_scored_idx is not None:
        return candidates[best_scored_idx]

    if first_valid_idx is not None:
        return candidates[first_valid_idx]

    return candidates[0]


def format_ranked_candidates(results, top_n=5):
    """Format ranked loop candidates for terminal output."""
    if top_n <= 0:
        return "Top 0 candidate loops (lower score is better):"

    sort_key = "rank_score" if any("rank_score" in result for result in results) else "score"
    ranked = sorted(results, key=lambda result: result[sort_key])[:top_n]
    if sort_key == "rank_score":
        lines = [f"Top {len(ranked)} candidate loops (lower rank score is better):"]
    else:
        lines = [f"Top {len(ranked)} candidate loops (lower score is better):"]

    for rank, result in enumerate(ranked, start=1):
        loop_length = result["end_frame_idx"] - result["start_frame_idx"]
        lines.append(
            "{rank}. score={score:.6f} rank={rank_score:.6f} start={start} "
            "end={end} len={loop_length} end_pos={end_pos:.6f}".format(
                rank=rank,
                score=result["score"],
                rank_score=result.get("rank_score", result["score"]),
                start=result["start_frame_idx"],
                end=result["end_frame_idx"],
                loop_length=loop_length,
                end_pos=result["end_frame_position"],
            )
        )

    return "\n".join(lines)


def rank_loop_candidates(
    candidates,
    duration_hint,
    minimum_loop_frames,
    video_duration=None,
):
    """Rank loop candidates using score plus consistency penalties.

    Lower values are better.
    """
    if minimum_loop_frames < 1:
        raise ValueError("minimum_loop_frames must be >= 1")

    effective_duration_hint = duration_hint
    if (
        effective_duration_hint is not None
        and effective_duration_hint > 0
        and video_duration is not None
        and video_duration > 0
        and effective_duration_hint >= video_duration
    ):
        # Ignore impossible hints (loop length cannot exceed remaining video).
        effective_duration_hint = None

    finite_scores = []
    for candidate in candidates:
        score = float(candidate["score"])
        if math.isfinite(score):
            finite_scores.append(score)

    score_scale = statistics.median(finite_scores) if finite_scores else 1.0
    if score_scale <= 0:
        score_scale = 1.0

    ranked = []
    for candidate in candidates:
        ranked_candidate = dict(candidate)
        score = float(ranked_candidate["score"])
        start_frame_idx = ranked_candidate["start_frame_idx"]
        end_frame_idx = ranked_candidate["end_frame_idx"]
        loop_length = end_frame_idx - start_frame_idx
        positive_loop_length = max(0, loop_length)
        end_position = ranked_candidate.get("end_frame_position")

        penalty = 0.0

        if not math.isfinite(score):
            penalty += 10000.0

        if loop_length < minimum_loop_frames:
            penalty += 1000.0 + (minimum_loop_frames - loop_length)

        if video_duration is not None and video_duration > 0:
            loop_coverage = positive_loop_length / float(video_duration)
            if effective_duration_hint is None:
                # In automatic scan mode, prefer keeping more of the original clip and
                # trimming only what is necessary.
                penalty += 3.0 * (1.0 - min(1.0, loop_coverage))
            else:
                removed_frames = max(0, start_frame_idx) + max(
                    0,
                    video_duration - 1 - end_frame_idx,
                )
                penalty += 0.25 * removed_frames / float(video_duration)

        if effective_duration_hint is not None and effective_duration_hint > 0:
            penalty += 2.0 * abs(loop_length - effective_duration_hint) / float(
                effective_duration_hint
            )

        try:
            end_position = float(end_position)
        except (TypeError, ValueError):
            penalty += 1000.0
        else:
            if not math.isfinite(end_position):
                penalty += 1000.0
            else:
                penalty += 8.0 * abs(1.0 - end_position)
            if end_position <= 0:
                penalty += 20.0

        ranked_candidate["rank_score"] = score + score_scale * penalty
        ranked.append(ranked_candidate)

    return sorted(ranked, key=lambda candidate: candidate["rank_score"])


def resolve_engine_blend_frames(
    candidate,
    requested_blend_frames,
    *,
    min_blend_frames,
    max_blend_frames,
):
    """Resolve how many synthetic bridge frames should be added at loop seam.

    If requested_blend_frames > 0, it is respected (with safety clamping).
    Otherwise, a value is estimated from seam quality so cleaner seams get
    fewer synthetic frames and rougher seams get more.
    """
    if min_blend_frames < 1:
        raise ValueError("min_blend_frames must be >= 1")
    if max_blend_frames < min_blend_frames:
        raise ValueError("max_blend_frames must be >= min_blend_frames")

    loop_length = max(1, int(candidate["end_frame_idx"]) - int(candidate["start_frame_idx"]) + 1)
    hard_max = max(1, min(max_blend_frames, max(1, loop_length // 3)))
    hard_min = min(min_blend_frames, hard_max)

    if requested_blend_frames is not None and requested_blend_frames > 0:
        return max(1, min(int(requested_blend_frames), hard_max))

    end_position = candidate.get("end_frame_position")
    try:
        end_position = float(end_position)
    except (TypeError, ValueError):
        seam_position_error = 1.0
    else:
        if math.isfinite(end_position):
            seam_position_error = abs(1.0 - end_position)
        else:
            seam_position_error = 1.0

    try:
        seam_score = float(candidate.get("score", 0.0))
    except (TypeError, ValueError):
        seam_score = 1.0

    if not math.isfinite(seam_score) or seam_score < 0:
        seam_score = 1.0

    # Typical match scores are around 1e-4 ... 1e-3. Higher means rough seam.
    normalized_score = min(1.0, seam_score / 0.0025)
    severity = min(1.0, max(seam_position_error * 20.0, normalized_score))

    resolved = int(round(hard_min + severity * (hard_max - hard_min)))
    return max(1, min(resolved, hard_max))


def generate_engine_bridge_plan(loop_frame_count, blend_frames):
    """Create a bridge synthesis plan for loop-engine export.

    The plan maps tail frames to a reversed head-window so early bridge frames
    start close to the tail and the final bridge frame converges to frame 0.
    """
    if loop_frame_count < 2:
        raise ValueError("loop_frame_count must be >= 2")
    if blend_frames <= 0:
        return []

    effective_blend = min(int(blend_frames), loop_frame_count - 1)
    tail_start = loop_frame_count - effective_blend

    plan = []
    for i in range(effective_blend):
        tail_index = tail_start + i
        head_index = max(0, effective_blend - 1 - i)
        progress = float(i + 1) / float(effective_blend)
        plan.append(
            {
                "tail_index": tail_index,
                "head_index": head_index,
                "progress": progress,
            }
        )

    return plan


def select_engine_bridge_style(
    *,
    blend_score,
    flow_score,
    previous_style,
    switch_margin=0.05,
):
    """Select bridge synthesis style with temporal hysteresis.

    Lower scores are better. The selector only switches away from
    previous_style when the alternative improves by at least switch_margin.
    """
    try:
        blend_score = float(blend_score)
    except (TypeError, ValueError):
        blend_score = float("inf")

    try:
        flow_score = float(flow_score)
    except (TypeError, ValueError):
        flow_score = float("inf")

    blend_valid = math.isfinite(blend_score)
    flow_valid = math.isfinite(flow_score)

    if not blend_valid and not flow_valid:
        return previous_style if previous_style in {"blend", "flow"} else "blend"
    if not blend_valid:
        return "flow"
    if not flow_valid:
        return "blend"

    margin = max(0.0, float(switch_margin))
    if previous_style == "flow":
        if blend_score <= flow_score * (1.0 - margin):
            return "blend"
        return "flow"

    if previous_style == "blend":
        if flow_score <= blend_score * (1.0 - margin):
            return "flow"
        return "blend"

    return "flow" if flow_score <= blend_score else "blend"


def resolve_engine_switch_margin(value, default_margin=0.05):
    """Resolve and clamp loop-engine auto switch margin to [0, 1]."""
    if value is None:
        margin = float(default_margin)
    else:
        margin = float(value)

    if not math.isfinite(margin):
        raise ValueError("engine switch margin must be finite")

    return min(1.0, max(0.0, margin))
