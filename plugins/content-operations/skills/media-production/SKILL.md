---
name: media-production
description: Turn an approved topic brief into a fact-checked master draft, adapt native per-platform variants without fact drift, run deterministic image adjustments, and validate every draft against target platform specs. Use whenever writing copy, preparing visuals/videos, or running pre-publish spec checks.
---

# Media Production & Multi-Platform Adaptation

Produce one verified canonical draft first, then project it into native platform variants and spec-compliant media assets.

## Workflow

1. **Create draft folder under `content-ops/drafts/<draft-id>/`.**
   - Required files: `meta.json`, `master.md`, `variants/`, `assets/`.
   - Link `topicId` and `planId` (from `drafts/plans.json`) in `meta.json`.
2. **Write the canonical `master.md` first.**
   - Read `topics/briefs/<topic-id>.md` and `brand-profile.md`.
   - Lock every fact, number, quote, version, and URL in `master.md` with its source ref. No downstream platform variant may introduce an unverified claim or contradict `master.md`.
3. **Adapt native variants per platform (`references/master-to-channel.md`).**
   - Load each target `../platform-<name>/SKILL.md` and `../platform-<name>/references/specs.json`.
   - Write `variants/<platform>.md` with a **leading ```` ```json ```` metadata fence** (`platform`, `mode`, `title`, `topics`, `media`, optional `cover`, optional `threads`, `options`) followed by publishable body copy—never use YAML frontmatter (rejected by `check_media_specs.py`). Keep spoken video scripts in `drafts/<draft-id>/script.md` separate from the publishable caption.
4. **Produce and adjust visual/video assets (`references/visual-and-video-guide.md`).**
   - Use deterministic pixel edits (`scripts/image_ops.py`: `probe`, `ratio-crop`, `resize`, `compress`, `rounded`, and `overlay` for logos/QR/watermarks).
   - Always probe real dimensions first (`python3 scripts/image_ops.py probe <image>`) rather than guessing pixel coordinates.
5. **Run automated spec validation and quality gate.**
   ```sh
   python3 scripts/check_media_specs.py <workspace>/content-ops/drafts/<draft-id> --update-meta
   ```
   - Resolve every blocking issue (`required`, `too_big`, `too_small`, `invalid_combination`, `unsupported_format`, `unsupported_content_mode`, `invalid_duration`, `invalid_option`, `media_unreachable`). `--update-meta` also records the 16-char sha256 `variantHash` used for Gate 2 tamper verification.
   - Run the final human-facing review against `references/quality-and-safety-gate.md`, set `meta.json` status to `ready`, and refresh `pipeline-board`.

## Done When

- `master.md` has verified facts with sources.
- Every targeted platform variant exists under `variants/<platform>.md` and passes `check_media_specs.py` with zero errors.
- Local media assets live under `drafts/<draft-id>/assets/` with verified dimensions and file sizes.
