---
name: platform-threads
description: "Run Threads end-to-end operations: conversational topic discovery, crisp 500-char posts with single native topic tags, Threads API two-step container publishing, reply management, and conversation-depth retrospectives."
---

# Threads Operations Playbook

Threads favors natural, human, low-jargon conversation. Replies and sustained back-and-forth threads drive far more distribution than polished announcements.

## 1. Topic Discovery (Platform-Native)
- **Conversational signals**: relatable practitioner observations, candid "what I learned today" notes, quick polls/questions, and behind-the-scenes snapshots.
- **Avoid**: recycled press-release language or heavy hashtag lists (Threads natively supports **1** `topic_tag` per post).

## 2. Native Content & Format Rules
- **Text (`<= 500` chars combined)**: conversational opening, concrete opinion or story, optional open-ended question to invite replies.
- **Media**: `text`, `image_text` (up to 10 `jpg`/`png` images, `<= 8 MB` each), or `video` (`mp4`/`mov`, `<= 1 GB`, `<= 300s`).
- **Topic tag**: native `topic_tag` field—max **1** clean topic tag (no `#` prefix required when passed via API `topic_tag`).

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate against `references/specs.json` via `check_media_specs.py`.
2. **Default zero-config path (Official Threads Web App)**: open `https://www.threads.net/` in the user's browser session (pause for login/2FA if prompted), click **New Thread**, attach local images/video directly from `drafts/<id>/assets/`, add the single topic tag, save draft (`draft_saved`) or pause before **Post** until Gate 2 confirmation, then record the live permalink.
3. **Optional official Threads API path** (requires `THREADS_ACCESS_TOKEN` & `THREADS_USER_ID`):
   - For image/video containers, upload local assets right before publishing via `ducoro-cli media upload <local-file> --json` to get a 5-hour temporary `publicUrl` (on non-Ducoro hosts, use your own HTTPS storage/CDN).
   - Use `scripts/client.py [--dry-run] <cmd>`: `create-container` (or child items + `create-carousel`), poll `container-status` until `FINISHED`, `publish`, `get-post`, and `insights`.
4. Record the verified permalink in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- `scripts/client.py` supports `list-replies --post-id <id>`, replying (`create-container --reply-to <id> ...` + `publish`), and hiding/unhiding (`manage-reply --reply-id <id> --hide true|false`).
- Keep engagement under 60 actions/day and respond authentically within the first 2 hours.

## 5. North-Star Metrics (`platformMetrics`)
Track `replyToViewRatio`, `quoteCount`, `repostCount`, and `views`.
