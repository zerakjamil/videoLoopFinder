"""Utility functions for multi-start loop scanning."""


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


def format_ranked_candidates(results, top_n=5):
    """Format ranked loop candidates for terminal output."""
    if top_n <= 0:
        return "Top 0 candidate loops (lower score is better):"

    ranked = sorted(results, key=lambda result: result["score"])[:top_n]
    lines = [
        f"Top {len(ranked)} candidate loops (lower score is better):"
    ]
    for rank, result in enumerate(ranked, start=1):
        lines.append(
            "{rank}. score={score:.6f} start={start} end={end} "
            "end_pos={end_pos:.6f}".format(
                rank=rank,
                score=result["score"],
                start=result["start_frame_idx"],
                end=result["end_frame_idx"],
                end_pos=result["end_frame_position"],
            )
        )

    return "\n".join(lines)
