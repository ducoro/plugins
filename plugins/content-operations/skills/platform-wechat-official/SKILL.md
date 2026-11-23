---
name: platform-wechat-official
description: Run WeChat Official Account (公众号) end-to-end operations: deep long-form topic selection, scannable HTML article authoring and cover specs, Official Account API draft-box and freepublish workflows, and open-rate plus share retrospectives.
---

# WeChat Official Account (公众号) Operations Playbook

WeChat Official Accounts serve high-trust, private-domain subscribers and WeChat Search readers. Distribution hinges on headline open rate, finish-reading rate, and forwarding to chats/Moments.

## 1. Topic Discovery (WeChat-Native Radar)
- **WeChat topic density radar**: run `python3 scripts/search_wechat_articles.py "<keyword>" --days 7 --limit 10 --json` to observe recent Official Account coverage density (stops cleanly on CAPTCHA and falls back to `web_search`; never bypasses anti-bot gates). Combine with `../topic-research-cn/SKILL.md` for broader Chinese hot boards and Baidu/360 demand signals.
- **Trust & depth signals**: WeChat Search ("搜一搜") long-tail queries, high-forward industry essays, recurring reader replies in backend messages, and authoritative release/methodology deep dives.
- **Winning angles**: complete guides worth bookmarking, candid founder/practitioner retrospectives, structured industry analysis, and clear product changelogs.

## 2. Native Content, Themes & Two Formats
- **Format A — Long-form Article (`image_text`)**:
  - **Title (`<= 64` chars; sweet spot 16–28 Chinese chars)**: clear value proposition without cheap clickbait (which destroys finish rate and triggers unfollows).
  - **Cover (`2.35:1` primary `900x383` + `1:1` secondary share thumb)**: clean visual, readable when forwarded to a chat card (generate artwork with `image_generate` or render crisp typography via `ducoro-cli board shot`).
  - **Body (`<= 20000` chars)**: write clean Markdown first; enrich key sections with WeChat-safe container blocks (`:::callout tip|warning|info|danger`, `:::steps`, `:::timeline`, `:::pullquote`, `:::label`, `:::quote`, `:::dialogue`, `:::highlight`, `:::summary`), keep paragraphs short (3–4 lines on mobile), tables `<= 4` columns, inline images `<= 10` recommended, explicit `digest` (`<= 120` UTF-8 bytes, ~40 Chinese chars) and `author` (`<= 8` chars).
  - **Deterministic WeChat Rendering, 18 Standalone Themes, Gallery, Theme Learning & 16-Rule Validation**: always render through `scripts/render_wechat_html.py` (18 standalone theme files in `assets/themes/*.json` with distinct typography, line-height, quote cards, and 7 H2 structural styles: `professional-clean`, `sspai`, `warm-editorial`, `tech-modern`, `newspaper`, `bold-navy`, `midnight`, `bauhaus`, `bold-green`, `bytedance`, `elegant-rose`, `focus-red`, `github`, `impeccable`, `ink`, `lobster-notes`, `minimal-gold`, `minimal`; run `--gallery <gallery.html>` to compare all 18 themes side by side, and pass `--workspace <content-ops>` to include learned themes from `<workspace>/style/themes/*.json`; automatic inline CSS, dark-mode attributes, CJK-Latin spacing, bold-punctuation fix, `<section>` lists, and external-link footnotes; `--aigc-footer` is **off by default** and added only when requested). Never push raw unvalidated HTML.
  - **Replicate a favorite publication's theme or import a reference article**:
    - `python3 scripts/learn_theme.py <url> --name <slug> --workspace <content-ops> --json` (or `--file <saved.html>` when WeChat returns a verification page—never bypass anti-bot gates) extracts inline palette & section-numbering style into `<workspace>/style/themes/<slug>.json`, immediately usable via `render_wechat_html.py --workspace <content-ops> --theme <slug>`.
    - `python3 scripts/fetch_wechat_article.py <url> -o <out.md>` (or `--file <saved.html>`) converts a WeChat article into clean Markdown for structural study or exemplar extraction (`../longform-writing/scripts/extract_exemplar.py`).
- **Format B — Image Carousel (`newspic` / 小绿书)**:
  - **Title (`<= 32` chars)**, **1–20** `3:4` vertical images (`1080x1440`—reuse `../shortform-social/assets/card-deck-template/index.html` + `ducoro-cli board shot --query pack=all`), plain-text description (`<= 1000` chars, no HTML).
- **Topics**: no native `#topic` field in API; use WeChat article collections ("合集") in MP backend for series navigation.

## 3. Three-Stage Authorization & Publishing (`references/protocol.md`)
Keep authorization strictly separated: **"write / format / preview" never authorizes pushing to WeChat draft box, and "push draft" never authorizes public broadcast.**
1. **Stage 1 — Local draft, quality check & preview (always default; never auto-triggers image generation)**:
   - Prefer `illustrated.md` when present, otherwise render the approved `master.md` / `variants/wechat-official.md` without overwriting original copy. Never auto-invoke `image_generate` during formatting/preview; if a cover is missing when the user asks to stage a draft, fall back cleanly to local preview instead of assuming WeChat supplies a default cover.
   - Run `../longform-writing/scripts/check_writing_quality.py score <article.md>` (diagnostic only) and `../content-ops-loop/scripts/check_media_specs.py` against `references/specs.json`.
   - Render local preview & validate 16 WeChat HTML rules:
     ```sh
     python3 scripts/render_wechat_html.py <article.md> --theme professional-clean --mode preview -o <draft-dir>/wechat-preview.html --json
     ```
   - Stop here unless the human explicitly asks to push to the WeChat draft box.
2. **Stage 2 — Push to WeChat Draft Box (only after explicit human request)**:
   - **Default zero-config path (Official MP Web Backend)**: open `https://mp.weixin.qq.com/` (pause for QR scan if needed), paste formatted content from `wechat-preview.html` (**Copy for WeChat Editor**), upload inline images and `2.35:1` cover (or `3:4` cards for `newspic`) from `drafts/<id>/assets/`, and save draft (`draft_saved`).
   - **Optional official API path** (verified enterprise/organization Official Accounts with `WECHAT_OFFICIAL_APP_ID`, `WECHAT_OFFICIAL_APP_SECRET`, `WECHAT_OFFICIAL_ACCESS_TOKEN`, and an allowlisted public IP; unverified personal subscription accounts hit `errcode=48001` on draft/datacube endpoints and should immediately fall back to the default MP Web Backend path above, as should `40164` IP allowlist errors):
     - Rotate expired 2h tokens via `scripts/client.py get-token`.
     - Long-form one-step draft staging: `scripts/client.py [--dry-run] stage-draft --content-file <article.md|html> --cover <cover.jpg> --theme <name> [--aigc-footer]` (validates HTML, auto-uploads local inline images to WeChat CDN, uploads cover, and creates draft).
     - Image carousel (`newspic` / 小绿书): `scripts/client.py [--dry-run] add-image-post --title "..." --images <img1.png,img2.png,...> --content "..."`.
     - Low-level primitives (`upload-image`, `upload-thumb`, `add-draft`) remain available when needed.
3. **Stage 3 — Mobile Preview, Publish & Edit Learning**:
   - Pause at Gate 2 for mobile preview; only after explicit human confirmation publish via MP backend or `submit-publish` + `poll-publish`, and log the verified `article_url`.
   - When the human polishes a draft inside WeChat before/after publishing, read back the final text via `scripts/client.py get-draft --media-id <id>` and feed the pair into `../longform-writing/scripts/learn_edits.py` so future articles match the human's voice.
   - Pull analytics via `scripts/client.py fetch-stats --days 7 --workspace <content-ops>` (aggregates `/datacube/getarticlesummary` + `/datacube/getarticletotal` directly into `<workspace>/analytics/snapshots.jsonl`), or query single-day `user-read`, `user-cumulate`, `article-total`.

## 4. Engagement & Risk Guardrails
- Configure `need_open_comment` and `only_fans_can_comment` per post sensitivity.
- Pin helpful author replies in the comment section; move recurring reader questions into `inbox/`.
- Respect WeChat original-declaration rules and avoid prohibited medical/financial promises or external download redirects.

## 5. North-Star Metrics (`platformMetrics`)
Track `openRate`, `finishReadingRate`, `shareToChatCount`, `momentsShareCount`, and `netFollowerDelta` (via `/datacube/getarticletotal`, `/datacube/getarticlesummary`, `/datacube/getuserread`, and `/datacube/getusercumulate`).
