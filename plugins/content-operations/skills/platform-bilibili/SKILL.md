---
name: platform-bilibili
description: "Neutral Bilibili (B站) platform advisor covering mid/long-form 16:9 community culture, triple-engagement (一键三连) and search-tail discovery, danmaku-friendly pacing, cover/title craft, creator studio/API delivery, and retention analytics."
---

# Bilibili (B站) Platform Expert Guide

Bilibili is a **community-driven mid/long-form video and knowledge-entertainment platform** anchored by bullet comments (`弹幕`), topic sub-communities (`分区`), and strong long-tail search. Always defer to the mounted agent's own context (profile, memory, private skills, workspace state) for voice, goals, and targets.

## 1. Audience, Mindset & Distribution Mechanics
- **Audience culture**: Younger, detail-sensitive, skeptical of blatant ads and shallow clickbait, and deeply appreciative of sincerity, craft, humor, and genuine depth. Viewers reward effort with **coins (`投币`, finite daily currency -> strongest quality signal)**, **saves (`收藏`)**, and **likes (`一键三连`)**.
- **Traffic entries**: (1) **Homepage feed (`推荐`)** — driven by `16:9` cover + title CTR paired with average watch percentage; (2) **Search (`搜索`)** — tutorials, reviews, game guides, essays, and tech/design breakdowns compound for months; (3) **Dynamic feed (`动态`)** — builds ongoing subscriber relationship via polls, text/image posts, and behind-the-scenes updates.
- **Danmaku & comments**: Moments that invite shared jokes, debates, or timestamped answers create high `弹幕` density and comment threads that keep the video circulating.

## 2. Formats & Content Spectrum
- **Specs (`references/specs.json`)**: Title `<= 79` chars; description `<= 249` chars (API) / longer in web studio; `16:9` `1080p/4K` `H.264/AAC MP4` up to 5 hours (`4GB`); `16:9` cover (`<= 5MB`, `1280x720` or `1920x1080`); dynamic `image_text` up to 9 images in browser mode.
- **Style spectrum**: Deep-dive video essays, candid product teardowns, vlog documentaries, coding/creative workflows, commentary/satire, music/art showcases, and serialized tutorials.
- **Packaging**: Design clean, high-contrast `16:9` thumbnails (`../shortform-social/scripts/card_deck.py --preset video-thumb` or real frame grabs); structure chapters cleanly (`看点/分段`) and respect `-14 LUFS` audio via `../video-production/scripts/video_ops.py probe --loudness`.

## 3. Delivery & Verification (`references/protocol.md`)
- Follow the shared Creator Studio / Gate 2 workflow in `../content-ops-loop/references/channel-access-matrix.md` and `approval-gates.md`.
- **Platform specifics**: Default path: `https://member.bilibili.com/` (full partition picker, chapter markers, interactive polls, dynamic posts). Optional OpenAPI: pass `--channel api` to `check_media_specs.py` (enforces `options.tid` and `options.copyright`; `copyright=2` reprint always requires `options.source`) and use `scripts/client.py` (`BILIBILI_ACCESS_TOKEN`).

## 4. Platform Red Lines & Engagement
- **Copyright & disclosure**: Declare original (`copyright=1`) vs. reprint (`copyright=2` with exact source) honestly; disclose commercial sponsorships via 花火 (`花火商单`) or natural transparent callouts (hidden stealth ads trigger fierce community backlash).
- **Rate cap**: Enforce `<= 10/hour`, `<= 50/day` (45–90s spacing) via `../engagement-and-analytics/scripts/engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `coverCtr`, `avgWatchPct`, `coinToViewRatio`, `saveToViewRatio`, and `danmakuDensity`.
