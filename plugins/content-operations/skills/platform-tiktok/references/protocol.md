# TikTok Content Posting API v2 Protocol

## Environment Variables
- `TIKTOK_ACCESS_TOKEN` (OAuth 2.0 Bearer token with scopes: `user.info.basic`, `user.info.stats`, `video.list`, `video.publish`, `video.upload`)

## OAuth Endpoints
- **Authorize**: `https://www.tiktok.com/v2/auth/authorize`
- **Token / refresh**: `POST https://open.tiktokapis.com/v2/oauth/token/`

## Publishing, Polling & Analytics (`https://open.tiktokapis.com/v2`)
1. **Query creator constraints (required before every publish)**:
   - `POST /post/publish/creator_info/query/` → returns `privacy_level_options`, `max_video_post_duration_sec`, `duet_disabled`, `stitch_disabled`, `comment_disabled`.
2. **Initialize Video Direct Post**:
   - `POST /post/publish/video/init/` with `post_info` (`title`, `privacy_level`, `disable_duet`, `disable_stitch`, `disable_comment`, `is_aigc`) and `source_info` (`source: "FILE_UPLOAD"` with `video_size`/`chunk_size`/`total_chunk_count`, or `source: "PULL_FROM_URL"` with `video_url`).
   - For `FILE_UPLOAD`, `PUT` chunks to returned `upload_url` with `Content-Range` headers.
3. **Initialize Video Inbox Draft**: `POST /post/publish/inbox/video/init/` (sends video to creator's TikTok app inbox for final audio/review).
4. **Initialize Photo Carousel**: `POST /post/publish/content/init/` (`media_type: "PHOTO"`, `post_mode: "DIRECT_POST"`, `source_info: { source: "PULL_FROM_URL", photo_cover_index, photo_images }`).
5. **Poll publish status**: `POST /post/publish/status/fetch/` (`{ publish_id }`) until `status == "PUBLISH_COMPLETE"` (or `FAILED` / `SEND_TO_USER_INBOX`).
6. **List / query works & stats**:
   - `POST /video/list/?fields=id,title,create_time,share_url,view_count,like_count,comment_count,share_count`
   - `POST /video/query/?fields=id,title,share_url,view_count,like_count,comment_count,share_count`
   - `GET /user/info/?fields=open_id,username,display_name,follower_count,likes_count,video_count`

## Default Official Browser Studio Path (Zero API Setup)
When no TikTok Developer API credentials are configured:
1. Open `https://www.tiktok.com/tiktokstudio/upload` in the user's browser session (pause for sign-in or CAPTCHA if prompted).
2. Upload the local video or photo set from `drafts/<id>/assets/`, set caption, cover frame, visibility, and AI-generated content label truthfully.
3. Save draft (`draft_saved`) or pause before clicking **Post** until Gate 2 confirmation, then record the verified `https://www.tiktok.com/@<username>/video/<id>` in `publish-log.jsonl`.
