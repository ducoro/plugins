# Anti-Spam & Rate-Limit Safety Guardrails

Enforce per-account ceilings before executing any comment, like, follow, repost, or DM action. Caps below match `content-ops-loop/scripts/build_boards.py` (`DEFAULT_DAILY_CAPS`).

## Per-Platform Daily Safe Ceilings

| Platform | Max Actions / Hour | Max Actions / Day | Minimum Gap Between Actions |
| --- | --- | --- | --- |
| `x-twitter` | 15 | **80** | 30–60s jittered |
| `youtube`, `facebook`, `threads` | 12 | **60** | 30–60s jittered |
| `bilibili`, `tiktok`, `instagram`, `pinterest` | 10 | **50** | 45–90s jittered |
| `xiaohongshu`, `douyin`, `wechat-channels`, `kuaishou`, `linkedin` | 6–8 | **40** | 90–180s jittered |
| `wechat-official` | 6 | **30** | 90–180s jittered |

## Hard Safety Rules
1. **Check `engagement/action-log.jsonl` first.** Count today's rows (`executedAt` matching UTC `YYYY-MM-DD`). Once 80% of daily cap is used, reserve remaining slots for `high_intent` and `feedback` replies.
2. **Idempotent checks.** Before acting, confirm `(platform, accountId, targetId, actionType)` is not already logged as `result: "ok"` in `action-log.jsonl`.
3. **Immediate circuit breaker.** On any HTTP `429`, risk-control prompt, CAPTCHA, or temporary mute warning: halt all engagement on that account, log the error, and escalate to the human. Never bypass anti-bot challenges.
4. **No unsolicited bulk DMs or follow/unfollow churn.** Keep interactions contextual to comments on your own works or approved discussions.
