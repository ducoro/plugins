# Topic Scoring Rubric, Cooldown & Brief Contract

Shared scoring and brief contract for global/English topic research. See `../../topic-research-cn/references/scoring-and-brief.md` for the identical full rubric and template; key operational reminders:

- Default formula (`score_topics.py`): `audiencePain * 0.35 + evidenceStrength * 0.30 + timeliness * 0.15 + brandFit * 0.20`, customizable via `--weights` and `--shortlist-min`.
- `evidenceStrength <= 2` or `brandFit <= 2` keeps a topic in `candidate` until proof or angle improves. Candidates are never silently archived unless `--auto-archive-below` is explicitly set.
- `score_topics.py --import-gated <gated.json>` deterministically merges `signal_gate.py gate` winners into `topics/topics.json`, checks `--cooldown-days` (default 14; override with `cooldownOverrideReason`), and attaches non-destructive `repeatAnnotation`.
- Write approved Gate 1 briefs to `topics/briefs/<topic-id>.md` with: Topic ID, Approved By/Ref, Primary Audience, Core Angle, Lead/Secondary Platforms, Verified Evidence, Boundaries, and Planned Formats by Platform.
