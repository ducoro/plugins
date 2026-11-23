# WeChat Channels Browser Publishing Protocol

WeChat Channels does not offer an open general creator publishing API (WeChat's `/channels/ec/finder/*` endpoints are restricted to authorized Channels EC / partner apps). Use this tool-agnostic browser workflow:

## Step-by-Step Draft Staging Flow
1. Open `https://channels.weixin.qq.com/platform/post/create`.
2. If WeChat QR login appears, stop and ask the human to scan and log in.
3. Upload the validated video from `drafts/<draft-id>/assets/` and select/upload the cover frame.
4. Fill **短标题** (`<= 16` chars), **视频描述** (`<= 1000` chars), `#topic` tags, optional Official Account link, and optional scheduled time.
5. Click **保存草稿 (Save Draft)** and present preview + Gate 2 checklist to the human.
6. After explicit Gate 2 approval: publish, wait for upload/transcoding confirmation, then read back the live work entry from **动态管理** (`channels.weixin.qq.com/platform/post/list`) and append to `publish-log.jsonl`.

## Engagement & Data Readback
- Read comments from **互动管理 → 评论管理** and metrics (`views`, `likes`, `comments`, `forwards`, `favorites`, `completionRate`) from **数据中心 → 动态数据**.
- Append snapshots to `analytics/snapshots.jsonl` and comments to `engagement/inbox.json`.
