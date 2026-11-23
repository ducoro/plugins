# WeChat Official Account API Protocol

## Environment Variables
- `WECHAT_OFFICIAL_ACCESS_TOKEN` (obtained via `GET https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=...&secret=...` or third-party component OAuth)

## Core Endpoints (`https://api.weixin.qq.com`)
1. **Upload inline body image**: `POST /cgi-bin/media/uploadimg?access_token=<token>` (multipart `media`) → returns WeChat-hosted `url` for `<img src>` inside HTML.
2. **Upload cover thumb material**: `POST /cgi-bin/material/add_material?access_token=<token>&type=image` → returns `media_id` (`thumb_media_id`).
3. **Create draft**: `POST /cgi-bin/draft/add?access_token=<token>` (`{ articles: [{ title, author, digest, content, content_source_url, thumb_media_id, need_open_comment, only_fans_can_comment }] }`) → returns `media_id`.
4. **Submit freepublish**: `POST /cgi-bin/freepublish/submit?access_token=<token>` (`{ media_id }`) → returns `publish_id`.
5. **Poll publish status**: `POST /cgi-bin/freepublish/get?access_token=<token>` (`{ publish_id }`) → wait until `publish_status == 0` and capture `article_detail.item[].article_url`.
6. **Analytics**:
   - Per-article daily summary: `POST /datacube/getarticlesummary?access_token=<token>` (`{ begin_date, end_date }`, max 1-day range)
   - Per-article cumulative breakdown: `POST /datacube/getarticletotal?access_token=<token>` (`{ begin_date, end_date }`, max 1-day range; returns day-by-day `int_page_read_count`, `share_count`, `add_to_fav_count`)
   - Aggregate read stats: `POST /datacube/getuserread?access_token=<token>` (`{ begin_date, end_date }`, max 3-day range)
   - Follower cumulate: `POST /datacube/getusercumulate?access_token=<token>` (`{ begin_date, end_date }`, max 7-day range)

## Default Official Browser Studio Path (Zero API Setup)
When no Official Account API credentials or IP allowlist are configured:
1. Open `https://mp.weixin.qq.com/` in the user's browser session (pause for WeChat QR scan when required).
2. Navigate to **草稿箱 → 新的创作**, fill title, author, digest, body copy, and upload inline images + `2.35:1` cover directly from `drafts/<id>/assets/`.
3. Save draft (`draft_saved`), ask the human to preview on mobile (Gate 2), and complete **发表 / 群发** only after explicit confirmation. Log the live `https://mp.weixin.qq.com/s/...` URL in `publish-log.jsonl`.
