---
name: platform-youtube
description: Run YouTube end-to-end video operations: search and browse topic discovery, thumbnail-and-title packaging for long-form and Shorts, YouTube Data API v3 upload/update/comment workflows, and CTR plus watch-time retrospectives.
---

# YouTube Operations Playbook

YouTube distributes long-form videos through two sequential gates—**Impression CTR** (title + thumbnail promise) and **Average View Duration / Satisfaction**—and distributes Shorts (`<= 60s` vertical) through swipe-away rate and completion.

## 1. Topic Discovery (Platform-Native)
- **Packaging before scripting**: test title + thumbnail concept before writing the script; if the promise is weak in 60 characters, fix the topic angle first.
- **Sources**: YouTube search autocomplete, outlier videos on smaller channels (high views vs. subscriber count), viewer questions in comment threads, and deep-dive walkthroughs that hold evergreen search demand.

## 2. Native Content & Packaging Structure
- **Title (`<= 100` chars; aim `<= 65` chars)**: front-load curiosity or concrete outcome so mobile truncation never hides the hook.
- **Thumbnail (`16:9`, `1280x720`, `< 2 MB`)**: max 3 visual elements, 2–5 words complementing (never duplicating verbatim) the title.
- **Description (`<= 5000` chars)**: first 2 lines carry the core summary + canonical link; include `00:00` chapters for long-form videos so YouTube indexes key moments.
- **Tags (`<= 500` total chars)**: supporting synonyms and common misspellings; never rely on tags to fix weak packaging.
- **Video specs**: `mp4`/`mov`/`mkv`/`avi`/`wmv`/`flv`, up to 256 GB / 12h. Scheduled `publishAt` requires `privacyStatus: "private"`.

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate against `references/specs.json` with `check_media_specs.py`.
2. **Default zero-config path (Official YouTube Studio)**: open `https://studio.youtube.com/` in the user's browser session (pause for Google sign-in/2FA if prompted), click **Create → Upload videos**, upload local video + `1280x720` thumbnail directly from `drafts/<id>/assets/`, fill title/description/tags/audience, save as **Private / Unlisted** draft (`draft_saved`) until Gate 2 approval, then switch visibility or schedule and copy the verified `watch?v=<id>` URL.
3. **Optional official Data API v3 path** (requires `YOUTUBE_ACCESS_TOKEN`; rotate 1h token via `scripts/client.py refresh-token` using `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN`):
   - `list-categories --region US`, `init-upload --title ... --privacy private [--publish-at ...]`, `upload-video --upload-url <uploadLocation> --file <video.mp4>`, `set-thumbnail --video-id <id> --file <thumb.jpg>`.
   - Read back stats and comments via `video-stats`, `list-comments`, `reply-comment`.
4. Record verified `https://www.youtube.com/watch?v=<videoId>` in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- Pin a top comment with key links or a focused discussion prompt right after publish.
- Use `commentThreads` and `comments` endpoints to read and reply within daily YouTube API quota units (`10,000` units/day default; each `videos.insert` costs ~1600 units, `comments.insert` costs 50 units).
- Always set `selfDeclaredMadeForKids` truthfully (`false` for general/adult tech & business content).

## 5. North-Star Metrics (`platformMetrics`)
Track `impressionCtr`, `avgViewDurationSec`, `avgViewPercentage`, `subscribersGained`, and `shortsStayedToWatchRate`.
