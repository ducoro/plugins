# 14-Platform Legitimate Channel Access Matrix

This plugin strictly operates through **two legitimate channels only**:

1. **Official Browser Creator Studio (Default, Zero Configuration)** — works across **all 14 platforms** with zero developer-app setup, zero OAuth management, and direct local file upload from `drafts/<draft-id>/assets/`. Always pause for human sign-in/CAPTCHA and pause before final publish at Gate 2.
2. **Official Platform OpenAPI (Optional, User-Owned Credentials)** — works on **12 platforms** when the user has already configured official developer tokens in environment variables. Never extract cookies, call reverse-engineered endpoints, or rely on hosted third-party OAuth proxies.

| Platform | Default Official Browser Studio | Official OpenAPI (`scripts/client.py`) | Typical Token TTL & Refresh | Media Upload Path (API Mode) |
| --- | --- | --- | --- | --- |
| **Xiaohongshu** (`xiaohongshu`) | `https://creator.xiaohongshu.com/publish/publish` | Browser only (no general public publish API) | Browser login session | Direct local upload in browser |
| **WeChat Channels** (`wechat-channels`) | `https://channels.weixin.qq.com/platform/post/create` | Browser only (no general public publish API) | Browser login session | Direct local upload in browser |
| **Douyin** (`douyin`) | `https://creator.douyin.com/creator-micro/content/upload` | Readback & fans (`query-videos`, `get-fans`); publishing via browser | OAuth access token (~15d; refresh via OpenAPI) | Browser Creator Studio for publishing |
| **Bilibili** (`bilibili`) | `https://member.bilibili.com/platform/upload/video/frame` | Categories, archive submit/view, stats (v2 HMAC-SHA256) | OAuth access token (~30d) | Video chunked upload per `protocol.md` (or direct browser upload) |
| **WeChat Official** (`wechat-official`) | `https://mp.weixin.qq.com/` (Draft Box) | `get-token`, `upload-image`, `upload-thumb`, `add-draft`, `submit-publish`, `poll-publish`, stats | **2 hours** (`client.py get-token` via AppID/Secret) | Direct multipart via `upload-image` & `upload-thumb` |
| **Kuaishou** (`kuaishou`) | `https://cp.kuaishou.com/article/publish/video` | `user-info`, `start-upload`, `photo-info`, `photo-list` | OAuth access token (~48h) | Fragment + multipart publish per `protocol.md` (or direct browser upload) |
| **X / Twitter** (`x-twitter`) | `https://x.com/compose/post` | `me`, `refresh-token`, `upload-media`, `post`, `post-thread`, `get-tweet`, `user-tweets`, `list-replies`, `engage` | **2 hours** (`client.py refresh-token` via `X_REFRESH_TOKEN`) | Direct v2 chunked upload via `upload-media` |
| **YouTube** (`youtube`) | `https://studio.youtube.com/` | `refresh-token`, `list-categories`, `init-upload`, `upload-video`, `set-thumbnail`, `video-stats`, comments | **1 hour** (`client.py refresh-token` via `YOUTUBE_REFRESH_TOKEN`) | Direct resumable PUT via `upload-video` & `set-thumbnail` |
| **TikTok** (`tiktok`) | `https://www.tiktok.com/tiktokstudio/upload` | `refresh-token`, `creator-info`, `account-stats`, `init-video-file`, `upload-video-file`, `init-video-url`, `publish-status`, `list-videos` | **24 hours** (`client.py refresh-token` via `TIKTOK_REFRESH_TOKEN`) | Direct local `FILE_UPLOAD` via `init-video-file` + `upload-video-file` (or verified-domain URL) |
| **Instagram** (`instagram`) | `https://www.instagram.com/` or `https://business.facebook.com/latest/composer` | `quota`, `create-container`, `create-carousel`, `container-status`, `publish`, `get-media`, insights, comments | Long-lived token (~60 days) | Public HTTPS URL right before publish via `ducoro-cli media upload <file> --json` (5h TTL) |
| **Facebook Page** (`facebook`) | `https://business.facebook.com/latest/composer` | `post-feed`, `post-photo`, `list-posts`, comments, `post-insights`, `page-insights` | Page token (60d / non-expiring system token) | Public HTTPS URL right before publish via `ducoro-cli media upload <file> --json` (5h TTL) |
| **Threads** (`threads`) | `https://www.threads.net/` | `create-container`, `create-carousel`, `container-status`, `publish`, `post-thread`, `get-post`, `insights`, replies | Long-lived token (~60 days) | Public HTTPS URL right before publish via `ducoro-cli media upload <file> --json` (5h TTL) |
| **LinkedIn** (`linkedin`) | `https://www.linkedin.com/feed/` | `userinfo`, `upload-image`, `post`, `post-with-first-reply`, `list-comments`, `comment` | OAuth access token (~60 days) | Direct image upload via `upload-image` → `post --image-urn` |
| **Pinterest** (`pinterest`) | `https://www.pinterest.com/pin-creation-tool/` | `list-boards`, `create-pin`, `get-pin`, `update-pin`, `pin-analytics` | OAuth access token (~30 days) | Public HTTPS URL right before publish via `ducoro-cli media upload <file> --json` (5h TTL) |

## Channel Selection Rule

- If the account in `accounts.json` has `status: "manual_browser"` OR its API environment variables are not configured: **default immediately to the Official Browser Studio path** (zero setup friction, direct local file upload).
- If valid official API credentials are present and the user wants automated API execution: use `scripts/client.py` (always preview with `--dry-run` first during setup).
- Never attempt to bridge missing API tokens by scraping cookies from the browser.
