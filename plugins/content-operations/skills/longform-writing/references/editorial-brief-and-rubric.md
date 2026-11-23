# Editorial Brief, Claim Grounding, 5-Dimension Rubric & Style Onboarding

Keep every long-form draft traceable from reader problem to verified sources to publishability gate.

## 1. Pre-Draft `brief.json` & `claims.json`

Before writing `master.md` for a substantive piece, save `sources.json` (via `scripts/source_ledger.py`), `brief.json`, and `claims.json` in `drafts/<draft-id>/`:

```json
{
  "version": 1,
  "audience": { "who": "Target reader", "context": "Reading situation", "question": "Problem to solve" },
  "goal": { "takeaway": "One repeatable conclusion", "action": "Concrete decision or next step" },
  "thesis": { "statement": "Core judgment", "novelty": "What is genuinely added", "boundary": "Where it holds", "counterpoint": "Strongest alternative view" },
  "personalMaterials": { "available": false, "items": [] },
  "framework": "opinion",
  "constraints": { "desiredLength": "1200-2500 chars", "mustInclude": [], "mustAvoid": [] }
}
```

```json
{
  "version": 1,
  "claims": [
    { "id": "C1", "text": "Specific claim", "type": "fact", "sourceIds": ["S1"], "status": "supported", "boundary": "Scope or date" }
  ]
}
```

- Run `python3 scripts/source_ledger.py verify-claims --ledger sources.json --claims claims.json --json`:
  - Every `fact` requires at least one `verified` source with an `http(s)://` URL (never mark model memory as `verified`).
  - Every `user_experience` requires a `user_provided` source explicitly supplied in the current task. When `personalMaterials.available` is `false`, never invent anecdotes, friends, dialogues, or sensory scenes—open with an observation, question, or core judgment instead.

## 2. Seven Writing Frameworks (Quick Reference)

| Framework | Best For | Progression |
| --- | --- | --- |
| `pain-point` | Reader faces a clear bottleneck | Scene -> Root cause -> Solution -> Boundary |
| `story` | People and turning points carry the lesson | Conflict -> Choice -> Outcome -> Meaning |
| `checklist` | Reader needs fast action | Goal -> Steps -> How to apply -> Pitfalls |
| `comparison` | Reader must choose between options | Criteria -> Evidence A/B -> Fit -> Recommendation |
| `trend-brief` | Fast-moving event or release | What happened -> Why it matters -> Impact -> Watchpoints |
| `opinion` | Judgment is the main value | Claim -> Evidence -> Counterpoint -> Boundary |
| `retro` | Transferable execution lessons | Goal -> Execution -> Variance -> Reusable takeaway |

Narrow the claim instead of padding sections when evidence is thin.

### Safe Content Enhancement (No "Plausible Reconstruction")
- **Opinion / Trend-Brief**: list consensus, split, and overlooked boundary conditions; add an evidence-backed causal angle rather than contrarianism for its own sake.
- **Pain-Point / Checklist**: fill actionable steps, prerequisites, costs, and failure signals (every tool/version/price must be verified).
- **Story / Retro**: use only user-supplied or verbatim-verifiable dates, quotes, and scenes; **never fabricate "plausible reconstructions," composite friends, or invented sensory details**.
- **Comparison**: establish shared criteria first, compare evidence + total cost + limits, and conclude who should choose what.

## 3. Five-Dimension Editorial Gate (`scripts/content_eval.py`)

Score each dimension from **1 to 5**:
1. **accuracy**: facts traced to direct sources; facts, inferences, and opinions cleanly separated.
2. **viewpoint**: clear thesis with added value, explicit boundary, and strongest counterpoint.
3. **usefulness**: directly answers the reader's problem with actionable steps or a reusable decision model.
4. **voice**: matches the publication voice without fabricating experiences or mimicking exemplar claims.
5. **readability**: opens fast, each section advances a claim, direct prose without filler or repetition.

Hard blockers (any one blocks publish): fabricated personal story, unsupported core fact, conclusion exceeding evidence, or missing reader takeaway.
- `publishable = true` only when `decision == "pass"`, `blockers == []`, minimum score `>= 3`, and average `>= 4.0`.
- Cap editorial revision at **2 passes**; if still failing on pass 2, drop unsupported claims and narrow the scope rather than faking a pass.
- **Anti-over-engineering guardrails**: never enforce mechanical quotas (such as forced hooks every N paragraphs, mandatory images every 400–500 chars, fixed section counts, or forced CTAs). Treat `check_writing_quality.py score` strictly as a diagnostic signal—never inject artificial choppy fragments or fake emotion just to game a score.

## 4. Style Onboarding (First-Time Voice Setup)

When `<workspace>/style/style-profile.json` does not exist, ask **1–2 conversational questions per turn** (never dump a long form):
- Required: publication/brand name + domain, core topics, desired tone.
- Optional (smart defaults): target audience, taboo words (`blacklist`), default WeChat theme (preview all 18 via `render_wechat_html.py --gallery`), and persona (auto-mapped from tone via `build_playbook.py init-style`).
- If the user has 5–30 historical articles, place `.md`/`.txt` files into `<workspace>/style/corpus/` and run `python3 scripts/build_playbook.py analyze --workspace <workspace> --json` to bootstrap `style/style-playbook.md`.
