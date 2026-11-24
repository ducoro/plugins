# Video Packaging, Safe Zones, Audio & Subtitle Standards

Platform-neutral engineering and packaging reference for short vertical and long horizontal video. Creative style, pacing, and tone belong to the creator—these are the objective delivery standards and platform UI realities that prevent clipped captions, muted audio, or failed uploads.

## 1. Platform UI Safe Zones (`1080x1920` Vertical `9:16`)

Platform chrome overlays (top search/tabs, right action rail, bottom caption/audio bar) cover fixed regions of the frame. Keep essential titles, faces, and burned-in subtitles inside the clear center box:

| Platform | Top Margin | Bottom Margin | Right Margin | Left Margin | Clear Center Box |
| --- | --- | --- | --- | --- | --- |
| **Douyin / TikTok** | `220 px` (11.5%) | `420 px` (22%) | `160 px` (15%) | `60 px` (5.5%) | `x: 60–920`, `y: 220–1500` |
| **WeChat Channels** | `200 px` (10.5%) | `400 px` (21%) | `150 px` (14%) | `60 px` (5.5%) | `x: 60–930`, `y: 200–1520` |
| **YouTube Shorts** | `210 px` (11%) | `380 px` (20%) | `140 px` (13%) | `60 px` (5.5%) | `x: 60–940`, `y: 210–1540` |
| **Instagram Reels** | `220 px` (11.5%) | `420 px` (22%) | `140 px` (13%) | `60 px` (5.5%) | `x: 60–940`, `y: 220–1500` |
| **Kuaishou** | `210 px` (11%) | `420 px` (22%) | `150 px` (14%) | `60 px` (5.5%) | `x: 60–930`, `y: 210–1500` |
| **16:9 Landscape (`1920x1080`)** | `80 px` | `140 px` (player scrub bar) | `80 px` | `80 px` | Keep subtitles `y <= 940` |

## 2. Export, Audio Loudness & Color Standards

- **Container & codec**: `MP4` (`H.264 / avc1` Main or High profile, `yuv420p`, `AAC-LC 48 kHz 128–192 kbps`, `-movflags +faststart`).
- **Color space**: Tag exports as **Rec.709 (`bt709`)** (`-colorspace bt709 -color_primaries bt709 -color_trc bt709`) to prevent washed-out gamma shifts on iOS/WeChat/Safari players.
- **Audio loudness**: Target **`-14 LUFS`** integrated loudness (`-1.0 dBTP` true peak ceiling), which matches YouTube, TikTok, Douyin, and Bilibili normalization. Keep background music **18–24 dB below spoken vocals**. Verify with `python3 scripts/video_ops.py probe <file.mp4> --loudness`.

## 3. Speaking-Rate & Subtitle Benchmarks

- **Spoken pace**: Chinese narration averages **240–280 chars/min** (fast short-video commentary ~300, calm storytelling ~210); English narration averages **130–160 words/min**. Estimate script duration with `scripts/video_ops.py estimate-duration <script.md>`.
- **Subtitle legibility**: Max **16–18 CJK chars/line** or **38–42 EN chars/line**, at most **2 lines per cue**, minimum ~1.0s display duration. Validate SRT timing and overlaps with `scripts/video_ops.py validate-srt <file.srt>`.

## 4. Production Paths & Metadata Contract

- **Programmatic / code-driven video**: Remotion or HyperFrames rendered deterministically to `H.264/AAC MP4`.
- **Footage / screen recordings / external edits**: Package with timed `script.md`, validated `.srt`, and clean thumbnail (`1280x720` for YouTube/Bilibili, `1080x1440` or `1080x1920` for vertical feeds).
- **Variant JSON**: Put the cover in top-level `"cover": {"path": "assets/cover.jpg"}` (never inside `media[]`), and declare `"durationSec"` (auto-verified against real `ffprobe` when available).

## 5. Line-Indexed Long-to-Short Clipping Workflow

When turning a long-form recording (podcast, talk, tutorial, walkthrough) into standalone short vertical clips:
1. Run `video_ops.py index-transcript <captions.srt|vtt> --text-only` to print 0-indexed cues (`index [start - end] text`).
2. Select self-contained arcs that open with a hook, complete one clear point, and stay within target duration bounds (default `20–90s`, adjustable via `--min-sec` / `--max-sec`). Reference **cue indices** (`from`, `to`) rather than hand-calculated timestamps so clips always start and end on true spoken boundaries:
   ```json
   {
     "clips": [
       { "from": 0, "to": 11, "title": "Opening thesis", "caption": "Draft social caption..." },
       { "from": 24, "to": 39, "title": "Concrete example", "caption": "Draft social caption..." }
     ]
   }
   ```
3. Run `video_ops.py plan-clips` to verify bounds, duration, and zero overlap deterministically, then `video_ops.py slice-clips` to emit `H.264/AAC bt709` MP4 slices, rebased `00:00:00,000` `.srt` files, and `clips-manifest.json`.
