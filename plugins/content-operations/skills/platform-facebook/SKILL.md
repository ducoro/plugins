---
name: platform-facebook
description: "Run Facebook Page end-to-end operations: community-oriented topic discovery, Feed/Photo/Video/Reels authoring, strict spec checks, Meta Graph API Page publishing and comment engagement, and Page Insights retrospectives."
---

# Facebook Page Operations Playbook

Facebook Pages work best for community discussion, link-supported updates, local/brand announcements, and short Reels discovery. Personal profiles cannot publish via the Pages API—always target an authorized **Facebook Page**.

## 1. Topic Discovery (Platform-Native)
- **Community discussion triggers**: questions in adjacent Facebook Groups, customer stories, relatable visual comparisons, and short vertical Reels repurposed from TikTok/IG.
- **Winning angles**: story-first posts that ask a grounded question, photo sets with clear narrative captions, and native video/Reels (native video beats raw external YouTube links).

## 2. Native Content & Format Rules
- **Modes**: `text`, `image_text` (up to 10 images, `<= 10 MB` each), `video` / Reels (`mp4`/`mov`/`avi`, `<= 1 GB`, `<= 3600s`).
- **Body (`<= 63206` chars; aim 100–400 chars for scannable feed posts)**: hook in lines 1–2 before "See more".
- **Topics**: no native API topic field; use minimal inline hashtags (0–3).

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate against `references/specs.json` with `check_media_specs.py`.
2. **Default zero-config path (Official Meta Business Suite)**: open `https://business.facebook.com/latest/composer` in the user's browser session (pause for login/2FA if prompted), select the target Facebook Page, upload local photos/video directly from `drafts/<id>/assets/`, fill post copy, save draft (`draft_saved`) or pause before **Publish** until Gate 2 confirmation, then record the verified post URL.
3. **Optional official Graph API path** (requires `FACEBOOK_PAGE_ACCESS_TOKEN` & `FACEBOOK_PAGE_ID`):
   - For photo/video URL publishing, upload local assets right before publishing via `ducoro-cli media upload <local-file> --json` to get a 5-hour temporary `publicUrl` (on non-Ducoro hosts, use your own HTTPS storage/CDN).
   - Use `scripts/client.py [--dry-run] <cmd>`: `post-feed`, `post-photo`, `list-posts`, `post-insights`, `page-insights` (multi-photo/video/Reels endpoints in `references/protocol.md`).
4. Record verified `permalink_url` in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- `scripts/client.py` supports `list-comments --post-id <id>` and `reply-comment --object-id <id> --message ...` (likes and deletes follow `references/protocol.md`). Stay within 60 actions/day.
- Reply promptly to early questions to sustain discussion threads.

## 5. North-Star Metrics (`platformMetrics`)
Track `postReach`, `postClicks`, `shares`, `commentDepth`, and `pageFollows`.
