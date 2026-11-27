# Competitive Intelligence, Triangulation & Red-Team Verification

Raw page diffs and release notes are evidence inputs, not conclusions. Use these domain lenses and independent verification environments to turn verified captures into decision-ready judgment—while staying flexible to the human's actual question and Bot `PROFILE.md`.

## 1. Four-Quadrant Signal Triangulation

A single website edit can be cosmetic noise or an A/B test. High-confidence strategic calls require **cross-source triangulation** across at least two independent evidence classes:

| Signal Quadrant | Primary Real Sources | What Alone Looks Ambiguous | What Cross-Source Triangulation Proves |
|---|---|---|---|
| **Commercial & Packaging** | Pricing page diffs, terms/limits pages | Tier renamed or starter price nudged | Paired with Enterprise AE hiring + SSO release = deliberate upmarket pivot |
| **Product & Delivery Velocity** | GitHub Releases, npm, PyPI, App Store Lookup, Statuspage | Quiet blog for 6 weeks | Paired with steady minor bugfix releases + zero new feature hires = maintenance phase |
| **Resource & Talent Bets** | Greenhouse, Ashby, Lever public job boards | One exploratory AI engineer role | 4+ roles in one new department or region = funded 6–12 month roadmap commitment |
| **Market & Financial Reality** | HN Algolia discussions, SEC EDGAR 10-K/10-Q/8-K, local filings | Vocal single user complaint | Repeated migration complaints across threads + rising risk disclosures in filings = exploitable vulnerability |

### Confidence Discipline (Enforced by `scripts/evidence_gate.py`)
- **`triangulated`**: Backed by `>= 2` distinct `sourceKinds` captured for **the same entity** (e.g., `webpage` + `ashby_jobs`, `github_releases` + `hn_algolia`, or `webpage` + `local_doc`). Cross-entity URL borrowing is blocked.
- **`single_source`**: Verified factual observation from one source kind; report factually without over-claiming strategic intent until corroborated.

## 2. Strategic Intent Decoding Patterns (Reference Hypotheses)

Treat these patterns as testable hypotheses rather than foregone conclusions—always look for counter-evidence:

- **Upmarket Move**: Free/starter caps tightened + enterprise security/SSO shipped + Enterprise AE / Solutions Architect roles opened -> possible opening in price-sensitive SMB segments.
- **Bundling / Land-Grab**: Adjacent capability added free to core plan + acquisition or partner announcement -> verify whether integration depth matches standalone workflows.
- **Defensive Price Cut / Discounting**: Sudden price drop or extended free tier without matching product launch -> check community threads or filings for conversion/churn pressure before reacting on price.
- **Platform / Ecosystem Lock-In**: New SDKs on npm/PyPI + public API docs expansion -> check release cadence and adoption discussion, not just launch copy.

## 3. Independent Red-Team & Counter-Evidence Review (Environment Orchestration)

For **high-impact strategic calls** (`high`-severity changes, pricing or positioning calls, or major battlecard revisions), verify self-consistency in an **isolated read-only review environment** before presenting conclusions to the human:

1. **Isolate context to eliminate confirmation bias**:
   - Select a reviewer agent via `ducoro-cli space participant list <space-id> --json`.
   - Dispatch a read-only red-team job that receives **only**:
     - raw `<data-dir>/captures/diff.json`,
     - raw `<data-dir>/captures/latest.json` (plus any cited `entities/<slug>/local-docs/`), and
     - the concise draft conclusion.
   - Do **not** pass the analyst's prior reasoning transcript or leading assumptions.
   ```sh
   ducoro-cli job dispatch --space <space-id> --agent <reviewer-agent-id> --name "intel-redteam-<slug>" \
     "Read-only counter-evidence audit: inspect <data-dir>/captures/diff.json, <data-dir>/captures/latest.json, and this draft claim: <draft>. Do not modify files. Challenge it on three axes: (1) plausible alternative explanations (A/B test, compliance edit, seasonal promo, backfill hire), (2) confidence inflation (single_source or same-origin echo framed as triangulated), and (3) missing evidence or contradicting signals."
   ducoro-cli job status <job-id> --json
   ducoro-cli job log <job-id>
   ```
2. **Reconcile before shipping**: If the red-team reviewer surfaces a credible alternative explanation or unverified leap, downgrade confidence to `single_source`, narrow the claim to observed facts, or collect an orthogonal second source before notifying the human.

## 4. Optional Situational Output Templates

Choose the deliverable format that fits the human's question, the Bot's `PROFILE.md`, and the research type (quick answer, sector deep-dive, periodic radar digest, or sales enablement). Hard invariants are grounded evidence, honest confidence labels, and zero fabricated claims—format templates below are optional starting points, not rigid mandates:

### Option A: Adversarial Battlecards (`battlecards/<slug>.json`)
Useful when comparing direct competitors for product positioning or active deal support. Recommended fields (rendered by `battlecard-board`):
- `oneLiner`: Objective one-sentence summary of target buyer and architectural bet.
- `threatLevel`: `high` | `medium` | `low` based on customer overlap and execution velocity.
- `whenWeWin` / `whenWeLose`: Honest boundaries—where we hold an advantage and where they genuinely win.
- `strengths` / `gaps`: Evidence-backed competitor strengths and observable limitations.
- `landmines`: Neutral discovery questions that help buyers surface structural trade-offs.
- `objectionHandlers`: Paired `{ "objection": "...", "response": "..." }` anchored in verifiable facts.
- `evidenceUrls`: Captured URLs backing every quantitative claim.

### Option B: Concise Decision Brief ("So What / Now What")
Useful for executive updates or high-severity shift alerts:
- **Verified Fact & Evidence**: What materially changed, when observed, and direct source links / `localRef`.
- **So What (Decoded Intent & Counter-Hypotheses)**: What the pattern implies, confidence level (`triangulated` vs `single_source`), and key alternative explanations ruled in or out.
- **Now What (Concrete Options)**: 2–3 actionable options with trade-offs for the human to decide.
- **Honest Silence vs Direct Answers**: Stay quiet on `no_material_change` during scheduled sweeps; answer directly with checked scope and "no material change" when a human explicitly asks.
