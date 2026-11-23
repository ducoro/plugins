---
name: platform-instagram
description: "Run Instagram end-to-end operations: visual carousel, Reels, and Story planning, strict 4:5 to 1.91:1 aspect-ratio and JPEG checks, Instagram Graph API two-step container publishing, comment engagement, and reach/save Insights retrospectives."
---

# Instagram Operations Playbook

Instagram runs on visual craft, carousel swipe-throughs, Reels watch time, and DM/send shares ("sends per reach" is a primary discovery signal).

## 1. Topic Discovery (Platform-Native)
- **Visual & shareable signals**: Explore tab niche formats, saveable 5–10 slide carousels, quick Reels visual hooks, and collaborator-ready co-posts (`collaborators <= 3`).
- **Winning angles**: visual frameworks, aesthetic before/after reveals, tight tutorial Reels (`15–45s`), and swipeable checklists.

## 2. Native Content & Format Rules
- **Feed / Carousel (`IMAGE` / `CAROUSEL`)**: `jpg`/`jpeg` **only** via Graph API (`<= 8 MB`), aspect ratio strictly **`0.8` (`4:5`) to `1.91` (`1.91:1`)**—`4:5` (`1080x1350`) maximizes mobile screen real estate. Up to **10** carousel items.
- **Reels (`REELS`)**: `mp4`/`mov`, `9:16` vertical, `3–900s` (`<= 300 MB`), optional `cover_url`.
- **Stories (`STORIES`)**: `9:16`, video `3–60s` (`<= 100 MB`) or JPEG image (`<= 8 MB`).
- **Caption (`<= 2200` chars)**: punchy opening line before the fold (~125 chars), clean line breaks, 3–8 targeted hashtags (hard cap 30), optional `alt_text` (`<= 1000` chars).

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate ratio (`0.8–1.91` for Feed `IMAGE`/`CAROUSEL`; `STORIES` and `REELS` are exempt from the Feed aspect-ratio band when `options.media_type` is set), JPEG format, and caption length via `check_media_specs.py`.
2. **Default zero-config path (Official Web / Meta Business Suite)**: open `https://business.facebook.com/latest/composer` or `https://www.instagram.com/` in the user's browser session (pause for login/2FA if prompted), upload local images/Reels directly from `drafts/<id>/assets/`, fill caption and alt text, save draft (`draft_saved`) or pause before **Share / Publish** until Gate 2 approval, then read back the live permalink.
3. **Optional official Graph API path** (requires `INSTAGRAM_ACCESS_TOKEN` & `INSTAGRAM_USER_ID`):
   - Check quota via `scripts/client.py quota`.
   - Just before publishing (not days ahead at scheduling time), upload local assets via `ducoro-cli media upload <local-file> --json` to get a 5-hour temporary `publicUrl` (on non-Ducoro hosts, use your own HTTPS storage/CDN).
   - Run two-step container publish via `scripts/client.py`: `create-container` (or child containers + `create-carousel`), poll `container-status` until `FINISHED`, `publish`, and verify via `get-media` (`media-insights` and `account-insights` also available).
4. Record the verified permalink in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- `scripts/client.py` supports `list-comments --media-id <id>`, `reply-comment --comment-id <id> --message ...`, and `delete-comment --comment-id <id>` (comment hiding uses `protocol.md`). Stay under 50 actions/day.
- Requires an Instagram Professional (Business or Creator) account.

## 5. North-Star Metrics (`platformMetrics`)
Track `sendsPerReach`, `saveRate`, `reach`, `profileVisits`, and `reelsAvgWatchTime`.
