---
name: shortform-social
description: Craft short-form posts, threads, multi-style 3:4 social carousels, paired WeChat 2.35:1+1:1 covers, and 16:9 thumbnails using image_generate, card_deck.py, and ducoro-cli board shot.
---

# Short-Form Social & Visual Card Studio

Write sharp, native short-form posts and render exact-pixel visual card decks without carrying long-form essay overhead. Always pair this skill with **only the target platform skill(s)** (`../platform-xiaohongshu/SKILL.md`, `../platform-wechat-official/SKILL.md`, `../platform-x-twitter/SKILL.md`, `../platform-instagram/SKILL.md`, etc.) so each platform stays native.

## References (Load on Demand)
- `references/shortform-and-card-guide.md` — variant JSON contract, thread syntax (`\n---\n`), `image_generate`, Board Shot export workflow, and `ducoro-cli media upload`.
- `references/card-design-system.md` — 3 visual languages (`paper-studio`, `grid-spec`, `darkroom-frame`), 11 WCAG-verified palettes, brand-color derivation, and 10 semantic `3:4` blueprints.
- `references/visual-craft-and-covers.md` — image sourcing & `SOURCES.md`, text-on-image subject safety, `3:4` vertical fill rhythm, WeChat `900x383` + `1080x1080` short-title cover pairs, screenshot framing, and scope boundaries.

## Workflow

1. **Load native platform rules first.**
   - Read the target `../platform-<name>/SKILL.md` and `../platform-<name>/references/specs.json` before drafting.
   - Start from the approved brief (`topics/briefs/<topic-id>.md`) or canonical `master.md`. Facts and numbers stay invariant; hooks and phrasing are rebuilt natively.
2. **Write native short copy (`variants/<platform>.md`).**
   - Open with a leading ```` ```json ```` metadata fence (`platform`, `mode`, `title`, `topics`, `media`, optional `cover`, optional `threads`, `options`)—never YAML frontmatter.
   - Lead with the sharpest observation, tension, or visual proof; separate threads with `\n---\n`.
   - Verify cross-platform anti-clone rewrites when adapting one topic across multiple surfaces (`python3 ../longform-writing/scripts/check_writing_quality.py similarity <variantA.md> <variantB.md> --threshold 0.45 --json`).
3. **Produce visual cards & cover pairs (`scripts/card_deck.py` + `ducoro-cli board shot`).**
   - **Intake visuals once**: prefer user photos/screenshots; if none exist, offer A (user supplies), B (`image_generate`, starting with `n: 1`), or C (free web photo downloaded locally with `assets/SOURCES.md`). State scope boundaries upfront for pure photography/OOTD shoots.
   - **Scaffold & author**: create a Board (`ducoro-cli board new`), scaffold with `python3 scripts/card_deck.py scaffold <board-dir> --preset xhs-carousel|wechat-cover-pair|video-thumb --style <style> --theme <theme> --overwrite --json` (or `--brand-hex "#RRGGBB"`), rotate blueprints across slides, and author an independent 4–10 char short headline for WeChat `1:1` covers.
   - **Audit, check & export**: run `python3 scripts/card_deck.py audit <board-dir> --json` until `passed: true`, verify live rendering with `ducoro-cli board check`, export PNGs via `ducoro-cli board shot --query frame=<id>` or `--query pack=all`, show images for human review, and copy approved files into `drafts/<draft-id>/assets/`.
   - **Pixel post-processing**: run `python3 ../content-ops-loop/scripts/image_ops.py` (`probe`, `ratio-crop`, `resize`, `compress`, `rounded`, `overlay`) as needed.
4. **Validate specs before Gate 2.**
   ```sh
   python3 ../content-ops-loop/scripts/check_media_specs.py <workspace>/drafts/<draft-id> --update-meta
   ```
   Resolve every blocking issue before scheduling or publishing.

## Done When
- Native `variants/<platform>.md` satisfies the target platform's voice, cadence, and limits.
- Visual cards/cover pairs pass `card_deck.py audit`, `ducoro-cli board check`, and visual review, and live in `drafts/<draft-id>/assets/`.
- `../content-ops-loop/scripts/check_media_specs.py --update-meta` exits `0` with zero errors.
