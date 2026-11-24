# Visual Card Design System & Starter Blueprints

HTML-based visual cards give far higher typography precision, adjustability, and consistency than asking image-generation models to render text directly. The styles, palettes, and blueprints bundled here are **neutral starter scaffolds and examples**—users and agents are free to pick a preset, mix elements, or author custom HTML/CSS for any brand or aesthetic while relying on `card_deck.py audit` and `ducoro-cli board check` for objective integrity checks.

## 1. Platform Export Frame Dimensions

`card_deck.py audit` recognizes standard multi-platform frame sizes out of the box (and accepts any custom size via `--allow-custom-size`):

| Frame Size | Ratio | Common Surfaces |
|---|---|---|
| `1080 × 1440` | `3:4` | Xiaohongshu carousel, Instagram portrait / profile grid, WeChat `newspic` |
| `1080 × 1350` | `4:5` | Instagram primary vertical feed |
| `1080 × 1920` | `9:16` | Stories, Reels/Douyin/Shorts vertical covers |
| `1080 × 1080` | `1:1` | Square carousels, WeChat share cover (`wechat-square`) |
| `900 × 383` | `2.35:1` | WeChat Official Account primary feed cover (`wechat-cover`) |
| `1280 × 720` | `16:9` | YouTube, Bilibili, WeChat Channels landscape thumbnail |
| `1200 × 675` | `16:9` | X/Twitter and LinkedIn landscape cards |
| `1000 × 1500` | `2:3` | Pinterest standard vertical pin |

## 2. Three Starter Visual Languages & 11 WCAG AA Palettes

Use these as fast, high-craft starting points when the user has not specified a custom design system:

| Starter Style (`data-style`) | Visual Character | Preset Themes (`data-theme`) |
|---|---|---|
| `paper-studio` | Warm tactile paper base, serif display headlines, editorial spacing | `warm-linen` (default), `celadon-ink`, `slate-ivory`, `oat-umber` |
| `grid-spec` | Subtle hairline matrix, clean sans display, monospace indices, crisp accent | `cobalt-grid` (default), `vermilion-spec`, `emerald-lab`, `amber-signal` |
| `darkroom-frame` | Deep charcoal canvas, warm light type, subtle studio depth | `obsidian-gold` (default), `midnight-cyan`, `plum-velvet` |

Need a brand color without manual contrast math? Derive an objective WCAG 2.1 AA-safe palette while preserving original hue and chroma as closely as possible:
```sh
python3 scripts/card_deck.py brand-theme "#2D6CDF" --style grid-spec --id brand --json
```
Or author custom CSS directly inside the Board HTML—`card_deck.py audit` enforces objective contrast only on declared theme blocks and never blocks custom styles.

## 3. Eleven Starter `3:4` Blueprints

Rotate, combine, or customize freely depending on the story:
1. `cover-split` — headline + lead + framed visual/diagram slot
2. `cover-bleed` — full-bleed photo with quiet-zone typography
3. `thesis` — single sharp statement + context note
4. `metric-hero` — primary verified figure + comparison bars
5. `compare-two` — two-column side-by-side contrast
6. `checklist` — numbered scannable action points
7. `step-flow` — sequential workflow steps with badges
8. `shot-stage` — framed UI screenshot showcase (`.device-browser` / `.device-phone`)
9. `quote-note` — editorial pull quote + practical note
10. `closing-cta` — summary frame with takeaway chips
11. `map-route` — offline route canvas (vector or local static map tile) with numbered pins & stop timings

## 4. Deterministic Ducoro Board Export Pipeline

1. `ducoro-cli board new --space <space-id> --title "<Deck Title>" --json`
2. Optional quick start via scaffold (or write custom HTML with `[data-ducoro-export-frame]`):
   ```sh
   python3 scripts/card_deck.py scaffold <space-work-root>/boards/<board-id> \
     --preset xhs-carousel --style paper-studio --theme warm-linen --pages 5 --overwrite --json
   ```
3. Author real copy, visuals (under `assets/`), and any custom CSS; keep `data-card` and `data-mark-item` unique for interactive Preview edits.
4. Run objective offline audit (dimensions, unique IDs, local image existence, zero leftover placeholders, WCAG AA contrast):
   `python3 scripts/card_deck.py audit <space-work-root>/boards/<board-id> --json`
5. Verify real browser layout & export exact PNGs/ZIP:
   `ducoro-cli board check --space <space-id> --board boards/<board-id> --json`
   `ducoro-cli board shot --space <space-id> --board boards/<board-id> --query pack=all --json`
