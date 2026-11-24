---
name: longform-writing
description: Neutral long-form editorial advisor and toolkit for essays, deep dives, newsletters, and articles across WeChat Official Accounts, blogs, LinkedIn, and X Articles—with optional source ledgers, diff-tracked evaluation, corpus bootstrapping, and scoped edit learning.
---

# Long-Form Editorial Workshop

Serve as a neutral editorial advisor for long-form writing across any genre or voice (reported analysis, technical walkthroughs, founder essays, culture/lifestyle commentary, reviews, or narratives). Match the rigor to the piece rather than forcing one rigid process on every draft.

> Use `../shortform-social/SKILL.md` for social cards/short posts and `../video-production/SKILL.md` for video scripts.

## References (Load on Demand)
- `references/editorial-brief-and-rubric.md` — optional brief/claims schema, distribution differences across WeChat / Newsletter / Blog SEO / LinkedIn / X Articles, starter structural patterns, and conversational style onboarding.
- `references/writing-personas.md` — optional starter voice presets and the 4-bucket claim/evidence discipline.
- `references/quality-and-safety-gate.md` — factual, originality, copyright, disclosure, and platform compliance checklist.

## Workflow

1. **Align scope, audience, and channel realities.**
   - Create `<workspace>/drafts/<draft-id>/` (`meta.json`, `master.md`, `variants/`, `assets/`).
   - Read `brand-profile.md` and any active workspace rules via `python3 scripts/learn_edits.py summarize <workspace> --json` (optional; filter by `--framework` / `--persona` when set).
   - For first-time style setup or bootstrapping from 5–30 historical articles in `style/corpus/`, run `python3 scripts/build_playbook.py init-style` or `analyze`.
2. **Ground facts proportionally (`scripts/source_ledger.py`, recommended for fact-heavy reporting).**
   - Never fabricate statistics, citations, quotes, or first-person anecdotes.
   - For reported or data-heavy pieces, record verifiable facts in `sources.json`:
     - Web sources: `python3 scripts/source_ledger.py add --ledger <draft-dir>/sources.json --url "<url>" --title "..." --claim "..." --status verified`
     - Non-web sources (local PDFs, books, interviews, first-hand benchmarks): add `--source-type local_file|first_hand_test|publication_or_interview --locator "<path or citation>"`.
     - User-supplied experiences: `--status user_provided`.
   - Verify before drafting with `python3 scripts/source_ledger.py verify-claims --ledger <draft-dir>/sources.json --claims <draft-dir>/claims.json --json`.
   - For personal essays or opinion pieces without external data claims, skip heavy ledger JSON while preserving zero-fabrication discipline.
3. **Draft, revise, and run advisory diagnostics.**
   - Write `master.md` in the author's chosen voice and structure (not locked to a single template).
   - Optional advisory diagnostics (never game scores or inject artificial style):
     ```sh
     python3 scripts/check_writing_quality.py score <draft-dir>/master.md --json
     python3 scripts/content_eval.py --draft <draft-dir>/draft.md --final <draft-dir>/master.md --assessment <draft-dir>/assessment.json -o <draft-dir>/review-report.json
     ```
4. **Lock approved copy & adapt natively per channel.**
   - Once `master.md` is approved, record its 16-char sha256 as `approvedMasterHash` in `meta.json` (`validate_workspace.py` guards against accidental overwrites). Put image insertions into `illustrated.md` and validate platform variants via `../content-ops-loop/scripts/check_media_specs.py <draft-dir> --update-meta`.
   - Hand off platform-native rendering and delivery to the target `../platform-<name>/SKILL.md` (e.g., `../platform-wechat-official/SKILL.md`).
5. **Voice flywheel (optional, only after human edits).**
   - Record real human revisions under the narrowest scope (`scripts/learn_edits.py record ...` + `summarize --write-playbook`) and optional reference structures (`scripts/extract_exemplar.py add ...`, `personalMaterialsReusable` is always `false`).

## Done When
- Factual claims are grounded (verified ledger for data-heavy reporting; zero fabricated experiences across all genres).
- `master.md` is approved (and untouched after approval), and target variants pass `../content-ops-loop/scripts/check_media_specs.py`.
