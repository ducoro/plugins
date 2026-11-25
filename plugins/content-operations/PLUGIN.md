## Domain

End-to-end multi-platform content operations as a durable, file-backed loop across 14 social and editorial platforms—spanning topic sourcing, master copy and multimodal production, platform adaptation, scheduled publishing with live readback, engagement triage, analytics retrospectives, and interactive boards. Supports both single-Space end-to-end execution and multi-Space relay over one shared `content-ops/` Local Folder.

## Activation & Boundaries

Activate for planning, researching, drafting, producing visuals or videos, scheduling, publishing, triaging comments, reviewing performance, or maintaining boards for social/editorial content operations. Stay inactive for software engineering, Git commits or pull requests, competitive intelligence archiving, customer support ticketing, financial bookkeeping, sales CRM outreach, and recruiting pipelines.

## Operating Loop

1. **Locate or bootstrap the shared workspace**: Check `ducoro-cli local-folder list --json` and `ducoro-cli space resources get <space-id> --json` first. Reuse an existing `content-ops` folder; if none exists, ask the human before initializing `~/.ducoro/workspaces/content-ops` (or a human-chosen folder) via `skills/content-ops-loop/SKILL.md`.
2. **Load only the needed stage and platform modules**: Never load all 14 platform guides at once. Defer brand voice, target accounts, editorial taste, and business strategy to the Bot's own profile, Memory, and workspace `brand-profile.md`.
3. **Run the durable file-backed loop**: Intake & hard signal gate → Gate 1 topic commitment → format production & objective media/spec checks → Gate 2 tamper-proof publish confirmation → official-channel release (`Ducoro Core Connectors` first → official browser Creator Studio default → optional official OpenAPI) with live URL readback → guarded engagement triage → 24h/72h/7d/30d analytics snapshots & interactive board refresh.
4. **Orchestrate natively**: Schedule timed/recurring releases via `ducoro-cli task create`, fan out parallel channel runs via `ducoro-cli job dispatch` / `job start`, and hand off cross-role relay via `ducoro-cli space send`.

## Needs a Yes

Require explicit human confirmation before:
- **Workspace bootstrap**: Initializing and registering a new `content-ops` Local Folder path.
- **Gate 1**: Committing scored topics into active production slots.
- **Gate 2**: Publishing or scheduling live posts, sending sensitive/disputed comment replies, or triggering breakout amplification.
- **Official channel boundaries**: Pause for human login/CAPTCHA in official browser sessions; never extract cookies, call private reverse-engineered APIs, or bypass anti-bot gates.
- Always defer to stricter confirmation rules in the Bot's own profile.

## Resources & Tools

Progressive level-1 directory map (read deeper level-2/level-3 files only when needed):

- `skills/content-ops-loop/SKILL.md`: Workspace bootstrap, shared deterministic scripts, 5 interactive boards, approval gates, and issue reporting.
- `skills/topic-research-cn/SKILL.md`: Chinese-market trend radar, live hot boards, and Gate 1 briefs.
- `skills/topic-research-global/SKILL.md`: Global/English trend radar across keyless live sources and Gate 1 briefs.
- `skills/longform-writing/SKILL.md`: Long-form essays, newsletters, source ledger, and editorial checks.
- `skills/shortform-social/SKILL.md`: Short-form posts, threads, visual card decks (`ducoro-cli render`), covers, and motion cards.
- `skills/video-production/SKILL.md`: Short/long video scripting, loudness/SRT checks, clipping, and packaging.
- `skills/engagement-and-analytics/SKILL.md`: Comment triage, anti-spam guard, metric snapshots, and weekly retro.
- `references/platforms.md`: Level-2 index to all 14 per-platform playbooks, machine-readable `specs.json`, and optional official OpenAPI clients.
