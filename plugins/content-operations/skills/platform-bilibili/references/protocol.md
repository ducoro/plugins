# Bilibili OpenAPI Protocol

## Environment Variables
- `BILIBILI_CLIENT_ID`
- `BILIBILI_CLIENT_SECRET`
- `BILIBILI_ACCESS_TOKEN`

## OAuth2 Endpoints
- **Authorize**: `https://account.bilibili.com/pc/account-pc/auth/oauth`
- **Exchange token**: `POST https://api.bilibili.com/x/account-oauth2/v1/token`
- **Refresh token**: `POST https://api.bilibili.com/x/account-oauth2/v1/refresh_token`

## Archive, Upload & Analytics Endpoints (`https://member.bilibili.com`)
All OpenAPI calls pass `client_id` and `access_token` query parameters (or signed headers per current Bilibili Open Platform app spec).

1. **List categories (`tid`)**: `GET https://member.bilibili.com/arcopen/fn/archive/type/list`
2. **Initialize upload**: `POST https://member.bilibili.com/arcopen/fn/archive/video/init` (body: `name`, `utype` (`0` multi-part / `1` single)) → returns `upload_token`.
3. **Upload video chunks**: `POST https://openupos.bilivideo.com/video/v2/part/upload?upload_token=<token>&part_number=<1-based>` (raw binary chunk).
4. **Complete upload**: `POST https://member.bilibili.com/arcopen/fn/archive/video/complete?upload_token=<token>`.
5. **Upload cover (optional)**: `POST https://member.bilibili.com/arcopen/fn/archive/cover/upload` (`multipart/form-data` image).
6. **Submit archive**: `POST https://member.bilibili.com/arcopen/fn/archive/add-by-utoken?upload_token=<token>` (JSON: `title`, `desc`, `tag`, `tid`, `copyright`, `source`, `no_reprint`, `cover`) → returns `resource_id` (`BV...`).
7. **Poll / read back status**: `GET https://member.bilibili.com/arcopen/fn/archive/view?resource_id=<bvid>` and `GET /arcopen/fn/archive/viewlist`.
8. **Analytics**:
   - Work stats: `GET https://member.bilibili.com/arcopen/fn/data/arc/stat?resource_id=<bvid>`
   - Account stats: `GET https://member.bilibili.com/arcopen/fn/data/user/stat`
   - Account info: `GET https://member.bilibili.com/arcopen/fn/user/account/info`

## Default Official Browser Studio Path (Zero API Setup)
When no Bilibili Open Platform app credentials are configured:
1. Open `https://member.bilibili.com/platform/upload/video/frame` in the user's browser session. Pause for human sign-in or CAPTCHA if prompted—never harvest cookies.
2. Upload the local video and `16:9` cover from `drafts/<id>/assets/`, set title, partition (`tid`), copyright (`原创`/`转载`), tags, and description.
3. Save draft (`draft_saved`) or stop before clicking **立即投稿** until Gate 2 approval is explicit.
4. Read back the live `https://www.bilibili.com/video/<bvid>` from **稿件管理** into `publish-log.jsonl`.
