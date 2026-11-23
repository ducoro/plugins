# Instagram Graph API Protocol

## Environment Variables
- `INSTAGRAM_ACCESS_TOKEN` (long-lived Instagram / Meta Graph API token)
- `INSTAGRAM_USER_ID` (IG Professional User ID)

## OAuth Endpoints
- **Authorize**: `https://www.instagram.com/oauth/authorize`
- **Exchange / long-lived / refresh**: `https://api.instagram.com/oauth/access_token`, `https://graph.instagram.com/access_token`, `https://graph.instagram.com/refresh_access_token`

## Container Publishing, Engagement & Insights (`https://graph.instagram.com/v21.0`)
1. **Check daily quota**: `GET /<igUserId>/content_publishing_limit?fields=config,quota_usage`
2. **Create media container**: `POST /<igUserId>/media`
   - Single image: `image_url`, `caption`, optional `alt_text`, `location_id`.
   - Reels: `media_type=REELS`, `video_url`, `caption`, optional `cover_url`.
   - Carousel: create children with `is_carousel_item=true`, then parent `media_type=CAROUSEL`, `children=<id1,id2,...>`, `caption`.
3. **Poll container status**: `GET /<containerId>?fields=status_code,status` until `status_code == "FINISHED"`.
4. **Publish container**: `POST /<igUserId>/media_publish` (`creation_id=<containerId>`) → returns live `id`.
5. **Read permalink**: `GET /<mediaId>?fields=id,permalink,timestamp,media_type,like_count,comments_count`
6. **Comments**:
   - List: `GET /<mediaId>/comments?fields=id,text,username,timestamp`
   - Reply: `POST /<commentId>/replies` (`message`)
   - Delete: `DELETE /<commentId>`
7. **Insights**:
   - Media: `GET /<mediaId>/insights?metric=views,reach,saved,shares,likes,comments`
   - Account: `GET /<igUserId>/insights?metric=reach&period=day&metric_type=total_value` (in v21+, `profile_views` time-series was deprecated; override `--metrics` as needed)

## Default Official Browser Studio Path (Zero API Setup)
When no Meta Graph API token is configured:
1. Open `https://business.facebook.com/latest/composer` (supports drafts & scheduling) or `https://www.instagram.com/` in the user's browser session (pause for login/2FA if prompted).
2. Upload local JPEG/MP4 files directly from `drafts/<id>/assets/`, fill caption and alt text, and save draft (`draft_saved`) or pause before **Share / Publish** until Gate 2 confirmation.
3. Copy the verified `https://www.instagram.com/p/<shortcode>/` or `/reel/<shortcode>/` permalink into `publish-log.jsonl`.
