# YouTube Data API v3 Protocol

## Environment Variables
- `YOUTUBE_ACCESS_TOKEN` (OAuth 2.0 Bearer token with scopes: `youtube.upload`, `youtube.force-ssl`, `youtube.readonly`, `yt-analytics.readonly`)

## OAuth Endpoints
- **Token / refresh**: `POST https://oauth2.googleapis.com/token`
- **Revoke**: `POST https://oauth2.googleapis.com/revoke`
- **Userinfo**: `GET https://www.googleapis.com/oauth2/v3/userinfo`

## Publishing, Readback & Engagement (`https://www.googleapis.com/youtube/v3`)
1. **List categories**: `GET /videoCategories?part=snippet&regionCode=US`
2. **Resumable video upload**:
   - Step 1 (init session): `POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status` with JSON metadata (`snippet: { title, description, tags, categoryId }`, `status: { privacyStatus, publishAt?, selfDeclaredMadeForKids }`) and headers `X-Upload-Content-Length` + `X-Upload-Content-Type`. Read `Location` response header.
   - Step 2 (upload bytes): `PUT <Location>` with raw binary chunks until HTTP `200`/`201` returns the created video object (`id`).
3. **Set thumbnail**: `POST https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=<id>&uploadType=media`
4. **Update metadata**: `PUT /videos?part=snippet,status`
5. **Read work & statistics**: `GET /videos?part=snippet,statistics,status&id=<videoId>`
6. **Channel statistics**: `GET /channels?part=snippet,statistics&mine=true`
7. **YouTube Analytics v2 (`https://youtubeanalytics.googleapis.com/v2/reports`, requires `yt-analytics.readonly`)**:
   - Channel daily analytics: `python3 scripts/client.py channel-analytics --days 14 [--workspace <content-ops>] [--account-id <id>]` — pulls `views`, `estimatedMinutesWatched`, `averageViewDuration` (`avgViewDurationSec`), `averageViewPercentage` (`avgViewPct`), `subscribersGained`, `subscribersLost`, and `likes`.
   - Single-video analytics: `python3 scripts/client.py video-analytics --video-id <id> --days 30 [--with-stats] [--workspace <content-ops> --window 7d]` — queries `filters=video==<id>` and optionally appends a normalized snapshot to `analytics/snapshots.jsonl`.
8. **List comments**: `GET /commentThreads?part=snippet,replies&videoId=<videoId>&maxResults=50`
9. **Reply to comment**: `POST /comments?part=snippet` (`{ snippet: { parentId, textOriginal } }`)
10. **Delete comment**: `DELETE /comments?id=<commentId>`

## Default Official Browser Studio Path (Zero API Setup)
When no Google Cloud OAuth credentials are configured:
1. Open `https://studio.youtube.com/` in the user's browser session (pause for Google sign-in/2FA if prompted).
2. Click **Create → Upload videos**, upload local video and `16:9` thumbnail from `drafts/<id>/assets/`, fill title, chapters/description, tags, and `Made for kids = No`.
3. Save as **Private** draft (`draft_saved`) at Gate 2; change to **Public** or **Schedule** only after explicit confirmation, then record `https://www.youtube.com/watch?v=<videoId>` in `publish-log.jsonl`.
