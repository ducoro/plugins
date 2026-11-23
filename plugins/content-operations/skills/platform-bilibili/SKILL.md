---
name: platform-bilibili
description: "Run Bilibili end-to-end video operations: deep-dive topic discovery, chaptered video scripting and 16:9 covers, strict category and copyright spec checks, OpenAPI multipart upload and submission, danmaku/comment engagement, and triple-action retrospectives."
---

# Bilibili Operations Playbook

Bilibili rewards depth, honesty, and long-tail search value. Viewers tolerate longer runtimes (`5–20+` min) when density stays high and titles deliver what they promise.

## 1. Topic Discovery (Platform-Native)
- **Long-tail search & community signals**: Bilibili search suggestions, partition hot rankings (`tid`), high-coin/high-favorite videos in your niche, and pinned technical questions in comments/danmaku.
- **Winning angles**: end-to-end tutorials, honest teardowns ("实测/拆解"), architecture/workflow deep dives, pitfall compilations, and structured series.

## 2. Native Content & Cover Structure
- **Cover**: `16:9` (`1280x720` or `1920x1080`, `jpg`/`png`, `<= 5 MB`), high visual contrast with crisp focal text legible in recommendation feeds.
- **Structure**: open with the payoff/result within 10 seconds, use clear chapters/timestamps, keep narration authentic (avoid stiff corporate scripts), and include a natural coin/favorite/follow cue only after delivering concrete value.
- **Copy limits**: title `<= 79` chars, description `<= 249` chars, total tags length `<= 199` chars; **video-only** (`mp4` / `flv`, up to 4 GB, 5 hours).
- **Mandatory metadata**: valid partition ID (`tid`), copyright flag (`1` original / `2` reprint—reprints require `source`), and optional `no_reprint` (`0` allow / `1` disallow).

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate against `references/specs.json` with `check_media_specs.py` (checks `tid`, `copyright`, and `cover`).
2. **Default zero-config path (Official Browser Studio)**: open `https://member.bilibili.com/platform/upload/video/frame` in the browser (pause for human sign-in/verification if prompted), upload the local video and `16:9` cover directly, fill title/partition/tags/description, save as draft (`draft_saved`) or pause before final submit until Gate 2 approval, then read back the live `BV` URL.
3. **Optional official OpenAPI path** (requires `BILIBILI_CLIENT_ID`, `BILIBILI_ACCESS_TOKEN`, and `BILIBILI_CLIENT_SECRET`): query live partition IDs (`tid`) via `python3 scripts/client.py [--dry-run] list-categories`, upload video chunks per `references/protocol.md`, submit via `scripts/client.py submit-archive`, and poll via `get-work --bvid <BV>` / `work-stats --bvid <BV>` / `account-stats`.
4. Record verified `https://www.bilibili.com/video/<bvid>` in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- Pin one comment summarizing timestamps, resource notes, or FAQ answers to anchor discussion.
- Treat technical critiques in comments/danmaku as `feedback` signals—acknowledge verified corrections openly.
- Avoid clickbait titles ("标题党") that trigger high bounce rates and negative danmaku sentiment.

## 5. North-Star Metrics (`platformMetrics`)
Track `coinToViewRatio`, `favoriteToViewRatio`, `tripleActionRate` (like + coin + favorite), `avgWatchProgress`, and `danmakuCount`.
