# Threads API Protocol

## Environment Variables
- `THREADS_ACCESS_TOKEN` (OAuth 2.0 Bearer token with `threads_basic`, `threads_content_publish`, `threads_manage_replies`, `threads_manage_insights`)
- `THREADS_USER_ID`

## OAuth Endpoints
- **Authorize**: `https://threads.net/oauth/authorize`
- **Exchange / long-lived / refresh**: `https://graph.threads.net/oauth/access_token`, `https://graph.threads.net/access_token`, `https://graph.threads.net/refresh_access_token`

## Core Endpoints (`https://graph.threads.net/v1.0`)
1. **Create container**: `POST /<userId>/threads` (`media_type=TEXT|IMAGE|VIDEO|CAROUSEL`, `text`, optional `image_url`/`video_url`/`topic_tag`/`reply_control`/`reply_to_id`).
2. **Poll container**: `GET /<containerId>?fields=status,error_message` until `FINISHED`.
3. **Publish**: `POST /<userId>/threads_publish` (`creation_id=<containerId>`).
4. **Read post & permalink**: `GET /<postId>?fields=id,text,permalink,timestamp,media_type`
5. **Replies & moderation**:
   - List: `GET /<postId>/replies?fields=id,text,username,timestamp,hide_status`
   - Hide / Unhide: `POST /<replyId>/manage_reply` (`hide=true|false`)
6. **Insights**:
   - Post: `GET /<postId>/insights?metric=views,likes,replies,reposts,quotes`
   - Account: `GET /<userId>/threads_insights?metric=views,likes,replies,reposts,quotes,followers_count`

## Default Official Browser App Path (Zero API Setup)
When no Threads API token is configured:
1. Open `https://www.threads.net/` in the user's browser session (pause for login/2FA if prompted).
2. Click **Create**, fill text (`<= 500` chars), attach local images/video directly from `drafts/<id>/assets/`, and set the single topic tag.
3. Save draft (`draft_saved`) or pause before **Post** until Gate 2 confirmation, then record the verified `https://www.threads.net/@<user>/post/<id>` permalink in `publish-log.jsonl`.
