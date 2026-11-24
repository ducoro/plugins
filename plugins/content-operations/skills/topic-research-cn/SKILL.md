---
name: topic-research-cn
description: Neutral Chinese-market topic research advisor sourcing signals via MCP connectors, CN hot boards (Weibo, Toutiao, Baidu), Baidu/360 search intent, platform-native cues, and web verification—with deterministic provenance/signal gates and Gate 1 briefs.
---

# CN Topic Research & Trend Radar

Capture Chinese-market demand signals across any vertical (consumer, lifestyle, travel, education, finance, B2B, tech, culture) without mixing in overseas/English feeds unless `--allow-mixed-regions` is explicitly requested. **Strong models + subagents own semantic triage; deterministic scripts enforce provenance, deduplication, and the signal floor.**

## References (Load as Needed)
- `references/scoring-and-brief.md` — customizable 4-dimension scoring rubric, cooldown rules, and Gate 1 brief template.
- `references/festival-calendar-cn.md` — Chinese seasonal, holiday, and e-commerce planning windows.

## Four-Track Lawful Source Ladder (Never Scrape Cookies)

1. **Connected Platform Connectors (Highest Priority)**: Check `ducoro-cli mcp catalog` / `status <slug>` for configured connectors; query via `ducoro-cli mcp call` and write `content-ops-signal-envelope/1` JSON (`region: "cn"`).
2. **CN Keyless Live Radars & Search Demand**:
   - **CN Hot Boards & General/Keyword News**:
     ```sh
     python3 scripts/fetch_hotspots_cn.py --limit 30 --envelope > <workspace>/inbox/cn-public.json
     ```
     (Pass `--query "<keyword>" --window-days 7` to pair filtered Weibo/Toutiao/Baidu hot boards with Chinese Google News search `gnews_cn`; without `--query`, `gnews_cn` fetches general CN headlines.)
   - **CN Search Autocomplete Demand**: `python3 scripts/seo_keywords_cn.py "<kw1>" "<kw2>" --json` (Baidu + 360 real search intent).
   - **Platform-Native Discovery Cues** (via `web_search` or user's browser session): Xiaohongshu search dropdown & "大家都在搜", Douyin 热点宝 / 巨量算数, WeChat 搜一搜 (or `../platform-wechat-official/scripts/search_wechat_articles.py` for WeChat Official), Bilibili 热搜 / 必刷, Zhihu 热榜.
3. **Primary Web Verification**: Use `web_search` and `web_fetch` to verify primary Chinese announcements, official reports, and real consumer questions.
4. **Local Workspace Corpus**: Fold in `engagement/inbox.json` reader questions and `analytics/retros/` findings.

## Workflow

1. **Ingest & Deduplicate (`signal_gate.py ingest`).**
   ```sh
   python3 ../content-ops-loop/scripts/signal_gate.py ingest \
     --input <workspace>/inbox/cn-public.json \
     --workspace <workspace> --window-days 7 --mark-seen \
     --output <workspace>/inbox/cn-pool.json
   ```
   - Pass `--allow-mixed-regions` only when intentionally running a cross-border CN+Global scan.
2. **Semantic Triage & Parallel Sharding.**
   - Triage against `brand-profile.md` (shard pools `>= 100` items across parallel subagents in chunks of 40–60), cluster same-event items, extract sharp reader questions/takes, and write `<workspace>/inbox/cn-candidates.json`.
3. **Enforce Provenance & Signal Floor (`signal_gate.py gate`).**
   ```sh
   python3 ../content-ops-loop/scripts/signal_gate.py gate \
     --pool <workspace>/inbox/cn-pool.json \
     --candidates <workspace>/inbox/cn-candidates.json \
     --strict --output <workspace>/inbox/cn-gated.json
   ```
   - Tune engagement floors (`--min-likes`, `--min-comments`, `--min-score`, `--single-source-floor`) for niche verticals where 20 strong comments matter more than viral volume.
   - If `outcome == "nothing_solid"`, report honestly instead of padding weak topics.
4. **Import, Score, Annotate Repeats & Pause at Gate 1.**
   ```sh
   python3 ../content-ops-loop/scripts/score_topics.py <workspace> \
     --import-gated <workspace>/inbox/cn-gated.json --cooldown-days 14
   ```
   - Customize `--weights` or `--shortlist-min` to match the channel's goals; candidates are preserved (not silently auto-archived unless `--auto-archive-below` is explicitly passed).
   - Present shortlisted candidates + `repeatAnnotation` at **Approval Gate 1**, write approved briefs to `topics/briefs/<topic-id>.md`, and hand off to the target format + platform skill.
5. **Recurring Watchlist (Optional)**: Manage tracks with `signal_gate.py watchlist <workspace> add --id <slug> --query "<topic>" --region cn --cadence daily` and schedule with `ducoro-cli task create`.

## Done When
- Signals passed `signal_gate.py ingest` and `gate --strict` with zero provenance violations.
- Either `topics/topics.json` is updated via `score_topics.py` and approved briefs sit under `topics/briefs/`, or an honest `nothing_solid` report was recorded.
