---
name: platform-x-twitter
description: Run X (Twitter) end-to-end operations: live discourse topic discovery, punchy posts and multi-tweet threads, strict 280-char and media spec checks, X API v2 publishing and engagement, and bookmark-driven retrospectives.
---

# X (Twitter) Operations Playbook

X rewards sharp signal density, timely participation in live conversations, replies from credible accounts, and bookmarks on reference-grade posts.

## 1. Topic Discovery (Platform-Native)
- **Live conversation signals**: search recent high-bookmark posts in your niche (`GET /2/tweets/search/recent`), shipping updates ("build in public"), sharp industry debates, and concrete benchmarks.
- **Winning angles**: single-screen architecture diagrams, crisp before/after demos, numbered teardowns, and direct evidence-backed contrarian takes.

## 2. Native Content & Thread Structure
- **Single post (`<= 280` chars baseline)**: open with a concrete claim or observation—no fluff intro. Pair with 1–4 crisp images (`jpg`/`png`/`webp`/`gif`, `<= 5 MB`) or a short native video (`<= 140s`, `mp4`/`mov`).
- **Thread pattern**: Tweet 1 must stand alone as a complete, bookmarkable summary + visual proof; Replies 2–N each deliver one self-contained point via `reply.in_reply_to_tweet_id`.
- **Links**: external links often suppress reach in the opening tweet—when appropriate, keep proof native in Tweet 1 and place the canonical link in the first self-reply.
- **Hashtags**: 0–2 max; hashtag stuffing reads as spam on X.

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate copy (single post or `\n---\n`-separated thread, with 23-char t.co URL weighting and CJK/emoji double weighting) and media with `check_media_specs.py` against `references/specs.json`.
2. **Default zero-config path (Official Web Composer)**: open `https://x.com/compose/post` in the user's browser session (pause for login/2FA/CAPTCHA if prompted), attach local media directly from `drafts/<id>/assets/`, compose the post or thread (`+` to add replies), save draft (`draft_saved`) or stop before clicking **Post** until Gate 2 confirmation, then read back the live post URL.
3. **Optional official API v2 path** (requires `X_ACCESS_TOKEN`, optional `X_CLIENT_ID` + `X_REFRESH_TOKEN` to rotate 2h tokens via `scripts/client.py refresh-token`):
   - Upload local media via `scripts/client.py [--dry-run] upload-media --file <path> [--media-category tweet_image|tweet_gif|tweet_video]`.
   - Publish/read via `scripts/client.py [--dry-run] <cmd>`: `me`, `post --text "..." [--reply-to <id>] [--quote-id <id>] [--media-ids ...]`, `get-tweet --tweet-id <id>`, `list-replies --conversation-id <id>` (Basic+ tier), `engage --action like|repost|bookmark --tweet-id <id>`.
4. Record the verified `https://x.com/i/status/<id>` in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- **Conversation velocity**: reply early to thoughtful comments and quote-post high-signal community responses with added insight.
- **Supported API actions**: reply, delete tweet, like/unlike, repost/undo, bookmark/remove, quote, follow/unfollow.
- **Rate cap**: respect X API v2 per-window limits and keep total engagement under 80 actions/day with 30–60s spacing. Stop immediately on `429 Too Many Requests`.

## 5. North-Star Metrics (`platformMetrics`)
Track `bookmarkRate` (`bookmarks / impressions`), `replyRate`, `repostRate`, and `profileClickRate`.
