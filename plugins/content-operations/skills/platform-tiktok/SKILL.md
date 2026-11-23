---
name: platform-tiktok
description: "Run TikTok end-to-end operations: hook-first short video and photo-carousel discovery, native vertical scripting, strict spec and AIGC checks, TikTok Content Posting API v2 init/poll publishing, and completion-rate retrospectives."
---

# TikTok Operations Playbook

TikTok distributes content strictly on viewer behavior—first-2-second hold, full watch completion, re-watches, saves, and shares—independent of follower count.

## 1. Topic Discovery (Platform-Native)
- **Live discovery**: TikTok Creative Center trends, niche search bar autocomplete, recurring questions in comment sections (great for "reply with video" follow-ups), and fast visual demos.
- **Winning angles**: instant visual proof ("watch what happens when..."), tight 3-step workflows, relatable pain-to-fix stories, and crisp photo carousels (up to 35 slides) for saveable checklists.

## 2. Native Content & Script Structure
- **0–2s Pattern Interrupt**: open mid-action or on a clear visual contrast; put a short on-screen headline in the upper-middle safe zone.
- **Runtime**: 20–60s sweet spot for rapid testing; hard API limit `600s` (10 min). Aspect ratio `9:16` (`1080x1920`).
- **Photo Mode (`image_text`)**: 1–35 images (`jpg`/`jpeg`/`webp`, `<= 20 MB` each), optional `auto_add_music: true` and `photo_cover_index`.
- **Caption (`<= 2200` chars combined)**: concise searchable phrase + 3–5 relevant hashtags.

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate with `check_media_specs.py` against `references/specs.json`.
2. **Default zero-config path (Official TikTok Studio)**: open `https://www.tiktok.com/tiktokstudio/upload` in the user's browser session (pause for login/CAPTCHA if prompted), upload the local video or photo carousel directly from `drafts/<id>/assets/`, fill caption/hashtags/cover and AIGC disclosure, save draft (`draft_saved`) or pause before **Post** until Gate 2 confirmation, then read back the live URL.
3. **Optional official Content Posting API v2 path** (requires `TIKTOK_ACCESS_TOKEN`; rotate 24h token via `scripts/client.py refresh-token` using `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, and `TIKTOK_REFRESH_TOKEN`):
   - Always query `scripts/client.py creator-info` first (`privacy_level` must be in `privacy_level_options`).
   - Direct local video upload: `init-video-file --title ... --file <video.mp4> --privacy ... [--aigc]` → `upload-video-file --upload-url <upload_url> --file <video.mp4>`.
   - Verified-domain URL upload: `init-video-url --title ... --video-url ... --privacy ... [--aigc]` (for inbox drafts or Photo Mode `/content/init/`, see `references/protocol.md`).
   - Poll `publish-status --publish-id <id>` until `PUBLISH_COMPLETE` and read stats via `list-videos` / `account-stats`.
4. Log verified `https://www.tiktok.com/@<username>/video/<id>` in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- TikTok's public Content Posting API does not provide open comment-write endpoints for standard apps; handle comment triage and replies via TikTok Studio / mobile app within 50 actions/day.
- Set `is_aigc: true` truthfully on AI-generated visuals/video, and set `brand_organic_toggle` / `brand_content_toggle` accurately for commercial posts.

## 5. North-Star Metrics (`platformMetrics`)
Track `twoSecHoldRate`, `fullWatchRate`, `avgWatchTimeSec`, `saveRate`, and `shareRate`.
