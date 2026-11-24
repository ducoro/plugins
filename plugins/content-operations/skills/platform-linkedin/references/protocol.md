# LinkedIn REST API Protocol

## Environment Variables
- `LINKEDIN_ACCESS_TOKEN` (OAuth 2.0 Bearer token with `openid profile w_member_social` or organization scopes)
- `LINKEDIN_AUTHOR_URN` (e.g., `urn:li:person:<id>` or `urn:li:organization:<id>`)

## OAuth Endpoints
- **Authorize**: `https://www.linkedin.com/oauth/v2/authorization`
- **Token**: `POST https://www.linkedin.com/oauth/v2/accessToken`
- **Revoke**: `POST https://www.linkedin.com/oauth/v2/revoke`
- **Userinfo**: `GET https://api.linkedin.com/v2/userinfo`

## Publishing & Comments (`https://api.linkedin.com/rest`)
Required headers on all `/rest/*` calls:
- `Authorization: Bearer <token>`
- `LinkedIn-Version: 202601` (override with `LINKEDIN_API_VERSION` to match an active monthly `YYYYMM` version within the trailing 12 months)
- `X-Restli-Protocol-Version: 2.0.0`

1. **Initialize image upload**: `POST /rest/images?action=initializeUpload` (`{ initializeUploadRequest: { owner } }`) → PUT bytes to `uploadUrl`, receive image URN.
2. **Initialize / finalize video upload**: `POST /rest/videos?action=initializeUpload` → PUT parts → `POST /rest/videos?action=finalizeUpload`.
3. **Create post**: `POST /rest/posts` (`author`, `commentary`, `visibility: "PUBLIC"`, `distribution: { feedDistribution: "MAIN_FEED" }`, `lifecycleState: "PUBLISHED"`, optional `content.media` / `content.multiImage`). Read `x-restli-id` response header for the live post URN.
   - **Post + automatic `firstReply` comment (`scripts/client.py post-with-first-reply`)**:
     - `python3 scripts/client.py post-with-first-reply --variant <workspace>/drafts/<id>/variants/linkedin.md [--image-urn <urn>] [--dry-run]`
     - Publishes the root post, then attaches `options.firstReply` via `POST /rest/socialActions/<encodedPostUrn>/comments`. On partial failure (root posted, comment failed), exits non-zero and returns `postUrn` + `resumePostUrn` so the comment can be retried via `--resume-post-urn <urn>` without duplicating the post.
4. **Read / Delete post**: `GET /rest/posts/<encodedPostUrn>`, `DELETE /rest/posts/<encodedPostUrn>`.
5. **Comments**:
   - List: `GET /rest/socialActions/<encodedPostUrn>/comments`
   - Create: `POST /rest/socialActions/<encodedPostUrn>/comments` (`{ actor, object: <postUrn>, message: { text } }`)
   - Delete: `DELETE /rest/socialActions/<encodedCommentUrn>`
6. **Analytics Boundary**:
   - LinkedIn's standard Member Posts API (`w_member_social`) does **not** expose personal-profile post impressions/analytics. For personal accounts (`urn:li:person:...`), record manual/exported LinkedIn Post Analytics figures into `analytics/snapshots.jsonl` with `source: "manual"`.
   - For Organization Pages (`urn:li:organization:...`) with `r_organization_social`, query `GET /rest/organizationalEntityShareStatistics?q=organizationalEntity&organizationalEntity=<encodedOrgUrn>`.

## Default Official Browser Composer Path (Zero API Setup)
When no LinkedIn Developer OAuth token is configured:
1. Open `https://www.linkedin.com/feed/` in the user's browser session (pause for login/2FA if prompted).
2. Click **Start a post**, attach local images/video/PDF from `drafts/<id>/assets/`, enter copy, and save draft (`draft_saved`) or pause before **Post** until Gate 2 approval is explicit.
3. Copy the verified `https://www.linkedin.com/feed/update/<urn>` link into `publish-log.jsonl`.
