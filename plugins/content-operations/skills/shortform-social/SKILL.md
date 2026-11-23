---
name: shortform-social
description: Craft short-form posts, threads, and exact-pixel visual carousel cards for X/Twitter, Xiaohongshu, Threads, Instagram, Pinterest, Facebook, LinkedIn, and WeChat newspic using image_generate, ducoro-cli board shot, and automated spec checks.
---

# Short-Form Social & Visual Card Workshop

Write sharp, native short-form posts and render crisp visual cards without carrying long-form essay overhead. Always pair this skill with **only the target platform skill(s)** (`../platform-x-twitter/SKILL.md`, `../platform-xiaohongshu/SKILL.md`, `../platform-instagram/SKILL.md`, `../platform-threads/SKILL.md`, `../platform-pinterest/SKILL.md`, etc.) so X posts never pick up WeChat habits and Xiaohongshu notes stay native to Xiaohongshu.

## References (Load on Demand)
- `references/shortform-and-card-guide.md` — variant JSON header contract, thread syntax (`\n---\n`), `image_generate` & `ducoro-cli board shot` exact-pixel card deck pipeline, temporary HTTPS relay (`ducoro-cli media upload`), and anti-drift rewrite rules.

## Workflow

1. **Load the target platform's native rules first.**
   - Read the target `../platform-<name>/SKILL.md` and `../platform-<name>/references/specs.json` before drafting a single word.
   - Start from the approved brief (`topics/briefs/<topic-id>.md`) or canonical `master.md` if repurposing a long-form piece. Facts and numbers stay invariant; structure, hook, and phrasing are rebuilt natively for the target platform.
2. **Write native short copy (`variants/<platform>.md`).**
   - Open with a leading ```` ```json ```` metadata fence (`platform`, `mode`, `title`, `topics`, `media`, optional `cover`, optional `threads`, `options`)—never YAML frontmatter.
   - Lead with the sharpest observation, tension, or visual proof in the first 1–2 lines; cut filler intros and throat-clearing.
   - For multi-post threads (X/Twitter, Threads), separate sequential posts with `\n---\n` (or `"threads": [...]`).
   - When adapting the same idea across multiple platforms, verify true native rewrite rather than copy-paste cloning (`python3 ../longform-writing/scripts/check_writing_quality.py similarity <variantA.md> <variantB.md> --threshold 0.45 --json`).
3. **Produce crisp visual assets & carousel cards (`references/shortform-and-card-guide.md`).**
   - **Original AI visuals (Ducoro)**: call built-in `image_generate` (`prompt`, `aspectRatio`, `size`, `quality`, `outputFormat`, `background`, `n`, `referencePaths`); start with `n: 1` and confirm before large batches since it charges wallet balance.
   - **Exact-pixel HTML carousel cards & covers (Ducoro Board Shot)**: for Xiaohongshu/Instagram/WeChat newspic `3:4` carousels (`1080x1440`), landscape cards (`1280x720`), or covers (`900x383`), create an artwork Board (`ducoro-cli board new`), copy `assets/card-deck-template/index.html`, run `ducoro-cli board check` until clean, then export exact PNGs via `ducoro-cli board shot --query frame=<id>` or `--query pack=all`.
   - **Deterministic pixel post-processing**: run `python3 ../content-ops-loop/scripts/image_ops.py` (`probe`, `ratio-crop`, `resize`, `compress`, `rounded`, `overlay`) as needed.
4. **Validate specs before Gate 2.**
   ```sh
   python3 ../content-ops-loop/scripts/check_media_specs.py <workspace>/drafts/<draft-id> --update-meta
   ```
   Resolve every blocking issue (`required`, `too_big`, `too_small`, `invalid_combination`, `unsupported_format`, `media_unreachable`) before scheduling or publishing.

## Done When
- Native `variants/<platform>.md` matches the target platform's voice, hook cadence, and length limits.
- Visual cards/images live in `drafts/<draft-id>/assets/` with verified pixel dimensions and zero overflow.
- `../content-ops-loop/scripts/check_media_specs.py --update-meta` exits `0` with zero errors.
