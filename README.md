# video-loop-finder

Tool to find matching start and end points in a looping video, e.g. in a concentric mosaic light field dataset.

## Setup

Install depencencies listed in `environment.yml`.
If Anaconda is set up, simply run:

```bash
conda env create -f environment.yml
```

## Usage

Check `video_loop_finder.py --help` for possible options.

```text
Video Loop Finder

USAGE:
    video_loop_finder.py [options] VIDEO_PATH [START_FRAME_IDX [DURATION_HINT]]

ARGUMENTS:
    VIDEO_PATH          Path to a video file or printf-style escaped path to image
                        sequence, e.g. '/path/to/image%04d.png'
    START_FRAME_IDX     Index of first frame of loop [default: 0]
                        In --scan-starts mode, a single positional integer is
                        interpreted as DURATION_HINT for convenience
    DURATION_HINT       Estimated duration of loop in frames [default: video duration]

OPTIONS:
    -r RANGE --range=RANGE          Search for end frame ±RANGE frames around
                                    START_FRAME + DURATION_HINT [default: 50]
    -w WIDTH --width=WIDTH          Image width in pixels used in computations. Set to 0
                                    to use full original image resolution [default: 256]
    -f PIXELS --flow-filter=PIXELS  Filters out optical flow vectors that,
                                    when chaining forward and backward flows together,
                                    do not map back onto themselves within PIXELS. Set
                                    to 'off' to disable filtering. [default: 0.2]
    --scan-starts                   Evaluate multiple candidate start frames and pick
                                    the best loop overall
    --start-step=STEP               Step size between candidate start frames when
                                    scan mode is enabled [default: 12]
    --start-max=MAX                 Maximum candidate start frame index (inclusive)
                                    in --scan-starts mode. Set to 0 to scan as far as
                                    possible [default: 0]
    --loop-engine                   Enable loop-engine export mode that synthesizes
                                    seam bridge frames for smoother looping
    --engine-blend=FRAMES           Number of seam bridge frames. Set to 0 for
                                    automatic estimation [default: 0]
    --engine-min-blend=FRAMES       Minimum auto-estimated seam bridge frames in
                                    --loop-engine mode [default: 4]
    --engine-max-blend=FRAMES       Maximum auto-estimated seam bridge frames in
                                    --loop-engine mode [default: 24]
    --engine-style=STYLE            Seam synthesis style in loop-engine mode:
                                    auto, flow, or blend [default: auto]
    --engine-switch-margin=RATIO    Relative improvement required before auto style
                                    switches between flow and blend. Set to 0 to
                                    disable hysteresis [default: 0.05]
    -i --interactive                Enable interactive alignment of start and end frames
    -d --debug                      Enable more verbose logging and plot intermediate
                                    results
    -o --outfile=OUTFILE            Save trimmed version of video in OUTFILE
    --ffmpeg-opts=OPTS              Pass options OPTS (one quoted string) to ffmpeg,
                                    e.g. --ffmpeg-opts="-b:v 1000 -c:v h264 -an"
    -h --help                       Show this help text


DESCRIPTION:

Finds a loop in a repeating video, such as a concentric mosaic dataset, stored in
VIDEO_PATH.

This script will find the best matching frame pair in terms of lowest sum of absolute
pixel differences and localise the end frame relative to the actual beginning/end of the
loop.

For example, if in a concentric mosaic video, the first frame is assumed at 0° and the
closest end frame is found at 359.1°, then the relative position of the latter is
359.1°/360° = 99.75%.
```

Scan mode example:

```bash
video_loop_finder.py --scan-starts --start-step=12 --start-max=240 input.mp4 360
```

This evaluates candidate starts 0, 12, 24, ... up to 240, prints a ranked top-5 list,
and then reports the best loop candidate.

If the initially detected end frame is not loopable (for example, invalid end position
or too-short seam), the tool now evaluates nearby seam candidates in a bounded local
window (prioritizing `end`, `end-1`, `end-2`, ...) and picks the best valid seam by a
composite quality score.

When exporting with `-o/--outfile`, quality-preserving ffmpeg defaults are applied if
you did not explicitly provide codec/quality flags in `--ffmpeg-opts`.

Loop engine export example:

```bash
video_loop_finder.py --scan-starts --loop-engine -o loop_engine.mp4 input.mp4 360
```

With `--loop-engine`, the tool auto-estimates how many bridge frames to synthesize
at the seam (or you can set `--engine-blend` explicitly) to improve boundary quality
when the clip repeats.

`--engine-style auto` now evaluates flow and blend candidates per bridge frame,
chooses the lower-discontinuity result, and uses a small hysteresis margin to
avoid style flicker on near-tie frames. `--engine-style flow` prefers optical-flow
motion morphing and falls back to blend if flow fails on a frame.

Tune the auto switching sensitivity with `--engine-switch-margin`:
lower values switch styles more aggressively, while higher values keep style
choices more stable unless there is a clearer quality win.

For highest visual quality on complex motion, try:

```bash
video_loop_finder.py --scan-starts --loop-engine --engine-style flow -o loop_engine.mp4 input.mp4 360
```
