# Instagram Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `image_text` (Feed / Carousel / Story), `video` (Reels / Story) |
| Caption Length | Max **2200** characters |
| Hashtags | Max **30** (recommended 3–8) |
| Images (Graph API) | 1–**10** images, **`jpg`/`jpeg` only**, max **8 MB** each, Feed aspect ratio **`0.8` (`4:5`) – `1.91`** |
| Video (Reels) | 1 video (`mp4`, `mov`), **3–900s**, max **300 MB** (`<= 1 GB` generic feed) |
| Video (Story) | 1 video (`mp4`, `mov`), **3–60s**, max **100 MB** |
| Options | `media_type` (`IMAGE` \| `REELS` \| `STORIES` \| `CAROUSEL`), `alt_text` (`<= 1000`), `cover_url`, `collaborators` (max 3), `location_id`, `user_tags`, `product_tags` |
| Publish Strategy | Two-step async container (`/<igUserId>/media` → poll `FINISHED` → `/<igUserId>/media_publish`) |
