# Kuaishou OpenAPI Protocol

## Environment Variables
- `KUAISHOU_APP_ID`
- `KUAISHOU_ACCESS_TOKEN`

## OAuth Endpoints (`https://open.kuaishou.com`)
- **Authorize**: `https://open.kuaishou.com/oauth2/authorize`
- **Access / Refresh token**: `POST /oauth2/access_token`, `POST /oauth2/refresh_token`

## Upload, Publish & Readback Endpoints (`https://open.kuaishou.com`)
1. **Start upload**: `POST /openapi/photo/start_upload?app_id=<app_id>&access_token=<token>` → returns `upload_token` and `endpoint`.
2. **Upload fragments**: `POST http://<endpoint>/api/upload/fragment?upload_token=<token>&fragment_id=<0-based>` (raw binary bytes).
3. **Complete upload**: `POST http://<endpoint>/api/upload/complete?upload_token=<token>&fragment_count=<N>`.
4. **Publish video**: `POST /openapi/photo/publish?app_id=<app_id>&access_token=<token>&upload_token=<token>` (multipart/form with `caption`, `cover` bytes, optional `stereo_type`, `merchant_product_id`) → returns `photo_info.photo_id`.
5. **Readback & list works**:
   - `GET /openapi/photo/info?app_id=<app_id>&access_token=<token>&photo_id=<id>`
   - `GET /openapi/photo/list?app_id=<app_id>&access_token=<token>&count=20`
   - `GET /openapi/user_info?app_id=<app_id>&access_token=<token>`

## Default Official Browser Studio Path (Zero API Setup)
When no Kuaishou Open Platform app credentials are configured:
1. Open `https://cp.kuaishou.com/article/publish/video` in the user's browser session (pause for login/verification if prompted).
2. Upload the local video and cover image from `drafts/<id>/assets/`, fill caption and up to 4 `#topic` tags.
3. Save draft (`draft_saved`) or stop before clicking **发布** until Gate 2 approval is explicit, then record the verified `https://www.kuaishou.com/short-video/<photoId>` in `publish-log.jsonl`.
