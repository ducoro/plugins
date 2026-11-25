# Competitive Intelligence & Signal Triangulation Methodology

Raw page diffs and release notes are only inputs—never hand unanalyzed raw change logs to the human. Apply four domain frameworks to turn verified captures into decision-ready intelligence.

## 1. Four-Quadrant Signal Triangulation

A single website edit can be cosmetic noise or an A/B test. High-confidence strategic calls require **cross-source triangulation** across at least two independent evidence classes:

| Signal Quadrant | Primary Real Sources | What Alone Looks Ambiguous | What Cross-Source Triangulation Proves |
|---|---|---|---|
| **Commercial & Packaging** | Pricing page diffs, terms/limits pages | Tier renamed or starter price nudged | Paired with Enterprise AE hiring + SSO release = deliberate upmarket pivot |
| **Product & Delivery Velocity** | GitHub Releases, npm, PyPI, App Store Lookup, Statuspage | Quiet blog for 6 weeks | Paired with steady minor bugfix releases + zero new feature hires = tech-debt / maintenance phase |
| **Resource & Talent Bets** | Greenhouse, Ashby, Lever public job boards | One exploratory AI engineer role | 4+ roles in one new department or region = funded 6–12 month roadmap commitment |
| **Market & Financial Reality** | HN Algolia discussions, SEC EDGAR 10-K/10-Q/8-K | Vocal single user complaint | Repeated migration complaints across threads + rising churn/risk disclosures in filings = exploitable vulnerability |

### Confidence Discipline (Enforced by `scripts/evidence_gate.py`)
- **`triangulated`**: Backed by `>= 2` distinct `sourceKinds` (e.g., `webpage` + `ashby_jobs` or `github_releases` + `hn_algolia`) in the verified capture pool.
- **`single_source`**: Verified factual observation from one source kind; report factually without over-claiming strategic intent until corroborated.

## 2. Strategic Intent Decoding Patterns

When changes pass `snapshot_diff.py`, test against common strategic patterns and explicitly check for counter-evidence:

- **Upmarket Move**: Free/starter caps tightened + enterprise security/SSO shipped + Enterprise AE / Solutions Architect roles opened → opportunity to capture price-sensitive SMBs left behind.
- **Bundling / Land-Grab**: Adjacent capability added free to core plan + acquisition or partner announcement → defend core workflow depth and expose bolted-on integration friction.
- **Defensive Price Cut / Discounting**: Sudden price drop or extended free tier without matching product launch → likely conversion pressure; check community threads for churn reasons before reacting on price.
- **Platform / Ecosystem Lock-In**: New SDKs on npm/PyPI + public API docs expansion → monitor developer adoption velocity, not just marketing claims.

## 3. Living Adversarial Battlecards (Comparison + Action)

Never write a battlecard as a passive feature-checkmark table. Every `battlecards/<slug>.json` must serve active decisions and deal conversations:

1. **`oneLiner`**: Objective one-sentence summary of who they serve and their core architectural bet.
2. **`threatLevel`**: `high` | `medium` | `low` based on target-customer overlap and execution velocity.
3. **`whenWeWin` / `whenWeLose`**: Honest boundaries—exact customer profiles where we win decisively AND scenarios where they hold a real edge (so time is not wasted on unwinnable fights).
4. **`landmines` (Offensive Discovery Questions)**: Neutral, factual questions a buyer can ask the competitor early to surface structural limitations (e.g., onboarding duration, hidden seat tiers, offline/data-ownership constraints).
5. **`objectionHandlers` (Defensive Talk Tracks)**: Paired `{ "objection": "...", "response": "..." }` anchored in verifiable facts—acknowledge genuine competitor strengths honestly, then reframe to buyer outcomes.
6. **`evidenceUrls`**: Every quantitative claim (prices, versions, hiring counts) must trace to captured URLs; never disparage competitors with unverified rumors.

## 4. One-Page Executive Brief Contract ("So What / Now What")

Every periodic or ad-hoc intelligence brief must fit one scannable page:
1. **Verified Fact & Evidence**: What materially changed, when observed, and direct source links.
2. **So What (Decoded Intent)**: What the cross-source pattern implies and confidence level (`triangulated` vs `single_source`).
3. **Now What (2–3 Concrete Options)**: Actionable responses for product, pricing, positioning, or content (with recommended option and trade-offs) for the human to decide.
4. **Honest Silence**: When `snapshot_diff.py` returns `no_material_change`, do **not** pad a brief with old news.
