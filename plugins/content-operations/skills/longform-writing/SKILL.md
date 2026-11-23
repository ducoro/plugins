---
name: longform-writing
description: Author deeply researched, fact-grounded long-form articles (WeChat Official Account essays, newsletters, blogs, LinkedIn/X long-form) with verifiable source ledgers, 7 writing frameworks, 7 personas, 5-dimension editorial evaluation, corpus style bootstrapping, and scoped edit learning.
---

# Long-Form Editorial Writing Workshop

Produce deeply reasoned, evidence-grounded long-form articles without fabricated anecdotes, mechanical AI clichés, or unverified claims. Use this skill for essays, tutorials, teardowns, and industry columns—**do not load this heavy editorial workflow for short tweets, casual social posts, or short video scripts** (use `../shortform-social/SKILL.md` or `../video-production/SKILL.md` instead).

## References (Load on Demand)
- `references/editorial-brief-and-rubric.md` — pre-draft `brief.json` & `claims.json`, 7 writing frameworks, safe content enhancement, 5-dimension editorial gate, anti-over-engineering guardrails, and conversational style onboarding.
- `references/writing-personas.md` — 7 built-in voice presets and the 4-bucket claim/evidence boundary.
- `references/quality-and-safety-gate.md` — final factual, originality, copyright, and compliance checklist.

## Workflow

1. **Create draft folder & bootstrap voice if needed.**
   - Create `<workspace>/drafts/<draft-id>/` with `meta.json`, `sources.json`, `brief.json`, `claims.json`, `master.md`, `variants/`, `assets/`.
   - Read `brand-profile.md`, `style/style-profile.json`, and run `python3 scripts/learn_edits.py summarize <workspace> --framework <fw> --persona <persona> --json` to fetch only currently active, non-decayed rules matching this article's scope.
   - For first-time style setup or bootstrapping from 5–30 historical articles in `style/corpus/`, run `python3 scripts/build_playbook.py init-style` or `analyze`.
2. **Ground sources & claims before drafting (`scripts/source_ledger.py`).**
   - Record every verifiable external fact via `python3 scripts/source_ledger.py add --ledger <draft-dir>/sources.json --url "<url>" --title "..." --claim "..." --status verified` (never mark model memory as `verified`). Record user-supplied anecdotes strictly as `--status user_provided`.
   - Save `brief.json` and `claims.json`, then run `python3 scripts/source_ledger.py verify-claims --ledger <draft-dir>/sources.json --claims <draft-dir>/claims.json --json`. Every `fact` must link to a `verified` URL; every `user_experience` must link to a `user_provided` source.
   - Optionally load at most 2 same-framework exemplars (`python3 scripts/extract_exemplar.py list <workspace> --framework <fw> --limit 2 --json`) for structure and pacing calibration only (`personalMaterialsReusable` is always `false`).
3. **Draft, edit, and pass the 5-dimension gate (`scripts/content_eval.py`).**
   - Write `draft.md`, review and directly revise against `references/editorial-brief-and-rubric.md` (maximum 2 passes), save approved copy to `master.md`, and run:
     ```sh
     python3 scripts/check_writing_quality.py score <draft-dir>/master.md --json
     python3 scripts/content_eval.py --draft <draft-dir>/draft.md --final <draft-dir>/master.md --assessment <draft-dir>/assessment.json -o <draft-dir>/review-report.json --strict
     ```
   - Treat `check_writing_quality.py score` as a diagnostic signal only—never inject artificial choppy fragments or fake emotion to game a score.
4. **Keep approved copy immutable & hand off to target platform.**
   - Once `master.md` is approved (`publishable: true`), **never overwrite `master.md` when adding visuals**—insert inline images into an independent copy (`illustrated.md`) and validate assets via `../content-ops-loop/scripts/check_media_specs.py <draft-dir> --update-meta`.
   - Hand off platform-native formatting and publishing to the target platform skill (e.g., `../platform-wechat-official/SKILL.md` for WeChat 18-theme rendering, preview, and draft staging).
5. **Learn cautiously from human edits & exemplars (Voice Flywheel).**
   - After human edits, record using the narrowest true scope (`--scope global|content_type|framework|persona --scope-value <val>`):
     ```sh
     python3 scripts/learn_edits.py record <workspace> --draft <ai-draft.md> --final <human-final.md> --platform <platform> --scope <scope> --scope-value <val> --json
     python3 scripts/learn_edits.py summarize <workspace> --write-playbook --json
     ```
   - Add admired reference articles with `python3 scripts/extract_exemplar.py add <workspace> <article.md> --source "<name>" [--framework <fw>] [--user-authored] --json` (default ownership `third_party`; never copy claims or personal stories).

## Done When
- `sources.json` + `claims.json` pass `source_ledger.py verify-claims` with zero errors.
- `review-report.json` passes `content_eval.py --strict` (`publishable: true`).
- Target platform variant passes `../content-ops-loop/scripts/check_media_specs.py`.
