# Short-Form Packaging, Variant Contract & Exact-Pixel Card Pipeline

## 1. Variant File Contract (`variants/<platform>.md`)

Every variant starts with a ```` ```json ```` metadata fence parsed by `../content-ops-loop/scripts/check_media_specs.py` (never YAML frontmatter):

````markdown
```json
{
  "platform": "xiaohongshu",
  "mode": "image_text",
  "title": "Sharp native title",
  "topics": ["tag1", "tag2"],
  "media": [
    {"type": "image", "path": "assets/card-01.png"},
    {"type": "image", "path": "assets/card-02.png"}
  ],
  "options": {}
}
```

Publishable body copy goes here...
````

- **Threads (X/Twitter, Threads)**: separate sequential posts with `\n---\n` in the body (or `"threads": [...]` in JSON). `check_media_specs.py` enforces per-post character limits (including X 23-char `t.co` URL weighting and CJK/emoji double weighting).
- **Anti-drift rule**: never fabricate metrics, quotes, or personal experiences to make a hook punchier; if a character limit forces dropping a critical caveat, link to the source or narrow the claim.

## 2. Built-In AI Visuals (`image_generate` in Ducoro)

- Call built-in `image_generate` directly with `prompt`, `aspectRatio` (`3:4`, `4:5`, `16:9`, `1:1`, `2:3`), optional `size`, `quality`, `outputFormat`, `background`, `n`, and up to 16 current-Space relative `referencePaths`.
- Avoid asking AI image generators to render dense Chinese/UI typography—use `image_generate` for illustration/art, then place it inside HTML cards exported via `ducoro-cli render shot`.
- Start with `n: 1` and confirm with the user before multi-image batches; copy approved outputs into `drafts/<draft-id>/assets/`.

## 3. Exact-Pixel Visual Card Studio (`scripts/card_deck.py` + `ducoro-cli render`)

Use the bundled Visual Card Studio (3 visual languages, 11 WCAG-verified palettes, 11 semantic `3:4`/`4:5` blueprints, LinkedIn PDF carousels, paired WeChat `900x383` + `1080x1080` covers, and `1280x720` video thumbnails; see `references/card-design-system.md` & `references/visual-craft-and-covers.md`). **Do not create a Space Board solely to export images or PDFs**—author and render directly in `drafts/<draft-id>/deck/`:

1. Scaffold a local card deck folder with the chosen preset, style, and palette:
   `python3 scripts/card_deck.py scaffold <workspace>/drafts/<draft-id>/deck --preset xhs-carousel --style paper-studio --theme warm-linen --pages 5 --title "<Title>" --brand "@Handle" --overwrite --json`
   (Presets: `xhs-carousel` `3:4`, `ig-carousel` `4:5`, `linkedin-pdf` `4:5`, `wechat-cover-pair`, `video-thumb`, `full-showcase`. For custom brand color, pass `--brand-hex "#RRGGBB"`.)
2. Edit `index.html` with real copy and verified local visuals under `deck/assets/` (or write freeform custom HTML with `[data-export-frame="<id>"]` sized in explicit CSS pixels).
3. Run offline structural & contrast audit:
   `python3 scripts/card_deck.py audit <workspace>/drafts/<draft-id>/deck --json`
4. Run real Chromium layout, asset & font verification:
   `ducoro-cli render check --file <workspace>/drafts/<draft-id>/deck/index.html --json`
   (Fix errors and unintended overflow/font-fallback warnings, then re-check.)
5. Export exact-pixel images or PDF directly into `drafts/<draft-id>/assets/`:
   - All frames as individual PNGs (default):
     `ducoro-cli render shot --file <workspace>/drafts/<draft-id>/deck/index.html --all --out-dir <workspace>/drafts/<draft-id>/assets --json`
   - JPEG export (for Instagram / Meta Graph APIs):
     `ducoro-cli render shot --file <workspace>/drafts/<draft-id>/deck/index.html --all --format jpeg --quality 92 --out-dir <workspace>/drafts/<draft-id>/assets --json`
   - Single frame:
     `ducoro-cli render shot --file <workspace>/drafts/<draft-id>/deck/index.html --frame card-01 --out <workspace>/drafts/<draft-id>/assets/card-01.png --json`
   - LinkedIn / multi-page PDF carousel:
     `ducoro-cli render pdf --file <workspace>/drafts/<draft-id>/deck/index.html --out <workspace>/drafts/<draft-id>/assets/deck.pdf --json`
   - If `reason: "renderer-installable"` is returned, ask the human explicitly before running `ducoro-cli render install`.
6. Visually inspect the exported PNG/JPEG/PDF files, present them for human sign-off, and run `check_media_specs.py`.
7. **Optional Board review**: only if the human wants to click individual cards inside Ducoro to leave targeted comments, create a Board (`ducoro-cli board new --space <space-id> --title "<Card Deck Title>" --json`), scaffold into `<space-work-root>/boards/<board-id>`, and still export via `ducoro-cli render shot --file <board-dir>/index.html --all --out-dir <workspace>/drafts/<draft-id>/assets --json`.

## 4. Temporary Public HTTPS Media Relay (URL-Fetch APIs)

For official APIs that fetch media from a public HTTPS URL (**Instagram, Facebook Page, Threads, Pinterest**), keep canonical files locally in `drafts/<draft-id>/assets/` and upload **right before publish** via `ducoro-cli media upload <local-file> --json` (resumable upload up to 300 MiB, automatic 5-hour TTL, inspectable via `ducoro-cli media list --json`), or use user-owned HTTPS object storage/CDN if preferred.
