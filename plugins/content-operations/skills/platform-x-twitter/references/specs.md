# X (Twitter) Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `text`, `image_text`, `video` (never mix images and video in one tweet) |
| Title Length | None (`0`) |
| Body / Total Text | Max **280** characters (standard API baseline; URLs count as 23 chars via t.co) |
| Topics / Hashtags | Inline `#tag` supported; recommended 0–2 |
| Images | 1–**4** images (`jpg`, `jpeg`, `png`, `gif`, `webp`), max **5 MB** each (GIF 15 MB) |
| Video | 1 video (`mp4`, `mov`), max **512 MB**, max **140s** (standard baseline) |
| Options | `reply_to_tweet_id`, `quote_tweet_id`, `reply_settings`, `poll` (2–4 options <= 25 chars, 5–10080 min), `alt_text` (<= 1000 chars), `made_with_ai`, `paid_partnership` |
| Live URL Pattern | `https://x.com/i/status/<tweetId>` |
