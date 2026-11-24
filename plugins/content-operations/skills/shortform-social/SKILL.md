---
name: shortform-social
description: "Craft short-form posts, threads, exact-pixel HTML social cards, LinkedIn PDF carousels, paired WeChat covers, thumbnails, and 3s/5s Live Photo motion cards using card_deck.py, live_photo.py, and ducoro-cli render."
---

# Short-Form Social & Visual Card Studio

Neutral workshop for short-form social copy, exact-pixel HTML visual cards, LinkedIn PDF carousels, and `3s/5s` Live Photo motion cards. Pair with **only the target platform skill(s)** (`../platform-<name>/SKILL.md`) so copy and visual choices fit that platform's audience and official rules.

## Starter Examples (`assets/examples/index.html`)
Browse 4 finished starter decks (`xhs-tool-teardown/`, `xhs-travel-route/`, `wechat-cover-pair/`, `xhs-live-photo/`) as reference points—follow them, adapt them, or create a completely custom visual style to match the user's taste and brand.

## References (Load on Demand)
- `references/shortform-and-card-guide.md` — variant JSON contract, thread syntax (`\n---\n`), `image_generate`, `ducoro-cli render` card/PDF pipeline, and `ducoro-cli media upload`.
- `references/card-design-system.md` — multi-platform frame sizes, 3 starter styles, 11 WCAG AA palettes, brand-color helper, and 11 starter `3:4`/`4:5` blueprints.
- `references/visual-craft-and-covers.md` — platform feed/crop mechanics, style trade-offs, image sourcing (`SOURCES.md`), text-on-image safety, and WeChat `2.35:1 + 1:1` covers.
- `references/category-playbooks.md` — niche-by-niche audience patterns and asset strategies for visual-first platforms.
- `references/live-photo-guide.md` — `5s` Xiaohongshu / `3s` WeChat Live Photo workflow (`scripts/live_photo.py`, `stack-3` / `grid-4` / `single`, `--crop-x`, native `.pvt` packaging, and desktop MP4/GIF fallback).

## Workflow

1. **Load native platform rules first.**
   - Read the target `../platform-<name>/SKILL.md` and `../platform-<name>/references/specs.json`.
   - Start from the approved brief (`topics/briefs/<topic-id>.md`) or canonical `master.md`; preserve factual accuracy while adapting hook and structure natively.
2. **Write native short copy (`variants/<platform>.md`).**
   - Open with a leading ```` ```json ```` metadata fence (`platform`, `mode`, `title`, `topics`, `media`, optional `cover`, optional `threads`, `options`)—never YAML frontmatter. Separate multi-post threads with `\n---\n`.
3. **Produce visual cards, PDF carousels, or Live Photo motion cards via deterministic pipelines.**
   - **HTML visual cards, covers & PDF carousels (no Board required)**: scaffold directly into the draft folder with `python3 scripts/card_deck.py scaffold <draft-dir>/deck --preset xhs-carousel|ig-carousel|linkedin-pdf|wechat-cover-pair|video-thumb --overwrite --json` (or author custom HTML with `[data-export-frame]`). Run `python3 scripts/card_deck.py audit <draft-dir>/deck --json` (objective dimensions, IDs, local assets, zero placeholders, WCAG AA contrast), verify real browser layout/fonts with `ducoro-cli render check --file <draft-dir>/deck/index.html --json`, and export directly into `drafts/<draft-id>/assets/` via `ducoro-cli render shot --file <draft-dir>/deck/index.html --all --out-dir <draft-dir>/assets --json` (pass `--format jpeg --quality 92` for Instagram/Meta APIs, or `ducoro-cli render pdf --file <draft-dir>/deck/index.html --out <draft-dir>/assets/deck.pdf --json` for LinkedIn PDF carousels). Create a Space Board (`ducoro-cli board new`) **only** if the human explicitly wants interactive click-to-comment review on the deck.
   - **Live Photo motion cards (user-supplied video clips)**: read `references/live-photo-guide.md`; run `live_photo.py probe` (use `contact-sheet` on long clips), preview `extract-frame`, then run `compose` + `package-pvt` (or `--fallback-mp4`/`--fallback-gif`) + `validate`.
   - **Pixel post-processing**: run `python3 ../content-ops-loop/scripts/image_ops.py` as needed.
4. **Validate specs before Gate 2.**
   ```sh
   python3 ../content-ops-loop/scripts/check_media_specs.py <workspace>/drafts/<draft-id> --update-meta
   ```

## Done When
- Native `variants/<platform>.md` fits the target platform and user's chosen style.
- Exported cards/PDF pass `card_deck.py audit` + `ducoro-cli render check` (or Live Photo bundles pass `live_photo.py validate`) and live in `drafts/<draft-id>/assets/`.
- `../content-ops-loop/scripts/check_media_specs.py --update-meta` exits `0` with zero errors.
