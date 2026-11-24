# Writing Personas & Claim Discipline

Voice belongs entirely to the creator or publication (`brand-profile.md` / `style/style-profile.json`). The presets below are **optional starting points**, not a closed list—adapt, blend, or define any custom voice freely.

> **Hard boundary**: Voice never overrides factual honesty. Never fabricate first-person anecdotes, "a friend told me" stories, or unverified metrics. Only experiences supplied by the operator may be written as first-hand experience.

## Claim & Evidence Stratification

Keep four buckets distinct whenever a piece mixes reporting and commentary:
1. **Verified Fact**: directly backed by a URL, document, book/interview citation, or logged first-hand test.
2. **Inference**: logical deduction signaled as reasoning rather than confirmed fact.
3. **Opinion / Judgment**: explicit stance, ideally noting where it does or does not apply.
4. **User-Supplied Experience**: real anecdote provided by the human operator.

## Optional Starter Voice Presets

| Preset ID | Example Fit | Tone & Pacing |
| --- | --- | --- |
| `midnight-friend` | Personal essays, reflective letters | Candid, conversational, comfortable with nuance |
| `warm-editor` | Culture, lifestyle, human stories | Grounded narrative arc, lived details, unhurried flow |
| `industry-observer` | Market analysis, company teardowns | Measured, causal, balances upside with trade-offs |
| `sharp-journalist` | News commentary, investigations | Crisp lead, clean fact-vs-commentary separation |
| `cold-analyst` | Finance, strategy, operator memos | Restrained, quantified assumptions, explicit downside risks |
| `humor-storyteller` | Cultural essays, sharp takes | Playful contrast, tight punchlines, grounded premise |
| `tech-coder` | Engineering tutorials, postmortems | Command/code-first, exact versions, failure modes |

## Learning From Real Human Edits

When an operator revises an AI draft, log pairs with `scripts/learn_edits.py record`. Patterns only graduate to `style/style-playbook.md` after recurring (`occurrences >= 2`) within the same narrow scope, so one unusual piece never distorts future drafts.
