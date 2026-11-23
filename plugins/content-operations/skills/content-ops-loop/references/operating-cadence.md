# Operating Cadence & Stop Conditions

## Recommended Loop Schedule

| Rhythm | Scope | Output |
| --- | --- | --- |
| **Daily intake** | Scan internal updates, platform trends, and overnight comments into `inbox/`; run `score_topics.py` | Updated `topics/topics.json` + candidate list if high-score items emerge |
| **Pre-slot publish check** | 30–60 min before scheduled slot in `calendar.json`: re-verify facts, `approvedVariantHash`, spec status, and Gate 2 approval | Published entry + verified `publicUrl` in `publish-log.jsonl`, or hold slot as `awaiting_approval` with reason in `notes` |
| **Post-publish engagement sweep** | T+1h to T+2h (golden window) and daily sweep: pull comments, triage into 4 tiers, draft replies | Updated `engagement/inbox.json` + safe actions logged in `action-log.jsonl` |
| **Analytics snapshots** | T+24h, T+72h, and T+7d after each publish: pull work & account metrics | New rows in `analytics/snapshots.jsonl` + rebuilt Analytics Board |
| **Weekly retrospective** | Once per week: run `aggregate_metrics.py`, analyze topic × hook × format × timing, write `analytics/retros/YYYY-Www.md` | Concrete keep/kill/double-down action list fed back into `inbox/` and `topics/` |

## Stop & Escalation Conditions

Stop and hand back to the human immediately when:
1. A platform token is expired/revoked or returns `401`/`403` after one refresh attempt.
2. A platform triggers CAPTCHA, login challenge, or anti-bot friction—never attempt to bypass anti-bot gates.
3. A fact in an approved draft is discovered to be outdated or contradicted by current evidence—downgrade draft to `needs_update` and halt its scheduled slot.
4. Daily engagement rate-limit cap is reached—pause further actions until cooldown resets.
5. Three consecutive runs fail on the same platform endpoint—halt that platform's queue, log diagnostic evidence, and if the failure indicates a plugin bug or upstream platform API/UI change, offer to submit a redacted report per `references/issue-reporting.md` (after user confirmation).

## Multi-Workspace Relay Handoff

When separate Spaces or workspaces handle monitoring, drafting, publishing, and analytics:
- **Shared root discovery**: register the canonical workspace once as a global Local Folder (recommended slug `content-ops`, default path `~/.ducoro/workspaces/content-ops`; use an external directory only if the user explicitly asks to store it outside `~/.ducoro/`). Every Space discovers its resolved path automatically via `ducoro-cli local-folder list --json` / `ducoro-cli space resources get <space-id> --json`.
- **Single-writer ownership** (prevents lost updates on mutable JSON files):
  - **Monitoring / Engagement / Analytics workspace**: writes `inbox/*.md`, `engagement/inbox.json`, `analytics/snapshots.jsonl`, `analytics/retros/*.md`.
  - **Drafting workspace**: exclusively owns `topics/topics.json`, `topics/briefs/*.md`, and `drafts/<id>/**` (including `meta.json`).
  - **Publishing workspace**: exclusively owns `calendar.json` (slot creation, Gate 2 `approvalRef` + `approvedVariantHash`, status updates), `publish-log.jsonl`, and `engagement/action-log.jsonl`. Publishing state truth lives in `calendar.json` and `publish-log.jsonl`—Publishing never concurrently mutates `drafts/<id>/meta.json`.
- **Tamper & drift guard**: before publishing any `approved` slot, the Publishing workspace recomputes the 16-char sha256 prefix of `variants/<platform>.md` and verifies it equals `slot.approvedVariantHash` (and `draft.status != "needs_update"`). On mismatch, halt, revert slot to `awaiting_approval` with a note, and request re-approval.
- Always run `validate_workspace.py` after mutating shared JSON files and `build_boards.py` after state transitions. Never overwrite append-only `.jsonl` logs—append new lines only.

## Ready-to-Use Recurring Trigger Schedule (Cron Examples)

Configure recurring schedules with `ducoro-cli task create` against the registered Local Folder:

| Job | Suggested Cron (Local Time) | Action Trigger |
| --- | --- | --- |
| Morning intake & topic scoring | `0 9 * * 1-5` | Scan sources into `inbox/`, run `score_topics.py`, rebuild Pipeline Board, notify human if new shortlisted topics await Gate 1 |
| Pre-slot publish readiness | `*/30 * * * *` | Check `calendar.json` slots due in next 45 min; verify Gate 2 + `approvedVariantHash`; upload local media via `ducoro-cli media upload` right before API publish when required; log verified `publicUrl` |
| Engagement sweep | `0 12,18 * * *` | Pull new comments, triage into `engagement/inbox.json`, draft replies within daily rate caps, rebuild Engagement Board |
| Due analytics snapshots | `0 10 * * *` | Run `aggregate_metrics.py` to inspect `dueSnapshots` (`24h`/`72h`/`7d`/`30d`), pull live metrics, append to `analytics/snapshots.jsonl`, rebuild Analytics Board |
| Weekly retrospective | `0 17 * * 5` | Run `aggregate_metrics.py --days 7`, draft `analytics/retros/YYYY-Www.md`, feed `## Next-Cycle Actions` into `inbox/`, rebuild all 5 boards |
