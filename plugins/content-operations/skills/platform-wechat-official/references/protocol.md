# WeChat Official Account API Protocol

## Environment Variables
- `WECHAT_OFFICIAL_APP_ID` & `WECHAT_OFFICIAL_APP_SECRET` (for `get-token` via `/cgi-bin/stable_token`)
- `WECHAT_OFFICIAL_ACCESS_TOKEN` (2h token used by draft, media, publish, and datacube endpoints)

## Local Formatting, Theme Learning & 16-Rule HTML Validation (`scripts/render_wechat_html.py`)
Always render Markdown through `scripts/render_wechat_html.py` (backed by shared rules & theme layout primitives in `scripts/wechat_html_rules.py` and 18 standalone theme files in `assets/themes/*.json`) before pasting into the WeChat editor or pushing a draft:
- `python3 scripts/render_wechat_html.py --list-themes [--workspace <content-ops>]` — list all 18 built-in themes plus any learned themes in `<workspace>/style/themes/*.json`.
- `python3 scripts/render_wechat_html.py [sample.md] --gallery <gallery.html> [--workspace <content-ops>] --json` — render a side-by-side HTML visual picker of all available themes.
- `python3 scripts/render_wechat_html.py <article.md> --theme <name> [--workspace <content-ops>] --mode preview -o <preview.html> [--aigc-footer] [--section-numbering] --json` — produces a standalone preview HTML with a one-click **Copy for WeChat Editor** button and automatic 16-rule compatibility checks (inline CSS only, no `<div>`/`class`/`id`/`<style>`, CJK-Latin spacing, bold punctuation fix, `<section>` lists, external links converted to footnotes, dark mode attributes, 120 UTF-8 byte digest truncation).
- `python3 scripts/render_wechat_html.py --validate-only <article.html> --json` — validate manually edited or external HTML (exits non-zero on any ERROR).
- `python3 scripts/learn_theme.py <url> --name <slug> --workspace <content-ops> --json` (or `--file <saved.html>` when WeChat shows a verification gate) — extract palette, serif/sans typography, and H2 layout into `<workspace>/style/themes/<slug>.json`.
- `python3 scripts/fetch_wechat_article.py <url> -o <out.md>` (or `--file <saved.html>`) — extract a public WeChat article to clean Markdown for structural study.
- `--aigc-footer` is **off by default**; enable it only when explicit AIGC disclosure is needed.

## Core Endpoints (`https://api.weixin.qq.com`)
1. **Fetch token**: `POST /cgi-bin/stable_token` (`scripts/client.py get-token [--force-refresh]`).
2. **Upload inline body image**: `POST /cgi-bin/media/uploadimg?access_token=<token>` (multipart `media`) → returns WeChat-hosted `url` for `<img src>` inside HTML.
3. **Upload cover / permanent image material**: `POST /cgi-bin/material/add_material?access_token=<token>&type=image` → returns `media_id` (`thumb_media_id` or `newspic` `image_media_id`).
4. **Create long-form draft**: `POST /cgi-bin/draft/add?access_token=<token>` — use `scripts/client.py stage-draft --content-file <md-or-html> --cover <cover.jpg> [--theme <name>] [--aigc-footer]` to validate HTML, automatically upload and rewrite every local inline image to WeChat CDN URLs, upload the cover, and stage the draft in one step (uses `ensure_ascii=False` so Chinese never expands into `\uXXXX`). Low-level `add-draft` remains available for pre-uploaded HTML.
5. **Create image carousel draft (`newspic` / 小绿书)**: `POST /cgi-bin/draft/add?access_token=<token>` with `article_type: "newspic"` via `scripts/client.py add-image-post --title <1-32 chars> --images <img1.png,img2.png,...> [--content <text>]`.
6. **Read back draft**: `POST /cgi-bin/draft/get?access_token=<token>` via `scripts/client.py get-draft --media-id <id>` — returns both HTML and stripped `plainText` so human edits made inside WeChat draft box can be fed into `../longform-writing/scripts/learn_edits.py`.
7. **Submit freepublish**: `POST /cgi-bin/freepublish/submit?access_token=<token>` (`{ media_id }`) → returns `publish_id`.
8. **Poll publish status**: `POST /cgi-bin/freepublish/get?access_token=<token>` (`{ publish_id }`) → wait until `publish_status == 0` and capture `article_detail.item[].article_url`.
9. **Analytics**:
   - Multi-day automated pull into workspace: `scripts/client.py fetch-stats --days 7 --workspace <content-ops>` (queries both `/datacube/getarticlesummary` and `/datacube/getarticletotal` and appends rows into `<workspace>/analytics/snapshots.jsonl` for `aggregate_metrics.py`)
   - Per-article daily summary: `POST /datacube/getarticlesummary?access_token=<token>` (`{ begin_date, end_date }`, max 1-day range)
   - Per-article cumulative breakdown: `POST /datacube/getarticletotal?access_token=<token>` (`{ begin_date, end_date }`, max 1-day range; returns day-by-day `int_page_read_count`, `share_count`, `add_to_fav_count`)
   - Aggregate read stats: `POST /datacube/getuserread?access_token=<token>` (`{ begin_date, end_date }`, max 3-day range)
   - Follower cumulate: `POST /datacube/getusercumulate?access_token=<token>` (`{ begin_date, end_date }`, max 7-day range)

## Default Official Browser Studio Path (Zero API Setup & Personal Account Fallback)
Unverified personal subscription accounts can view `AppID`/`AppSecret` in MP backend, but WeChat blocks draft and datacube APIs with `errcode=48001` (and unallowlisted host IPs return `errcode=40164`). Whenever credentials are absent or `48001`/`40164` occurs, switch immediately to the official browser studio:
1. Render a local preview first via `scripts/render_wechat_html.py <article.md> --theme <name> --mode preview -o <preview.html>`.
2. Open `https://mp.weixin.qq.com/` in the user's browser session (pause for WeChat QR scan when required).
3. For long-form articles, open **草稿箱 → 新的创作**, paste from the preview page (**Copy for WeChat Editor**), upload inline images + `2.35:1` cover directly from `drafts/<id>/assets/`; for **小绿书 (`newspic`)**, open **图片消息** and upload the `3:4` carousel PNGs (rendered via `ducoro-cli board shot`).
4. Save draft (`draft_saved`), ask the human to preview on mobile (Gate 2), and complete **发表 / 群发** only after explicit confirmation. Log the live `https://mp.weixin.qq.com/s/...` URL in `publish-log.jsonl`.
