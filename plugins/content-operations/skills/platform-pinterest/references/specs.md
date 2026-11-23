# Pinterest Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `image_text` (1 image), `video` (1 video) |
| Title Length | Max **100** characters |
| Description Length | Max **800** characters |
| Images | **1** image (`jpg`, `jpeg`, `png`, `webp`, `bmp`, `tiff`), max **20 MB**; `2:3` (`1000x1500`) optimal |
| Video | **1** video (`mp4`, `m4v`, `mov`), max **300s** |
| Topics | No native topic field |
| Required Options | `board_id` (from `GET /v5/boards`) |
| Optional Options | `link` (HTTPS destination URL), `alt_text`, `dominant_color` |
| Post-Publish Update | Supported (`PATCH /v5/pins/<pinId>`) |
| Live URL Pattern | `https://www.pinterest.com/pin/<pinId>` |
