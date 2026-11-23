# Douyin OpenAPI & Browser Publishing Protocol

## Environment Variables (API Mode)
- `DOUYIN_CLIENT_KEY`
- `DOUYIN_CLIENT_SECRET`
- `DOUYIN_ACCESS_TOKEN`
- `DOUYIN_OPEN_ID`

## Official OpenAPI Endpoints (`https://open.douyin.com`)
- **OAuth authorize**: `https://open.douyin.com/platform/oauth/connect/`
- **Access token / client token**:
  - `POST https://open.douyin.com/oauth/access_token/`
  - `POST https://open.douyin.com/oauth/client_token/`
- **Query video / live readback**: `POST https://open.douyin.com/api/douyin/v1/video/video_data/?open_id=<open_id>` (Web OpenAPI, body `{ item_ids }`) or `POST https://open.douyin.com/api/apps/v1/video/query/?open_id=<open_id>` (Mini-App)
- **Query fan count**: `GET https://open.douyin.com/api/douyin/v1/user/fans_data/?open_id=<open_id>&date_type=7` (Web OpenAPI) or `GET https://open.douyin.com/api/apps/v1/user/get_fans/?open_id=<open_id>&date_type=7` (Mini-App)
- **QR handoff / mini-app publish**: `POST https://open.douyin.com/api/apps/v1/qrcode/create/` (generates QR scanned by the creator's Douyin app to confirm publish handoff)

Use `scripts/client.py` with `--dry-run` first to verify payloads before issuing live calls.

## Browser Creator Studio Fallback (Tool-Agnostic)
When an account does not hold Douyin Open Platform video publish scopes:
1. Open `https://creator.douyin.com/creator-micro/content/upload`.
2. If login/QR or verification appears, pause and ask the human to sign in.
3. Upload video (`9:16`) or image carousel (`<= 12` images), fill title (`<= 30` chars), body, up to 5 `#topic` tags, cover frame (`cover_tsp`), and `private_status` / `download_type`.
4. Save draft or stop before clicking **发布** until Gate 2 approval is explicit.
5. After publishing, read back the live URL (`https://www.douyin.com/video/<id>` or `/note/<id>`) from **作品管理** and append to `publish-log.jsonl`.
