# Visual Craft, Image Safety & Paired Cover Rules

Typography and CSS pass mechanical checks, yet a card can still fail human eyes in a mobile feed. Apply these visual craft rules before final export.

## 1. Image Sourcing Priority & Provenance

Real evidence beats decorative stock art. When the user supplies text only (no photos or screenshots), ask **once** at intake before designing:
- **A. User photos / screenshots (recommended)** — authentic, highest trust, least synthetic look.
- **B. Ducoro built-in `image_generate`** — best for conceptual illustrations or atmosphere visuals without embedded Chinese/UI text. Start with `n: 1` before batches.
- **C. Free-tier web photography** — search via `web_search` / `web_fetch` (prioritize Pexels for Chinese local scenes, Unsplash for clean lifestyle/outdoor scenes, or CC-licensed pools), download into the deck's local `assets/` directory, and log every URL in `assets/SOURCES.md` (`<filename> <- <source-url>`). Always disclose unverified copyright status and ask once whether to include a subtle credit caption.

Never leave live hotlinked `http(s)://` URLs in the final export deck—download approved visuals into `assets/` so `board shot` renders deterministically offline.

## 2. Text-on-Image & Subject Avoidance (`cover-bleed`)

Whenever typography sits directly over a photograph:
1. **Quiet-zone check first**: the photo must have a calm, low-detail band covering at least ~30% of the canvas (sky, blurred wall, shadow, calm water, fog) where text naturally reads cleanly. If the image is busy edge-to-edge, switch to `cover-split` instead of burying the photo under dark ink.
2. **Subject map before placing text**: inspect the photo visually first and record an HTML comment above the hero block noting where faces, hands, products, or focal edges sit and which band is safe. Never lay display text across a person's face or core product detail.
3. **Explicit `object-position` on every `<img>`**: never trust default `50% 50%` on tall `3:4` or wide `2.35:1` crops. Set `style="object-position: center 25%"` (subject high), `center 60%` (mid-body), or `center 75%` (foreground item) explicitly.
4. **No full-canvas black walls**: start without a scrim. If the thumbnail check still lacks contrast, add only a localized, image-toned gradient (`.soft-scrim-bottom` or `.soft-scrim-top` using `--tint-rgb`). Never use uniform full-canvas black overlays.
5. **360px thumbnail check**: inspect exported cover PNGs scaled down to mobile two-column feed width (~360px). If the title competes with the background, move the title to a quieter zone or switch to `cover-split`.

## 3. Portrait Vertical Balance (`1080 × 1440`)

A `3:4` portrait card is tall—layouts that work on widescreen slides easily collapse into an awkward top strip with a dead lower third.
- Plan each vertical slide across 5 bands: header meta, headline/lead, primary evidence (photo, screenshot stage, metric bars, comparison, or list), bottom takeaway strip (when needed), and pinned flex footer.
- Aim for active visual composition across **>= 75%** of the frame height. Intentional whitespace belongs to `thesis` or `cover-bleed` hero pages, not accidentally short 3-line bullet lists.
- Never force vertical centering with empty spacer divs to hide underfilled content—upgrade to a higher-presence blueprint (`quote-note`, `metric-hero`, `shot-stage`) or combine two thin points onto one stronger slide.
- Across a 5–9 slide carousel, use at least 4 distinct layouts and avoid repeating the exact same blueprint more than twice consecutively.

## 4. WeChat Cover Pair Discipline (`900 × 383` + `1080 × 1080`)

WeChat renders the `2.35:1` primary cover in subscription feeds and a `1:1` square thumbnail in chat forwards, Moments, and secondary slots. **Never blindly center-crop a `2.35:1` cover into `1:1`.**

Build both frames inside one Board (`--preset wechat-cover-pair`) sharing the same `data-style` and `data-theme`, but author **two distinct headlines**:
- **`wechat-cover` (`900 × 383`)**: carries the full or near-full descriptive headline (12–24 chars) + concise value subtitle.
- **`wechat-square` (`1080 × 1080`)**: carries an **independent short headline (4–10 Chinese chars, hard cap 16)** in large display type (`title-square`), zero cramped multi-line subtitles:
  - **Verb + Object**: `装备减重 3.4kg` / `一图看懂配置`
  - **Two-clause break** (explicit `<br />` at comma, <= 6 chars per line): `不堆参数，<br />只看实测`
  - **Number-led anchor**: `3 步避坑` / `省下 40% 时间`

`card_deck.py audit` enforces that every `900 × 383` frame is paired with a `1080 × 1080` frame and rejects verbatim copies of long (> 12 chars) headlines into the square cover.

## 5. Screenshot Framing (`shot-stage`)

When showcasing apps, web dashboards, code, or chat evidence:
- Preserve real screenshot legibility—never stretch aspect ratios or shrink UI labels to unreadable dust.
- Give the screenshot stage **50–65%** of the vertical canvas height; keep surrounding copy to one crisp headline + one directive sentence.
- Wrap desktop screenshots in `.device-browser` and mobile screenshots in `.device-phone` over `.shot-stage` so the evidence sits cleanly on a subtle CSS-only backdrop.

## 6. Honest Capability Boundaries

State boundaries clearly at intake rather than forcing a poor fit:
- **Strong fit**: structured carousels, tutorials, benchmarks, teardowns, checklists, travel/book/product notes, screenshot explainers, article cover pairs, video thumbnails.
- **Outside scope**: pure fashion/OOTD photography showcases, fine-art retouching, heavy decorative sticker/collage aesthetics, or full long-form video editing (route video work to `../video-production/SKILL.md`).
