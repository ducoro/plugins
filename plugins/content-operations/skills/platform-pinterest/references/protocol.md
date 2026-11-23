# Pinterest API v5 Protocol

## Environment Variables
- `PINTEREST_ACCESS_TOKEN` (OAuth 2.0 Bearer token with `boards:read`, `pins:read`, `pins:write`, `user_accounts:read`)

## OAuth Endpoints
- **Authorize**: `https://www.pinterest.com/oauth/`
- **Token / revoke**: `POST https://api.pinterest.com/v5/oauth/token`, `POST /v5/oauth/revoke`

## Core Endpoints (`https://api.pinterest.com/v5`)
1. **Account info**: `GET /v5/user_account`
2. **List boards (`board_id`)**: `GET /v5/boards`
3. **Create Pin**: `POST /v5/pins`
   - JSON body: `board_id`, `title`, `description`, optional `link`, `alt_text`, `media_source: { source_type: "image_url", url }` (or `video_id` after `POST /v5/media` upload + poll `GET /v5/media/<mediaId>`).
4. **Read / Update Pin**: `GET /v5/pins/<pinId>`, `PATCH /v5/pins/<pinId>`
5. **Pin Analytics**: `GET /v5/pins/<pinId>/analytics?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&metric_types=IMPRESSION,SAVE,PIN_CLICK,OUTBOUND_CLICK`

## Default Official Browser Creation Tool Path (Zero API Setup)
When no Pinterest API v5 token is configured:
1. Open `https://www.pinterest.com/pin-creation-tool/` in the user's browser session (pause for login/2FA if prompted).
2. Upload the local `2:3` image or video directly from `drafts/<id>/assets/`, fill title, description, destination link, alt text, and select target board.
3. Save draft (`draft_saved`) or pause before **Publish** until Gate 2 confirmation, then record `https://www.pinterest.com/pin/<pinId>` in `publish-log.jsonl`.
