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
   - Read `brand-profile.md` and any active workspace rules via `python3 scripts/learn_edits.py summarize <workspace> --json` (optional; filter by `--framework` / `--persona` when set). When `analytics/snapshots.jsonl` has history, optionally check `topHooks` via `../engagement-and-analytics/scripts/aggregate_metrics.py <workspace> --days 30` for proven opening inspiration.
   - For first-time style setup or bootstrapping from 5–30 historical articles in `style/corpus/`, run `python3 scripts/build_playbook.py init-style` (pass explicit `--persona` when chosen; otherwise recorded as `unspecified` for model judgment) or `analyze`.
2. **Ground facts proportionally (`scripts/source_ledger.py`, recommended for fact-heavy reporting).**
   - Never fabricate statistics, citations, quotes, or first-person anecdotes.
   - For reported or data-heavy pieces, record verifiable facts in `sources.json`:
     - Web sources: `python3 scripts/source_ledger.py add --ledger <draft-dir>/sources.json --url "<url>" --title "..." --claim "..." --status verified`
     - Non-web sources (local PDFs, books, interviews, first-hand benchmarks): add `--source-type local_file|first_hand_test|publication_or_interview --locator "<path or citation>"`.
     - User-supplied experiences: `--status user_provided`.
   - Verify before drafting with `python3 scripts/source_ledger.py verify-claims --ledger <draft-dir>/sources.json --claims <draft-dir>/claims.json --json`.
   - For personal essays or opinion pieces without external data claims, skip heavy ledger JSON while preserving zero-fabrication discipline.
3. **Draft, run physical telemetry, and enforce writer-reviewer isolation.**
   - Write `master.md` in the author's chosen voice and structure (not locked to a single template).
   - Optional physical text telemetry & cross-platform rewrite check (pure objective stats—never subjective quality scoring):
     ```sh
     python3 scripts/check_writing_quality.py probe <draft-dir>/master.md --json
     python3 scripts/check_writing_quality.py similarity <draft-dir>/master.md <draft-dir>/variants/<plat>.md --json
     ```
   - **Writer-reviewer isolation (mandatory for high-risk releases or final long-form sign-off)**: Never self-certify `<draft-dir>/assessment.json` in the same drafting context. Inspect seated peers with `ducoro-cli space participant list <space-id> --json`, dispatch isolated fresh read-only reviewer jobs via `ducoro-cli job dispatch [--space <space-id>] --agent <agent-id> --name "<lens>" "<prompt>"` across three orthogonal lenses—(a) **fact & provenance tracing** against `sources.json`/`claims.json`, (b) **platform red lines & compliance**, and (c) **reader subtraction** (cut throat-clearing, challenge weak leaps)—and collect verdicts via `ducoro-cli job status <job-id> --json` and `ducoro-cli job log <job-id>`. Record the independent review into `<draft-dir>/assessment.json`, then run:
     ```sh
     python3 scripts/content_eval.py --draft <draft-dir>/draft.md --final <draft-dir>/master.md --assessment <draft-dir>/assessment.json -o <draft-dir>/review-report.json
     ```
4. **Lock approved copy & adapt natively per channel.**
   - Once `master.md` is approved, record its 16-char sha256 as `approvedMasterHash` in `meta.json` (`validate_workspace.py` guards against accidental overwrites). Put image insertions into `illustrated.md` and validate platform variants via `../content-ops-loop/scripts/check_media_specs.py <draft-dir> --update-meta`.
   - Hand off platform-native rendering and delivery to the target `../platform-<name>/SKILL.md` (e.g., `../platform-wechat-official/SKILL.md`).
5. **Voice flywheel (optional, only after human edits).**
   - Record real human revisions under the narrowest scope (`scripts/learn_edits.py record ...` + `summarize --write-playbook`) and optional reference structures (`scripts/extract_exemplar.py add ... --genre <genre>`, `personalMaterialsReusable` is always `false`).

## Done When
- Factual claims are grounded (verified ledger for data-heavy reporting; zero fabricated experiences across all genres).
- `master.md` is approved (and untouched after approval), and target variants pass `../content-ops-loop/scripts/check_media_specs.py`.
