# Douyin Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `video`, `image_text` (no mixed image+video) |
| Title / Short Title | Title max **30** chars; optional `short_title` max **12** chars |
| Body / Total Text | Max **1000** characters combined |
| Topics / Tags | Native field supported; max **5** tags |
| Images (`image_text`) | 1–**12** images (`jpg`, `jpeg`, `png`, `bmp`), max **20 MB** each |
| Video | 1 video (`mp4`, `avi`, `mkv`, `mov`), max **100 MB** (OpenAPI baseline; Creator Studio accepts larger), max **900s** |
| Options | `short_title` (<=12), `cover_tsp` (ms), `download_type` (`1` allow / `2` disallow), `private_status` (`0` public / `1` private / `2` friends) |
| Live URL Patterns | `https://www.douyin.com/video/<videoId>` or `https://www.douyin.com/note/<noteId>` |
