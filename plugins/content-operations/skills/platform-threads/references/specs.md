# Threads Hard Specifications

| Field | Limit / Rule |
| --- | --- |
| Supported Modes | `text`, `image_text`, `video` (no mixed image+video in single post; carousel items up to 10) |
| Body / Total Text | Max **500** characters |
| Topic Tag | Native `topic_tag`; max **1** topic per post |
| Images | 1–**10** images (`jpg`, `jpeg`, `png`), max **8 MB** each |
| Video | 1 video (`mp4`, `mov`), max **1 GB**, max **300s** |
| Options | `firstReply` (validated follow-up reply `<= 500` chars), `reply_control` (`everyone` \| `accounts_you_follow` \| `mentioned_only`), `topic_tag`, `reply_to_id`, `location_id` |
| Publish Strategy | Two-step container (`/<userId>/threads` → poll `FINISHED` → `/<userId>/threads_publish`) |
