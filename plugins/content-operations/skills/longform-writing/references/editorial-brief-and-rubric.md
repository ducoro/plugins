# Editorial Brief, Channel Mechanics & Optional Rubric

Neutral domain knowledge for long-form publishing. Use the JSON schemas and evaluation tools when a piece is high-stakes or fact-heavy; skip unnecessary ceremony for short essays or opinion columns.

## 1. Long-Form Channel Mechanics (Where Platforms Actually Differ)

| Channel | Entry & Discovery | Reading Environment | Practical Adaptation |
| --- | --- | --- | --- |
| **WeChat Official Account** | Private subscriber push + Moments shares + Recommendation feed + WeChat Search | Mobile vertical scroll; dark mode common; external hyperlinks stripped for unverified accounts | Short mobile paragraphs (2–4 lines), clear scannable subheads, inline styles (`<section>`), external links converted to footnotes, 2.35:1 + 1:1 covers |
| **Email Newsletter** | Direct inbox (subject line + preview text determine open rate) | Mobile + desktop mail clients; high personal trust | Single clear promise in subject/preheader, conversational opening, links inline, easy skim-to-deep pacing |
| **Blog / Docs (SEO)** | Organic search intent + AI citation + referral links | Desktop + mobile web; readers arrive mid-task | Direct answer near the top, semantic `H2`/`H3` matching real queries, canonical URLs, durable evergreen examples |
| **LinkedIn / X Articles** | Social feed preview card + author authority + reposts/bookmarks | Fast social feed transitioning into long read | Sharp thesis in the opening 3 lines visible in feed preview, clean visual breaks, invite thoughtful disagreement in comments |

## 2. Optional Pre-Draft `brief.json` & `claims.json`

Useful for multi-source reporting, teardowns, or multi-agent handoffs:

```json
{
  "version": 1,
  "audience": { "who": "Target reader", "context": "Reading situation", "question": "Problem or curiosity" },
  "thesis": { "statement": "Core angle", "boundary": "Where it holds", "counterpoint": "Strongest alternative view" },
  "personalMaterials": { "available": false, "items": [] },
  "constraints": { "mustInclude": [], "mustAvoid": [] }
}
```

- When verifying claims via `scripts/source_ledger.py verify-claims`:
  - `fact` links to a `verified` source (either `web_url` with `http(s)://` URL, or `local_file` / `first_hand_test` / `publication_or_interview` with `--locator`).
  - `user_experience` links to a `user_provided` source supplied in the current task. Never invent composite friends or fake first-hand scenes.

## 3. Starter Structural Patterns (Examples, Not Mandates)

Authors and strong models are free to invent any structure that serves the material. Common starting shapes include:
- **Problem -> Cause -> Trade-off -> Action** (tutorials, operational guides)
- **Scene / Event -> Choice -> Consequence -> Reflection** (profiles, retrospectives, essays)
- **Claim -> Evidence -> Counter-evidence -> Boundary** (opinion, industry analysis)
- **Criteria -> Side-by-Side Comparison -> Fit by Persona** (tool/product evaluations)

Never enforce artificial quotas (fixed section counts, forced hooks every N paragraphs, mandatory images every 400 chars, or forced CTAs).

## 4. Optional 5-Dimension Evaluation Log (`scripts/content_eval.py`)

When running structured editorial review, score 1–5 across `accuracy`, `viewpoint`, `usefulness`, `voice`, and `readability` (customizable thresholds via `--min-avg` and `--min-dim`, no arbitrary cap on revision passes). Hard editorial blockers: fabricated personal story, unsupported core fact, or conclusion exceeding evidence.

## 5. Style Onboarding (First-Time Setup)

When `<workspace>/style/style-profile.json` does not exist, ask **1–2 conversational questions per turn** (domain, audience, preferred voice—never dump a long questionnaire). If historical articles exist in `style/corpus/`, run `scripts/build_playbook.py analyze` to extract real voice patterns instead of guessing.
