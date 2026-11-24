---
name: topic-research-global
description: Neutral global/English topic research advisor sourcing signals via MCP connectors, 7 keyless public radars (HN/Algolia, Lobsters, GitHub, Polymarket, DEV.to, arXiv, Google News), and web verification—with deterministic provenance/signal gates and Gate 1 briefs.
---

# Global Topic Research & Trend Radar

Capture global/English demand signals across any vertical (business, culture, health, science, consumer, finance, tech) without mixing in domestic-CN feeds unless `--allow-mixed-regions` is explicitly passed. **Strong models + subagents own semantic triage; deterministic scripts enforce provenance, deduplication, and the signal floor.**

## References (Load as Needed)
- `references/scoring-and-brief.md` — customizable 4-dimension scoring rubric, cooldown rules, and Gate 1 brief template.
- `references/festival-calendar-global.md` — global seasonal and marketing planning windows.

## Four-Track Lawful Source Ladder (Never Scrape Cookies)

1. **Connected Platform Connectors (Highest Priority)**: Check `ducoro-cli mcp catalog` / `status <slug>` (e.g., X, GitHub, YouTube, Reddit, Slack); query via `ducoro-cli mcp call` and normalize into `content-ops-signal-envelope/1` JSON (`region: "global"`).
2. **Verified Keyless Public Radars**:
   ```sh
   python3 scripts/fetch_hotspots_global.py --sources gnews,polymarket,hackernews,lobsters,github,devto,arxiv --query "<topic>" --window-days 30 --limit 30 --envelope > <workspace>/inbox/global-public.json
   ```
   - Select only the sources relevant to your domain: e.g., `--sources gnews,polymarket --gnews-topic BUSINESS` for general business/culture, or `--sources hackernews,github,arxiv --arxiv-cat cs.AI` for technical/research verticals. Without `--query`, `gnews` fetches general headlines (never forced into tech). Route Reddit via a Connector or `web_search` `site:reddit.com`.
3. **Primary Web Verification**: Use `web_search` and `web_fetch` to verify primary announcements, filings, studies, and audience discussions tailored to the target platform (`platform-x-twitter`, `platform-youtube`, `platform-linkedin`, `platform-instagram`, etc.).
4. **Local Workspace Corpus**: Fold in `engagement/inbox.json` audience questions and `analytics/retros/` findings.

## Workflow

1. **Ingest & Deduplicate (`signal_gate.py ingest`).**
   ```sh
   python3 ../content-ops-loop/scripts/signal_gate.py ingest \
     --input <workspace>/inbox/global-public.json \
     --workspace <workspace> --window-days 30 --mark-seen \
     --output <workspace>/inbox/global-pool.json
   ```
   - Pass `--allow-mixed-regions` when intentionally merging CN and Global feeds for bilingual/cross-border creators.
2. **Semantic Triage & Parallel Sharding.**
   - Triage against `brand-profile.md` (shard `100+` item pools into 40–60 item chunks across parallel subagents), cluster same-event items, extract sharp community takes (`bestTakes`), and save `<workspace>/inbox/global-candidates.json`.
3. **Enforce Provenance & Signal Floor (`signal_gate.py gate`).**
   ```sh
   python3 ../content-ops-loop/scripts/signal_gate.py gate \
     --pool <workspace>/inbox/global-pool.json \
     --candidates <workspace>/inbox/global-candidates.json \
     --strict --output <workspace>/inbox/global-gated.json
   ```
   - Tune engagement thresholds (`--min-likes`, `--min-comments`, `--min-score`, `--min-volume`, `--single-source-floor`) for specialized niches. If `outcome == "nothing_solid"`, report honestly instead of padding weak topics.
4. **Import, Score, Annotate Repeats & Pause at Gate 1.**
   ```sh
   python3 ../content-ops-loop/scripts/score_topics.py <workspace> \
     --import-gated <workspace>/inbox/global-gated.json --cooldown-days 14
   ```
   - Customize `--weights` or `--shortlist-min` to fit the channel's priorities; candidates remain preserved unless `--auto-archive-below` is explicitly set.
   - Present shortlisted candidates + `repeatAnnotation` at **Approval Gate 1**, write approved briefs to `topics/briefs/<topic-id>.md`, and hand off to the format + platform skill.
5. **Recurring Watchlist (Optional)**: Manage ongoing tracks with `signal_gate.py watchlist <workspace> add --id <slug> --query "<topic>" --region global --cadence daily` and schedule with `ducoro-cli task create`.

## Done When
- Signals passed `signal_gate.py ingest` and `gate --strict` with zero provenance violations.
- Either `topics/topics.json` is updated via `score_topics.py` and approved briefs sit under `topics/briefs/`, or an honest `nothing_solid` report was recorded.
