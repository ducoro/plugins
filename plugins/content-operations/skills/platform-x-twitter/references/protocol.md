# X (Twitter) API v2 Protocol

## Environment Variables
- `X_ACCESS_TOKEN` (OAuth 2.0 User Context Bearer token, ~2h TTL; scopes: `tweet.read tweet.write users.read media.write like.write bookmark.write offline.access`)
- `X_CLIENT_ID`, `X_REFRESH_TOKEN` (optional `X_CLIENT_SECRET` for confidential clients) — used by `scripts/client.py refresh-token` to rotate expired 2h access tokens
- `X_USER_ID` (optional cached numeric user ID; can be fetched via `GET /2/users/me`)

## Auth & Token Endpoints
- **Token / refresh**: `POST https://api.x.com/2/oauth2/token`
- **Revoke**: `POST https://api.x.com/2/oauth2/revoke`

## Publishing & Media Upload (`https://api.x.com`)
1. **Media upload (v2 chunked)**:
   - `POST /2/media/upload/initialize` (`total_bytes`, `media_type`, `media_category`: `tweet_image` | `tweet_video` | `tweet_gif`) → returns `data.id`.
   - `POST /2/media/upload/<media_id>/append` (`segment_index`, multipart chunk).
   - `POST /2/media/upload/<media_id>/finalize`; for video, poll status until `processing_info.state == "succeeded"`.
   - Optional alt text: `POST /2/media/metadata` (`id`, `metadata.alt_text.text`).
2. **Create post / reply / quote**: `POST /2/tweets`
   - JSON body: `text`, optional `media: { media_ids }`, `reply: { in_reply_to_tweet_id }`, `quote_tweet_id`, `reply_settings`, `poll`.
   - Returns `data.id` → live URL `https://x.com/i/status/<id>`.
3. **Publish thread + optional `firstReply` (`scripts/client.py post-thread`)**:
   - `python3 scripts/client.py post-thread --variant <workspace>/drafts/<id>/variants/x-twitter.md [--media-ids <id...>] [--dry-run]`
   - Chains root post → subsequent thread items (`\n---\n` or `meta.threads[]`) → `options.firstReply` via `reply.in_reply_to_tweet_id`.
   - On partial failure, exits non-zero and returns `publishedTweets` plus `resumeReplyTo` so the remaining tail can resume via `--resume-reply-to <id>` without duplicating already-posted tweets.

## Engagement, Benchmark Radar & Analytics Endpoints
- **Self profile**: `GET /2/users/me?user.fields=public_metrics,username`
- **Read tweet & metrics**: `GET /2/tweets/<id>?tweet.fields=public_metrics,created_at,conversation_id`
- **Benchmark account recent tweets (`scripts/client.py user-tweets`)**:
  - Resolves handle via `GET /2/users/by/username/<username>` when `--username` is given, then calls `GET /2/users/<uid>/tweets?since_id=<cursor>&exclude=retweets&tweet.fields=created_at,public_metrics,conversation_id,lang`.
  - Requires a paid X API v2 tier with read access; otherwise use the official browser session or a connected X MCP connector.
- **List replies (conversation)**: `GET /2/tweets/search/recent?query=conversation_id:<id>&tweet.fields=author_id,created_at,public_metrics`
- **Like / Unlike**: `POST /2/users/<uid>/likes` (`{ tweet_id }`) / `DELETE /2/users/<uid>/likes/<tweet_id>`
- **Repost / Undo**: `POST /2/users/<uid>/retweets` / `DELETE /2/users/<uid>/retweets/<tweet_id>`
- **Bookmark / Remove**: `POST /2/users/<uid>/bookmarks` / `DELETE /2/users/<uid>/bookmarks/<tweet_id>`
- **Follow / Unfollow**: `POST /2/users/<uid>/following` (`{ target_user_id }`) / `DELETE /2/users/<uid>/following/<target_id>`
- **Delete tweet**: `DELETE /2/tweets/<id>`

## Default Official Browser Composer Path (Zero API Setup)
When no X Developer API credentials are configured (or when using Premium long posts / X Articles / readback without paid API tiers):
1. Open `https://x.com/compose/post` in the user's browser session (pause if sign-in/2FA/CAPTCHA appears—never harvest cookies).
2. Enter post text (or click `+` to build a multi-post thread), attach local images/GIF/video directly from `drafts/<id>/assets/`, and add alt text.
3. Save draft (`draft_saved`) or pause before clicking **Post** until Gate 2 approval is explicit; afterward, if `options.firstReply` is present, reply to the newly published root post with the approved `firstReply` text and record the verified `https://x.com/i/status/<id>` into `publish-log.jsonl`.

## X Articles (Long-Form Composer & Readback)
X Articles are web-composer only (not supported by X API v2 `POST /2/tweets`; `check_media_specs.py --channel api` rejects `mode: "article"`):
1. **Variant contract**: Set `"mode": "article"`, a non-empty `"title"` (`<= 120` chars), `"cover": {"path": "assets/<banner>.png"}` at **5:2** aspect ratio (recommended `2000×800` or `1600×640`), and optional inline images in `"media"` (`<= 25`). Inline links are allowed directly in article body without triggering `outbound_link_in_root`.
2. **Drafting & upload (`https://x.com/compose/articles`)**:
   - Confirm the active logged-in account has X Articles access (Premium+ / eligible org). If unavailable, deliver the approved local draft and images and report the account-tier blocker explicitly.
   - Upload the 5:2 top banner and inspect crop/readability in the live header preview.
   - Paste/enter title and structured body (headings, bold emphasis, blockquotes, links), insert inline images at their matching paragraphs, and verify section order.
3. **Draft readback & Gate 2 publish**:
   - Save as an unpublished Article draft first and read back the saved draft (distinguishing original copy from browser auto-translation) to verify text, bolding, and inline image placement.
   - After explicit Gate 2 approval, publish and read back the live public Article URL and timestamp into `publish-log.jsonl`.
