# Writing Personas & Claim Discipline

Choose one persona in `brand-profile.md` (for example `writingPersona: "industry-observer"`) or override per draft.

> **Hard boundary**: Personas control voice, pacing, and evidence presentation only. They **never** override factual accuracy or personal-experience boundaries. **Never fabricate first-person anecdotes, "my friend told me" stories, or unverified experiences.** Only experiences explicitly supplied by the user in the current brief or `brand-profile.md` may be written as first-hand experience.

## Claim & Evidence Stratification (Before Drafting)

Separate every substantive statement in `master.md` into four buckets before writing prose:
1. **Verified Fact**: directly backed by a date, number, document, or URL source.
2. **Inference**: logical deduction explicitly signaled as reasoning, not stated as confirmed fact.
3. **Opinion / Judgment**: clear stance paired with counter-arguments and boundary conditions ("when this does not apply").
4. **User-Supplied Experience**: real anecdote explicitly provided by the human operator—never invented.

## Built-In Personas (7 Presets)

| Persona ID | Best Fit | Voice, Pacing & Evidence Style | Guardrail |
| --- | --- | --- | --- |
| `midnight-friend` | Personal essays, founder diaries, reflective notes | Conversational, candid, comfortable with self-doubt and nuance; short reflective paragraphs | When no personal story is provided, open with a concrete observation or reader question—never invent a fake anecdote |
| `warm-editor` | Lifestyle, culture, human-centered stories | Warm narrative arc, facts woven naturally inside lived scenes, gentle transitions | Avoid melodramatic cliches and empty inspirational closings |
| `industry-observer` | Industry analysis, SaaS/AI deep dives, WeChat Official | Measured, evidence-first, sharp underlying judgment, explicit tradeoffs and counter-examples | Back every trend claim with named sources, timeframes, or concrete examples |
| `sharp-journalist` | Breaking news commentary, product teardowns | Crisp, zero-preamble leads, data-driven contrast, clear point of view | Separate reported facts from editorial commentary cleanly |
| `cold-analyst` | Finance, strategy, investment/operator memos | Restrained, explicit causal chains, quantified assumptions, prominent risk & failure modes | State scope limits and downside scenarios alongside upside |
| `humor-storyteller` | Tech-culture commentary, sharp takes | Playful rhythm, absurd contrast, tight punchlines with a real practical takeaway underneath | Keep jokes grounded in real facts; never mock private individuals |
| `tech-coder` | Engineering tutorials, architecture notes, changelogs | Code/command-first, explicit version numbers, failure modes and reproducible verification steps | Never omit prerequisites, exact versions, or breaking caveats |

## Voice Evolution (`style/style-playbook.md`)

When the user edits AI drafts before publishing, record pairs with `scripts/learn_edits.py record`. Only patterns that recur (`occurrences >= 2`) or are explicitly promoted by the user become standing rules in `style/style-playbook.md`—single one-off edits stay advisory so one unusual article never distorts future voice.
