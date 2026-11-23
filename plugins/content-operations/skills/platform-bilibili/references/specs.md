# Bilibili Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `video` only |
| Title Length | Max **79** characters |
| Description (`desc`) | Max **249** characters |
| Tags (`tag`) | Native comma-separated field; total length max **199** characters |
| Video | 1 video (`mp4`, `flv`), max **4 GB**, max **18000s** (5 hours) |
| Cover Image | `jpg`, `jpeg`, `png`, max **5 MB**, `16:9` recommended |
| Required Options | `tid` (positive integer partition ID), `copyright` (`1` original / `2` reprint; if `2`, `source` is required) |
| Optional Options | `no_reprint` (`0` allow / `1` disallow), `topic_id`, `mission_id` |
| Live URL Pattern | `https://www.bilibili.com/video/<BVid>` (matches `^(?:BV[0-9A-Z]+|av\d+)$`) |
