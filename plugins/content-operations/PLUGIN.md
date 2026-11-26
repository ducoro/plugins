## Domain

Multi-platform content operations across 14 social and editorial platforms—covering topic sourcing, master copy and multimodal production, adaptation, scheduled publishing with live readback, engagement triage, retrospectives, and interactive boards. Runs in the human's existing folder or current Space `files/`; shared directories are fallback-only for cross-Space relay.

## Activation & Boundaries

Activate for researching, drafting, producing visuals/videos, scheduling, publishing, triaging comments, reviewing performance, or maintaining boards for social/editorial content operations. Stay inactive for software engineering, Git commits/PRs, competitor intelligence, customer support, financial bookkeeping, sales CRM, and recruiting.

## Operating Loop

1. **Resolve working directory (no forced workspace)**: Check `ducoro-cli space resources get <space-id> --json` and `ducoro-cli local-folder list --json`. Use the human's existing folder first, or this Space's `files/` for single-Space work. Propose a global Local Folder only when multiple Spaces must share files and no folder fits—scoped to the initiative, never per Bot.
2. **Ducoro platform shortcuts (one-hop onboarding)**:
   - **Channels**: `ducoro-cli mcp catalog list|status|tools|call <slug> <tool> --args-file <path|-> --json` (Connectors -> official browser Creator Studio -> optional OpenAPI).
   - **Schedule (auto-lands in Plan)**: `ducoro-cli task create --space <id> --at <iso>|--daily <HH:MM>|--cron "<expr>" --timezone <tz> --title "..." --instruction "..."`.
   - **Inbox sign-off**: pair `--human <id> --ask confirm --request-summary "..."` on `task create`.
   - **Parallel fan-out**: `ducoro-cli job dispatch --agent <id> --name "<name>" "<prompt>"` / `job start`.
   - **Media, render, boards & relay**: `ducoro-cli render check|shot|pdf --file <path> --json`, `ducoro-cli media upload <path> --json`, `ducoro-cli board new --space <id> --title "..." --json`, and `ducoro-cli space send`.
3. **Load only needed modules & enforce gates**: Defer voice and strategy to Bot profile, Memory, and `brand-profile.md`. Run `signal_gate.py`, `check_media_specs.py`, and `validate_workspace.py --verify-slot <slotId>` (Gate 2 `variantHash` lock) before publishing with live URL readback.

## Needs a Yes

Require explicit human confirmation before:
- **Gate 1**: Committing scored topics to production slots.
- **Gate 2**: Publishing/scheduling live posts, sending sensitive/disputed replies, or breakout amplification.
- **Official channels**: Pause for human login/CAPTCHA; never extract cookies, call private APIs, or bypass anti-bot gates.
- **Cross-Space fallback**: Only if registering a new global Local Folder.
- Always defer to stricter rules in the Bot's own profile.

## Resources & Tools

Load deeper files on demand:

- `skills/content-ops-loop/SKILL.md`: End-to-end loop, shared scripts, 5 boards, gates, and issue reporting.
- `skills/topic-research-cn/SKILL.md`: CN trend radar, live hot boards, and Gate 1 briefs.
- `skills/topic-research-global/SKILL.md`: Global/EN trend radar and Gate 1 briefs.
- `skills/longform-writing/SKILL.md`: Essays, newsletters, source ledger, and editorial checks.
- `skills/shortform-social/SKILL.md`: Posts, threads, visual card decks (`ducoro-cli render`), covers, motion cards.
- `skills/video-production/SKILL.md`: Video scripting, loudness/SRT checks, clipping, and packaging.
- `skills/engagement-and-analytics/SKILL.md`: Comment triage, rate limits, metric snapshots, and weekly retro.
- `references/platforms.md`: Level-2 index to all 14 platform playbooks, `specs.json`, and optional OpenAPI clients.
