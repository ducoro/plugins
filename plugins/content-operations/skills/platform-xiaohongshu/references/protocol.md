# Xiaohongshu Browser Publishing & Readback Protocol

Xiaohongshu does not expose a general-purpose public posting API for regular creator accounts. Execute through a **tool-agnostic browser workflow** (compatible with any host browser agent, Computer Use, or manual handoff).

## Pre-Flight Checks
1. Verify `accounts.json` lists the intended account with `status: "manual_browser"`.
2. Confirm `check_media_specs.py` passes with zero errors for `variants/xiaohongshu.md`.
3. Confirm the local browser session is logged into `https://creator.xiaohongshu.com/publish/publish`. If a login QR or CAPTCHA appears, **stop immediately and hand back to the human**—never attempt to bypass login or anti-bot checks.

## Step-by-Step Draft Staging Flow
1. Open `https://creator.xiaohongshu.com/publish/publish`.
2. Select tab **上传图文** (`image_text`) or **上传视频** (`video`).
3. Upload ordered files from `drafts/<draft-id>/assets/` (verify Card 1 is the intended `3:4` cover).
4. Fill **标题** (`<= 20` chars) and **正文** (`<= 1000` chars).
5. Insert up to 5 `#topic` tags via the native tag autocomplete so topics bind as real clickable tags rather than plain text.
6. Set options per `variants/xiaohongshu.md` `options` object:
   - `visibility`: `"public"` (default) | `"private"` | `"friends"`
   - `scheduledAt`: optional ISO-8601 datetime (`YYYY-MM-DDTHH:MM:SS+08:00`) for Creator Studio scheduled publish
   - `poi`: optional location display name string
   - `originalDeclared`: boolean (`true` to enable original-content declaration)
7. **Default Gate 2 stop**: click **暂存离开 (Save Draft)** or pause on the filled editor, capture a screenshot/readback for human confirmation, and append a `status: "draft_saved"` record (`publicUrl: null`, `workId: null`, `variantHash` from `meta.json`) to `content-ops/publish-log.jsonl`.
8. Only after explicit Gate 2 confirmation: click **发布 (Publish)**, wait for confirmation toast, navigate to **笔记管理 (Note Management)**, and read back the live note ID and URL (`https://www.xiaohongshu.com/explore/<noteId>`).
9. Append the verified `status: "published"` record to `content-ops/publish-log.jsonl`.

## Comment & Metrics Collection Flow
- Open Creator Studio **评论管理** and **笔记数据** views to read recent comments and per-note metrics (`views`, `likes`, `comments`, `shares`, `saves`, `coverCtr`).
- Log comments in `engagement/inbox.json` and snapshots in `analytics/snapshots.jsonl`.
- Keep all browser interactions human-paced (90–180s jittered spacing; max 6–8 actions/hour).
