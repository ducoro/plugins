---
name: topic-research-global
description: Source global/English topics via connected MCP connectors, 6 keyless live radars (HN, Lobsters, GitHub, Polymarket, DEV.to, arXiv), and web verification; shard large feeds across subagents, enforce hard provenance/signal gates, and write Gate 1 briefs.
---

# Global Topic Research & Trend Radar

Capture global/English demand signals without mixing in domestic-CN feeds. **Strong models + subagents own semantic triage; deterministic scripts enforce provenance, deduplication, and the hard signal floor.**

## References (Load as Needed)
- `references/scoring-and-brief.md` — 4-dimension weighted rubric, trend/demand/evergreen mix, graduated cooldown, and brief template.
- `references/festival-calendar-global.md` — global seasonal and marketing planning windows.

## Four-Track Lawful Source Ladder (Never Scrape Cookies)

1. **Connected Platform Connectors (Highest Priority)**: Inspect available connectors with `ducoro-cli mcp catalog` and `ducoro-cli mcp status <slug>` (for example X, GitHub, YouTube, Reddit, Slack). Query authenticated feeds via `ducoro-cli mcp tools <slug>` / `ducoro-cli mcp call <slug> <tool>` and write results as `content-ops-signal-envelope/1` JSON (`region: "global"`).
2. **Verified Keyless Public Radars (Zero-Config Fallback)**:
   ```sh
   python3 scripts/fetch_hotspots_global.py --sources hackernews,lobsters,github,polymarket,devto,arxiv --query "<topic>" --window-days 30 --limit 30 --envelope > <workspace>/inbox/global-public.json
   ```
   (Omit `--query` for broad daily scanning; Reddit public JSON blocks unauthenticated requests, so route Reddit through a Connector or `web_search` `site:reddit.com`.)
3. **Primary Web Verification**: Use `web_search` and `web_fetch` to verify release notes, official docs, benchmarks, and high-signal discussions tailored to the target platform (`../platform-x-twitter/SKILL.md`, `../platform-youtube/SKILL.md`, `../platform-linkedin/SKILL.md`, etc.).
4. **Local Workspace Corpus**: Fold in `engagement/inbox.json` high-intent questions and `analytics/retros/` findings.

## Workflow

1. **Ingest & Deduplicate via Hard Provenance Gate (`signal_gate.py ingest`).**
   ```sh
   python3 ../content-ops-loop/scripts/signal_gate.py ingest \
     --input <workspace>/inbox/global-public.json \
     --workspace <workspace> --window-days 30 --mark-seen \
     --output <workspace>/inbox/global-pool.json
   ```
   - Rejects stale/malformed envelopes, drops rows without valid `http(s)://` URLs or ISO dates, canonicalizes URLs, merges duplicates keeping the richest engagement and `topComments`, and strips previously seen URLs into a pure `delta` pool.
2. **Semantic Triage & Parallel Sharding (Model + Subagents).**
   - For small pools (`<= 40` items): read `global-pool.json` directly to discard noise/off-topic chatter, cluster same-event items, extract sharp community quotes (`bestTakes`), and draft platform-native angles.
   - For large pools (`100–300+` items from broad Connector or multi-source pulls): **shard the pool into chunks of 40–60 items and dispatch parallel subagents** (or hand off specialized slices to sibling Spaces/bots via `ducoro-cli space send`) to triage concurrently, then synthesize the top candidates into `<workspace>/inbox/global-candidates.json` (`title`, `evidenceUrls`, `junkShape`, `isPrimarySource`, `bestTakes`, `angle`, `targetPlatforms`).
3. **Enforce Hard Signal Floor (`signal_gate.py gate`).**
   ```sh
   python3 ../content-ops-loop/scripts/signal_gate.py gate \
     --pool <workspace>/inbox/global-pool.json \
     --candidates <workspace>/inbox/global-candidates.json \
     --strict --output <workspace>/inbox/global-gated.json
   ```
   - Blocks any candidate citing an ungrounded/hallucinated URL (exit code `2` with `--strict`—fix the citation and re-run).
   - Enforces the hard floor (`distinctSources >= 2`, OR `isPrimarySource`, OR strong single-source engagement; `junkShape: true` requires `seedSourceCount >= 2`).
   - If `outcome == "nothing_solid"`, report honestly that this window has no solid signal (optionally mentioning `weakSignal`)—**never pad low-signal topics**.
4. **Score, Annotate Fuzzy Repeats & Pause at Gate 1.**
   - Write passed candidates into `topics/topics.json` (plus raw evidence snapshot `inbox/YYYY-MM-DD-<slug>.md`) and run:
     ```sh
     python3 ../content-ops-loop/scripts/score_topics.py <workspace> --cooldown-days 14
     ```
   - `score_topics.py` preserves distinct rows while annotating fuzzy title overlap (`>= 0.6`) via `repeatAnnotation` (inheriting `alreadyCovered: true` for previously produced/published topics).
   - Present shortlisted candidates at **Approval Gate 1**; write approved briefs to `topics/briefs/<topic-id>.md` and hand off to the matching format skill (`../longform-writing/SKILL.md`, `../shortform-social/SKILL.md`, or `../video-production/SKILL.md`) plus the target `../platform-<name>/SKILL.md`.
5. **Recurring Watchlist Automation (Optional).**
   - Register ongoing tracks in `<workspace>/watchlist.json` with `signal_gate.py watchlist <workspace> add --id <slug> --query "<topic>" --region global --cadence daily` and schedule recurring delta scans with `ducoro-cli task create --space <space-id> --daily 09:00 --instruction "..."`.

## Done When
- Signals passed `signal_gate.py ingest` and `signal_gate.py gate --strict` with zero provenance violations.
- Either `topics/topics.json` is scored via `score_topics.py` and approved briefs exist under `topics/briefs/<topic-id>.md`, or an honest `nothing_solid` report was recorded.
