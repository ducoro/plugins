# Attribution Retrospective & Next-Cycle Feedback

A snapshot alone is vanity metrics. Every weekly retro (`analytics/retros/YYYY-Www.md`) separates *why* a post worked or failed across four factors so the next week's topics and hooks measurably improve.

## 4-Factor Attribution Diagnostic

| Observed Pattern | Likely Bottleneck | Concrete Next-Cycle Fix |
| --- | --- | --- |
| Low views + normal engagement rate among viewers | **Hook / Cover / Title / Timing** failed distribution gate | Rewrite cover headline contrast, tighten 0–3s opener, or shift publish slot |
| High views + low saves/bookmarks & low comments | **Topic or depth** felt generic/clickbait | Raise `evidenceStrength` floor; add concrete walkthroughs, numbers, or checklists |
| High saves/bookmarks + low likes | **High-utility reference content** (strong signal on X & Xiaohongshu) | Double down on this series; add a light closing prompt for comments |
| High comments + skepticism/confusion | **Missing caveat or unclear framing** | Turn the top objection into next week's follow-up topic and clarify `master.md` |
| Same `topicId` won on Platform A but flopped on Platform B | **Platform adaptation mismatch** | Check Platform B's native structure and format rather than discarding the topic |

## Breakout Amplification & Hook Recall
- **Breakout triggers (`aggregate_metrics.py --stage-breakouts`)**: Rather than waiting until the weekly retro to react, detect recently published works (default `<= 168h` old) outperforming the platform median (`>= 2.0x` by default) or explicit per-platform thresholds configured in optional `engagement/breakout-rules.json`:
  ```json
  {
    "defaults": { "baselineMultiplier": 2.0, "maxAgeHours": 168 },
    "platforms": {
      "x-twitter": { "minLikes": 40, "maxAgeHours": 168 },
      "linkedin": { "minInteractions": 30, "maxAgeHours": 120 }
    }
  }
  ```
  Staged entries land in `engagement/outbound-queue.json` with `status: "discovered"`, `requiresApproval: true`, and idempotency checks against both `outbound-queue.json` and `engagement/action-log.jsonl`.
- **Top historical hooks (`topHooks`)**: Pull proven opening lines from the account's own highest-performing drafts (`python3 scripts/aggregate_metrics.py <workspace> --days 30 --platform <plat>`) before drafting new openings—refine the hook first, then write the body.

## Weekly Retro Markdown Template (`analytics/retros/YYYY-Www.md`)

```markdown
# Weekly Content Retro — YYYY-Www

## Headline Numbers
- Works tracked: N | Total views: X | Avg engagement rate: Y%
- Top performer: <workId> (<platform>) — why it won
- Biggest miss: <workId> (<platform>) — bottleneck diagnosis

## Cross-Platform Same-Topic Takeaways
- <topicId>: Platform A vs Platform B delta and root cause

## Next-Cycle Actions (Auto-Parsed by Analytics Board)
- [ ] Double down: <specific follow-up topic + target platform>
- [ ] Fix bottleneck: <specific hook/format/timing adjustment>
- [ ] Recycle comment signal: <recurring audience question -> inbox/>
- [ ] Stop / cut: <underperforming pattern to drop>
```
