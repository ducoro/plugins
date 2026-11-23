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

## Engagement & Analytics Endpoints
- **Self profile**: `GET /2/users/me?user.fields=public_metrics,username`
- **Read tweet & metrics**: `GET /2/tweets/<id>?tweet.fields=public_metrics,created_at,conversation_id`
- **List replies (conversation)**: `GET /2/tweets/search/recent?query=conversation_id:<id>&tweet.fields=author_id,created_at,public_metrics`
- **Like / Unlike**: `POST /2/users/<uid>/likes` (`{ tweet_id }`) / `DELETE /2/users/<uid>/likes/<tweet_id>`
- **Repost / Undo**: `POST /2/users/<uid>/retweets` / `DELETE /2/users/<uid>/retweets/<tweet_id>`
- **Bookmark / Remove**: `POST /2/users/<uid>/bookmarks` / `DELETE /2/users/<uid>/bookmarks/<tweet_id>`
- **Follow / Unfollow**: `POST /2/users/<uid>/following` (`{ target_user_id }`) / `DELETE /2/users/<uid>/following/<target_id>`
- **Delete tweet**: `DELETE /2/tweets/<id>`

## Default Official Browser Composer Path (Zero API Setup)
When no X Developer API credentials are configured:
1. Open `https://x.com/compose/post` in the user's browser session (pause if sign-in/2FA/CAPTCHA appears—never harvest cookies).
2. Enter post text (or click `+` to build a multi-post thread), attach local images/GIF/video directly from `drafts/<id>/assets/`, and add alt text.
3. Save draft (`draft_saved`) or pause before clicking **Post** until Gate 2 approval is explicit; afterward copy the verified `https://x.com/i/status/<id>` into `publish-log.jsonl`.
