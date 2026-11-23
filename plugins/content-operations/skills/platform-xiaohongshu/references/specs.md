# Xiaohongshu (RedNote) Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `image_text`, `video` (never mix images and video in one note) |
| Title Length | Max **20** characters |
| Body Length | Max **1000** characters |
| Topics / Tags | Native field supported; recommended max **5** tags |
| Images | 1–**9** images (`jpg`, `jpeg`, `png`, `bmp`, `webp`), max **20 MB** each |
| Recommended Image Ratio | `3:4` (`1080x1440`) primary; `1:1` acceptable; avoid extreme wide crops |
| Video | 1 video (`mp4`, `avi`, `mkv`, `mov`, `webm`), max **1 GB**, max **3600s** (practical sweet spot 30–180s) |
| Platform Scheduling / Post-Edit | Handled in Creator Studio; no public API update flow |
| Live URL Pattern | `https://www.xiaohongshu.com/explore/<noteId>` |
