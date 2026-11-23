# Facebook Graph API (Pages) Protocol

## Environment Variables
- `FACEBOOK_PAGE_ACCESS_TOKEN` (Page Access Token with `pages_manage_posts`, `pages_read_engagement`, `pages_manage_engagement`, `read_insights`)
- `FACEBOOK_PAGE_ID`

## Core Endpoints (`https://graph.facebook.com/v21.0`)
1. **Publish text / link**: `POST /<pageId>/feed` (`message`, optional `link`)
2. **Publish photo**: `POST /<pageId>/photos` (`url`, `caption`, optional `published=false` for multi-photo attachments)
3. **Publish video / Reels**: `POST /<pageId>/videos` (`file_url`, `description`) or `/<pageId>/video_reels`
4. **List published posts**: `GET /<pageId>/published_posts?fields=id,message,permalink_url,created_time`
5. **Comments & likes**:
   - List: `GET /<postId>/comments?fields=id,from,message,created_time`
   - Create/Reply: `POST /<objectId>/comments` (`message`)
   - Delete: `DELETE /<commentId>`
   - Like: `POST /<objectId>/likes`
6. **Insights (Meta Graph API v21.0+)**:
   - Post: `GET /<postId>/insights?metric=post_media_view,post_reactions_by_type_total`
   - Page: `GET /<pageId>/insights?metric=page_media_view,page_post_engagements,page_follows&period=day`

## Default Official Browser Studio Path (Zero API Setup)
When no Facebook Page Access Token is configured:
1. Open `https://business.facebook.com/latest/composer` in the user's browser session (pause for login/2FA if prompted).
2. Select the target Facebook Page, upload local media from `drafts/<id>/assets/`, enter message copy, and save draft (`draft_saved`) or pause before **Publish** until Gate 2 approval is explicit.
3. Record the verified `https://www.facebook.com/...` post URL in `publish-log.jsonl`.
