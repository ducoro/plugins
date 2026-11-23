# Visual Card Design System & Blueprints

Use this guide when designing multi-slide social carousels (`3:4`), WeChat Official Account cover pairs (`2.35:1` + `1:1`), or `16:9` video thumbnails via `scripts/card_deck.py` and `ducoro-cli board shot`.

## 1. Choose One Visual Language Per Deck

Pick by **editorial stance**, not rigid topic stereotypes. Never mix two visual languages inside the same deck unless explicitly requested.

| Style (`data-style`) | Visual Character | Best Fit | Default Theme |
|---|---|---|---|
| `paper-studio` | Tactile paper base, serif display headlines, generous breathing room, soft hairline dividers | Narratives, essays, travel notes, reading digests, lifestyle guides | `warm-linen` |
| `grid-spec` | Subtle 48px hairline matrix, crisp sans display (**lighter weight at larger scale**), monospace indices, one vivid accent | Tool teardowns, benchmarks, SOP checklists, tutorials, AI & product explainers | `cobalt-grid` |
| `darkroom-frame` | Deep charcoal canvas, warm silver typography, subtle studio rim glow | Dark UI screenshots, hardware showcases, gaming/film reviews, night photography | `obsidian-gold` |

## 2. Preset Palettes (All WCAG 2.1 Verified)

Never invent arbitrary inline hex colors inside cards. Select one preset theme on `<html data-theme="...">`:

- **`paper-studio`**: `warm-linen` (default), `celadon-ink` (cool sage), `slate-ivory` (clean tech editorial), `oat-umber` (warm heritage)
- **`grid-spec`**: `cobalt-grid` (default), `vermilion-spec` (sharp red accent), `emerald-lab` (growth/health), `amber-signal` (alert/news)
- **`darkroom-frame`**: `obsidian-gold` (default), `midnight-cyan` (tech/night), `plum-velvet` (culture/film)

Inspect all contrast ratios any time via:
```sh
python3 scripts/card_deck.py themes --json
```

### Custom Brand Color (Constrained Derivation)
When the user requires a specific brand hex, derive a contrast-safe theme token block instead of pasting raw hex:
```sh
python3 scripts/card_deck.py brand-theme "#2D6CDF" --style grid-spec --id brand --json
```
Or pass `--brand-hex "#2D6CDF"` directly to `scaffold`. If the derived palette cannot satisfy WCAG 2.1 `4.5:1` contrast, the command fails cleanly—fall back to a preset.

## 3. Exact Export Frames

| Frame Preset | Exact Size | Target Surfaces |
|---|---|---|
| `3:4` vertical card | `1080 × 1440` | Xiaohongshu carousel, Instagram portrait carousel, WeChat `newspic` |
| WeChat primary cover | `900 × 383` (`2.35:1`) | WeChat Official Account primary feed header (always pair with `1080 × 1080`) |
| WeChat share cover | `1080 × 1080` (`1:1`) | WeChat chat card / Moments / secondary cover (independent short headline) |
| `16:9` thumbnail | `1280 × 720` | YouTube, Bilibili, WeChat Channels landscape cover |

## 4. Ten Semantic Layout Blueprints (`3:4`)

Rotate layouts across a 5–9 slide deck so no two adjacent content slides look identical:

1. **`cover-split`** — Eyebrow, punchy headline, concise lead, and a large framed visual slot. Safest default cover.
2. **`cover-bleed`** — Full-bleed photograph with quiet-zone typography (requires subject mapping and explicit `object-position`).
3. **`thesis`** — Single bold statement + evidence callout strip. Use when a slide carries one sharp insight.
4. **`metric-hero`** — Oversized verified stat + proportional comparison bars. Ideal for test results and benchmarks.
5. **`compare-two`** — Side-by-side two-column contrast (common pitfall vs. recommended approach).
6. **`checklist`** — Three numbered high-scannability cards with clear title + 1–2 line detail.
7. **`step-flow`** — Four-step vertical process track with monospace badges.
8. **`shot-stage`** — Pure-CSS textured backdrop with `.device-browser` or `.device-phone` chrome for real UI screenshots.
9. **`quote-note`** — Editorial pull quote with attribution plus practical takeaway band.
10. **`closing-cta`** — Highlight-bordered summary frame with 3 takeaway chips and a comment/save prompt.

## 5. End-to-End Ducoro Board Pipeline

1. **Create Board**: `ducoro-cli board new --space <space-id> --title "<Deck Title>" --json`
2. **Scaffold Deck**:
   ```sh
   python3 scripts/card_deck.py scaffold <space-work-root>/boards/<board-id> \
     --preset xhs-carousel --style grid-spec --theme cobalt-grid \
     --pages 5 --title "实测对比标题" --brand "@Handle" --overwrite --json
   ```
   (Use `--preset wechat-cover-pair` for paired `900×383` + `1080×1080` covers, or `--preset video-thumb` for `1280×720`.)
3. **Author Content & Visuals**: edit `index.html` with real copy and verified assets in `assets/`; preserve stable `data-card` and `data-mark-item` IDs so the human can click any slide in Preview to request targeted revisions.
4. **Offline Hard Audit**:
   ```sh
   python3 scripts/card_deck.py audit <space-work-root>/boards/<board-id> --json
   ```
   Fix every `error` (dimensions, duplicate IDs, missing assets, raw inline colors, tiny fonts, absolute footer, missing 1:1 WeChat pair, contrast failures).
5. **Live Browser Check & Export**:
   ```sh
   ducoro-cli board check --space <space-id> --board boards/<board-id> --json
   ducoro-cli board shot --space <space-id> --board boards/<board-id> --query pack=all --json
   ```
   Show the rendered PNGs to the user for visual sign-off, copy approved PNGs into `drafts/<draft-id>/assets/`, and run `../content-ops-loop/scripts/check_media_specs.py`.
