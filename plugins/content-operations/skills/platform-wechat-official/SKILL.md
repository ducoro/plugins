---
name: platform-wechat-official
description: "Neutral WeChat Official Account (公众号) platform advisor covering private-domain vs recommendation-feed dynamics, WeChat HTML rendering across 18 themes, newspic (小绿书) carousels, 3-stage draft/publish authorization, and open/finish/share analytics."
---

# WeChat Official Account (公众号) Platform Expert Guide

WeChat Official Accounts serve **high-trust private subscribers**, **WeChat Recommendation feed (`看一看`/信息流)**, and **WeChat Search (`搜一搜`)**. Always defer to the mounted agent's own context (profile, memory, private skills, workspace state) for voice, goals, and targets.

## 1. Audience, Mindset & Distribution Mechanics
- **Two distinct traffic pools**: (1) **Private-domain push** — subscribers scan title + `2.35:1` cover inside their subscription feed (open rate + finish rate + forward-to-chat/Moments drive reach); (2) **Recommendation & Search** — non-subscribers discover posts by topic relevance, completion rate, likes/wow (`在看`), and exact search intent in `搜一搜`.
- **Content spectrum**: Supports everything from personal essays, literary columns, and cultural commentary to investigative journalism, founder letters, visual `小绿书` photo diaries, and structured tutorials. Match tone and structure to the reader's expectation—not one rigid template.
- **WeChat-native radar**: Run `python3 scripts/search_wechat_articles.py "<keyword>" --days 7 --limit 10 --json` to gauge Official Account topic coverage (stops cleanly on CAPTCHA; never bypasses anti-bot gates).

## 2. Formats, Specs & Deterministic HTML Toolchain
- **Format A — Long-form Article (`image_text`, `references/specs.json`)**:
  - **Title**: `<= 64` chars (16–28 CN chars avoids truncation in chat share cards). **Digest**: `<= 120` UTF-8 bytes (~40 CN chars). **Body**: `<= 20000` chars.
  - **Cover pair**: `2.35:1` (`900x383` headline) + `1:1` (`1080x1080` chat/secondary share) via `../shortform-social/scripts/card_deck.py scaffold <dir> --preset wechat-cover-pair`.
  - **Deterministic inline HTML (`scripts/render_wechat_html.py`)**: WeChat strips `<style>`, `<script>`, `<link>`, `@media`, `var(--*)`, and external fonts, and rewrites links for unverified accounts. Always render through `scripts/render_wechat_html.py` (18 standalone themes in `assets/themes/*.json` + `--gallery <out.html>` + `--workspace <ws>` for learned themes; supports 9 `:::container` blocks with custom/locale titles, `--no-cjk-spacing`, `--section-numbering`, and optional `--aigc-footer` off by default). Validator (`validate_wechat_html`) parses real HTML tags/styles cleanly—never false-flags CSS keywords inside prose or `<code>`.
  - **Theme learning & import**: `scripts/learn_theme.py <url|--file saved.html> --name <slug> --workspace <ws>` extracts inline palette/layout; `scripts/fetch_wechat_article.py <url|--file saved.html> -o <out.md>` converts articles to Markdown.
- **Format B — Image Carousel (`newspic` / 小绿书)**:
  - **Hard limits** (enforced by `check_media_specs.py`): Title `<= 32` chars, plain-text body `<= 1000` chars, **1–20 images** (`3:4` `1080x1440` preferred).

## 3. Three-Stage Authorization & Delivery (`references/protocol.md`)
**"Write/preview" never authorizes pushing to WeChat draft box; "push draft" never authorizes public broadcast.**
1. **Stage 1 — Local preview (default)**:
   - Run `../content-ops-loop/scripts/check_media_specs.py <draft-dir>` and render local preview:
     ```sh
     python3 scripts/render_wechat_html.py <article.md> --theme <name> --mode preview -o <draft-dir>/wechat-preview.html --json
     ```
   - Never overwrite approved `master.md` when adding images (`illustrated.md` instead). Stop here unless the human asks to push to the draft box.
2. **Stage 2 — Push to Draft Box (explicit human request)**:
   - **Default (MP Web Studio)**: open `https://mp.weixin.qq.com/` (pause for QR scan), paste via **Copy for WeChat Editor**, upload cover/images, save draft (`draft_saved`).
   - **Optional Official API** (verified enterprise/org accounts; unverified personal accounts hit `48001` and IP restrictions hit `40164` -> fall back to MP Web Studio):
     - `scripts/client.py get-token` (2h token)
     - `scripts/client.py [--dry-run] stage-draft --content-file <md|html> --cover <img.jpg> --theme <name> [--show-cover-pic 0|1] [--no-cjk-spacing]`
     - `scripts/client.py [--dry-run] add-image-post --title "..." --images <a.png,b.png> --content "..."`
3. **Stage 3 — Gate 2 Publish, Edit Learning & Stats**:
   - Verify Gate 2 (`validate_workspace.py --verify-slot <slotId>`), publish via MP Studio or `submit-publish` + `poll-publish`, and log verified `article_url`.
   - Read back human edits via `scripts/client.py get-draft --media-id <id>` for `learn_edits.py`; pull stats via `scripts/client.py fetch-stats --days 7 --workspace <ws>`.

## 4. Platform Red Lines & Engagement
- **Original declaration (`原创`)**: Publish on WeChat and declare Original **before** syndicating elsewhere so crawlers do not block your original badge.
- **Compliance**: Avoid external download redirects, unverified medical/financial promises, or deceptive clickbait (hurts finish rate and drives unfollows). Enforce `<= 6/hour`, `<= 30/day` via `engagement_guard.py`.

## 5. North-Star Metrics (`platformMetrics`)
Track `openRate`, `finishReadingRate`, `shareToChatCount`, `momentsShareCount`, and `netFollowerDelta`.
