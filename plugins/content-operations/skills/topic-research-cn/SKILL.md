---
name: topic-research-cn
description: Source Chinese-market topics via connected MCP connectors, CN hot boards (Weibo, Toutiao, Baidu), Baidu/360 search demand, and web verification; shard large feeds across subagents, enforce hard provenance/signal gates, and write Gate 1 briefs.
---

# CN Topic Research & Trend Radar

Capture Chinese-market demand signals without mixing in overseas/English feeds. **Strong models + subagents own semantic triage; deterministic scripts enforce provenance, deduplication, and the hard signal floor.**

## References (Load as Needed)
- `references/scoring-and-brief.md` — 4-dimension weighted rubric, trend/demand/evergreen portfolio mix, demand-window rules, graduated cooldown, and brief template.
- `references/festival-calendar-cn.md` — Chinese seasonal and e-commerce planning windows.

## Four-Track Lawful Source Ladder (Never Scrape Cookies)

1. **Connected Platform Connectors (Highest Priority)**: Check `ducoro-cli mcp catalog` and `ducoro-cli mcp status <slug>` for configured connectors; query via `ducoro-cli mcp call <slug> <tool>` and normalize results into `content-ops-signal-envelope/1` JSON (`region: "cn"`).
2. **CN Keyless Live Radars & Search Demand**:
   - **CN Hot Boards & Keyword News**:
     ```sh
     python3 scripts/fetch_hotspots_cn.py --limit 30 --envelope > <workspace>/inbox/cn-public.json
     ```
     (Pass `--query "<keyword>" --window-days 7` to automatically include Chinese Google News RSS `gnews_cn` alongside filtered Weibo/Toutiao/Baidu hot boards.)
   - **CN Search Autocomplete Demand**: `python3 scripts/seo_keywords_cn.py "<kw1>" "<kw2>" --json` (Baidu + 360 long-tail search intent).
   - **WeChat-specific radar**: only when targeting WeChat Official Account, run `../platform-wechat-official/scripts/search_wechat_articles.py "<keyword>" --days 7 --limit 10 --json` (stops cleanly on CAPTCHA).
3. **Primary Web Verification**: Use `web_search` and `web_fetch` to verify primary Chinese announcements, official data, and native cues for Xiaohongshu / Douyin / Bilibili / Kuaishou per the target `../platform-<name>/SKILL.md`.
4. **Local Workspace Corpus**: Fold in `engagement/inbox.json` high-intent reader questions and `analytics/retros/` findings.

## Workflow

1. **Ingest & Deduplicate via Hard Provenance Gate (`signal_gate.py ingest`).**
   ```sh
   python3 ../content-ops-loop/scripts/signal_gate.py ingest \
     --input <workspace>/inbox/cn-public.json \
     --workspace <workspace> --window-days 7 --mark-seen \
     --output <workspace>/inbox/cn-pool.json
   ```
   - Rejects stale/malformed envelopes, drops rows lacking valid `http(s)://` URLs or ISO dates, canonicalizes URLs, merges duplicates keeping richest engagement/comments, and emits pure incremental `delta`.
2. **Semantic Triage & Parallel Sharding (Model + Subagents).**
   - For small pools (`<= 40` items): triage directly against `brand-profile.md`, cluster same-event hot items, extract sharp comment quotes (`bestTakes`), and draft platform-native angles.
   - For large pools (`100–300+` items): **shard into chunks of 40–60 items and dispatch parallel subagents** (or hand off platform slices via `ducoro-cli space send`), then consolidate into `<workspace>/inbox/cn-candidates.json` (`title`, `evidenceUrls`, `junkShape`, `isPrimarySource`, `bestTakes`, `angle`, `targetPlatforms`).
3. **Enforce Hard Signal Floor (`signal_gate.py gate`).**
   ```sh
   python3 ../content-ops-loop/scripts/signal_gate.py gate \
     --pool <workspace>/inbox/cn-pool.json \
     --candidates <workspace>/inbox/cn-candidates.json \
     --strict --output <workspace>/inbox/cn-gated.json
   ```
   - Fails closed (`exit 2`) if any candidate cites an ungrounded URL; enforces multi-source / primary-source / strong-engagement floor (`junkShape: true` requires `seedSourceCount >= 2`).
   - If `outcome == "nothing_solid"`, report honestly instead of padding low-signal topics.
4. **Score, Annotate Fuzzy Repeats & Pause at Gate 1.**
   - Write passed candidates to `topics/topics.json` (plus evidence snapshot `inbox/YYYY-MM-DD-<slug>.md`) and run:
     ```sh
     python3 ../content-ops-loop/scripts/score_topics.py <workspace> --cooldown-days 14
     ```
   - Review `repeatAnnotation` (non-destructive fuzzy overlap `>= 0.6` and inherited `alreadyCovered`) before presenting shortlisted candidates at **Approval Gate 1**.
   - Write approved briefs to `topics/briefs/<topic-id>.md` and hand off to the matching format skill (`../longform-writing/SKILL.md`, `../shortform-social/SKILL.md`, or `../video-production/SKILL.md`) plus the target `../platform-<name>/SKILL.md`.
5. **Recurring Watchlist Automation (Optional).**
   - Register tracks with `signal_gate.py watchlist <workspace> add --id <slug> --query "<topic>" --region cn --cadence daily` and schedule recurring delta runs via `ducoro-cli task create --space <space-id> --daily 09:00 --instruction "..."`.

## Done When
- Signals passed `signal_gate.py ingest` and `signal_gate.py gate --strict` with zero provenance violations.
- Either `topics/topics.json` is scored via `score_topics.py` and approved briefs exist under `topics/briefs/<topic-id>.md`, or an honest `nothing_solid` report was recorded.
