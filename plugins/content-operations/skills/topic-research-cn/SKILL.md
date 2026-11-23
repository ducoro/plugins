---
name: topic-research-cn
description: Source Chinese-market topics from CN hot boards (Weibo, Toutiao, Baidu), Baidu/360 search demand probes, domestic seasonal anchors, and feedback; deduplicate, score, and write Gate 1 briefs. Use for WeChat, Xiaohongshu, Douyin, Bilibili, Kuaishou.
---

# CN Topic Research & Trend Radar

Capture Chinese-market demand signals, filter noise against `brand-profile.md`, score candidates, and prepare Gate 1 topic briefs.

## References (Load as Needed)
- `references/scoring-and-brief.md` — 4-dimension weighted rubric, 10-topic trend/demand/evergreen portfolio mix, demand-window rules, graduated cooldown, and brief template.
- `references/festival-calendar-cn.md` — Chinese seasonal and e-commerce planning windows.

## Workflow

1. **Scan CN live signals into `<workspace>/inbox/`.**
   - **CN Hot Boards**: `python3 scripts/fetch_hotspots_cn.py --limit 20 --json` (concurrent Weibo, Toutiao, Baidu; falls back to `web_search` if unavailable).
   - **CN Search Autocomplete Demand**: `python3 scripts/seo_keywords_cn.py "<kw1>" "<kw2>" --json` (Baidu + 360 autocomplete demand and related long-tail queries).
   - **Platform-specific radar**: when targeting WeChat Official Account, also run `../platform-wechat-official/scripts/search_wechat_articles.py "<keyword>" --days 7 --limit 10 --json` for WeChat topic density; for Xiaohongshu/Douyin/Bilibili, inspect native platform demand cues via `web_search` / `web_fetch` per the target `../platform-<name>/SKILL.md`.
   - **Deep verification**: verify primary sources, dates, and concrete figures via `web_search` and `web_fetch`, and save each batch as `inbox/YYYY-MM-DD-<slug>.md`.
2. **Merge, score, and check cooldown.**
   - Merge duplicate signals, assign a kebab-case `cooldownKey`, score `audiencePain`, `evidenceStrength`, `timeliness`, and `brandFit` (`1`–`5`), then run:
     ```sh
     python3 ../content-ops-loop/scripts/score_topics.py <workspace> --cooldown-days 14
     ```
3. **Pause at Approval Gate 1 & write Topic Briefs.**
   - Present shortlisted candidates with target audience, core claim, verified evidence vs. gaps, target platform(s), and cooldown status.
   - Write approved briefs to `topics/briefs/<topic-id>.md` and hand off to the matching format skill (`../longform-writing/SKILL.md`, `../shortform-social/SKILL.md`, or `../video-production/SKILL.md`) plus the target `../platform-<name>/SKILL.md`.

## Done When
- Raw CN signals are saved in `inbox/` with verifiable sources.
- `topics/topics.json` is scored and cooldown-checked via `../content-ops-loop/scripts/score_topics.py`.
- Approved topics have complete briefs under `topics/briefs/<topic-id>.md`.
