---
name: topic-research-global
description: Source global/English content topics from live builder boards (Hacker News, Lobsters), primary web research, global anchors, and feedback; deduplicate, score, and write Gate 1 briefs. Use for X, YouTube, TikTok, Instagram, Threads, LinkedIn, Facebook, Pinterest.
---

# Global Topic Research & Trend Radar

Capture global/English demand signals, verify primary sources, score candidates, and prepare Gate 1 topic briefs without mixing in domestic-CN feeds.

## References (Load as Needed)
- `references/scoring-and-brief.md` — 4-dimension weighted rubric, trend/demand/evergreen mix, graduated cooldown, and brief template.
- `references/festival-calendar-global.md` — global seasonal and marketing planning windows.

## Workflow

1. **Scan Global live signals into `<workspace>/inbox/`.**
   - **Global Live Tech & Builder Boards**: `python3 scripts/fetch_hotspots_global.py --limit 20 --json` (concurrent Hacker News + Lobsters; falls back to `web_search` if unavailable).
   - **Platform & primary-source research**: use built-in `web_search` and `web_fetch` to inspect release notes, changelogs, benchmark threads, and live conversations tailored to the target platform (`../platform-x-twitter/SKILL.md`, `../platform-youtube/SKILL.md`, `../platform-linkedin/SKILL.md`, etc.).
   - Save each raw batch as `inbox/YYYY-MM-DD-<slug>.md` with primary URLs, dates, verbatim facts, and unverified gaps.
2. **Merge, score, and check cooldown.**
   - Merge duplicate signals, assign a kebab-case `cooldownKey`, score `audiencePain`, `evidenceStrength`, `timeliness`, and `brandFit` (`1`–`5`), then run:
     ```sh
     python3 ../content-ops-loop/scripts/score_topics.py <workspace> --cooldown-days 14
     ```
3. **Pause at Approval Gate 1 & write Topic Briefs.**
   - Present shortlisted candidates with target audience, single core claim, verified evidence vs. gaps, target platform(s), and cooldown status.
   - Write approved briefs to `topics/briefs/<topic-id>.md` and hand off to the matching format skill (`../longform-writing/SKILL.md`, `../shortform-social/SKILL.md`, or `../video-production/SKILL.md`) plus the target `../platform-<name>/SKILL.md`.

## Done When
- Raw global signals are saved in `inbox/` with verifiable primary sources.
- `topics/topics.json` is scored and cooldown-checked via `../content-ops-loop/scripts/score_topics.py`.
- Approved topics have complete briefs under `topics/briefs/<topic-id>.md`.
