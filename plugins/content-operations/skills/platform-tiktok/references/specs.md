# TikTok Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `video`, `image_text` (Photo Mode; never mix image + video) |
| Caption / Total Text | Max **2200** characters combined |
| Images (`image_text`) | 1–**35** images (`jpg`, `jpeg`, `webp`), max **20 MB** each (PULL_FROM_URL requires verified domain) |
| Video | 1 video (`mp4`, `mov`, `webm`), max **4 GB**, max **600s** |
| Options | `privacy_level` (must be in `creator_info.privacy_level_options`), `disable_duet`, `disable_stitch`, `disable_comment`, `brand_organic_toggle`, `brand_content_toggle`, `is_aigc`, `auto_add_music`, `photo_cover_index`, `source` (`FILE_UPLOAD` \| `PULL_FROM_URL`) |
| Live URL Patterns | `https://www.tiktok.com/@<username>/video/<id>` or `/photo/<id>` |
