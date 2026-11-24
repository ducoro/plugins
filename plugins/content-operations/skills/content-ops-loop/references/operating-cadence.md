# Operating Cadence, Native Scheduling & Stop Conditions

## Native Ducoro Scheduling First (No Polling Loops)

Do **not** create a polling cron job to repeatedly scan `calendar.json` for due slots. Ducoro natively schedules exact one-shot and recurring tasks, projects them onto the top-level **Plan** calendar (`ducoro-cli plan read`), catches up after offline restarts, and dispatches parallel runs:

- **Exact single- or multi-platform publish (`--at`)**: Publishing to 1 platform or 5 platforms uses the same native primitive—create an exact one-shot schedule task for the approved slot(s):
  ```sh
  ducoro-cli task create --space <space-id> \
    --at "2026-11-26T10:00:00+08:00" --timezone "Asia/Shanghai" \
    --title "Publish <draft-id> (X + LinkedIn + YouTube)" \
    --instruction "Verify Gate 2 variantHash for <slot-ids>, publish via connected Connectors/API/browser, record live URLs to publish-log.jsonl, and rebuild boards."
  ```
  - For concurrent multi-platform execution (or parallel heavy jobs), fan out independent channels with `ducoro-cli job dispatch --agent <agent-id> --name "<channel>" "<prompt>"` (or `ducoro-cli job start` for long local scripts such as `ffmpeg` slicing).
  - If a scheduled publish or review still needs a human sign-off first, attach native Inbox routing (`--human <human-id> --ask confirm --request-summary "<one-line summary>"`).
- **Role of `calendar.json` & `calendar-board`**: They hold the **content-domain ledger** (draft/variant links, Gate 2 `approvalRef` + tamper-proof `approvedVariantHash`, platform spec status, holiday anchors, and live readback URLs), while Ducoro's `task` + **Plan** own the actual wake-up clock.

## Recommended Recurring Loop Schedule (`--daily` / `--cron`)

| Rhythm | Suggested Schedule (`ducoro-cli task create`) | Scope & Output |
| --- | --- | --- |
| **Morning intake & topic scoring** | `--daily 09:00` (or `--cron "0 9 * * 1-5"`) | Scan Connectors/radars into `inbox/`, run `signal_gate.py` + `score_topics.py`, rebuild Pipeline Board, notify human (`--ask confirm` / Inbox) when shortlisted topics await Gate 1 |
| **Post-publish engagement sweep** | `--cron "0 12,18 * * *"` (plus one-shot `--at` T+1h golden window after major launches) | Pull new comments (Connector-first), triage into 4 tiers, check `engagement_guard.py` caps, draft replies, rebuild Engagement Board |
| **Due analytics & breakout check** | `--daily 10:00` | Run `aggregate_metrics.py --days 14 --stage-breakouts` to inspect `dueSnapshots` (`24h`/`72h`/`7d`/`30d`) and `breakoutCandidates`, pull live metrics, append `analytics/snapshots.jsonl`, rebuild boards |
| **Weekly retrospective** | `--cron "0 17 * * 5"` | Run `aggregate_metrics.py --days 7`, analyze topic × hook × format × timing, write `analytics/retros/YYYY-Www.md`, feed `## Next-Cycle Actions` into `inbox/`, rebuild all 5 boards |

## Stop & Escalation Conditions

Stop and hand back to the human immediately (via Inbox / direct confirmation) when:
1. A platform Connector or token is expired/revoked or returns `401`/`403` after one refresh attempt.
2. A platform triggers CAPTCHA, login challenge, or anti-bot friction—never attempt to bypass anti-bot gates.
3. A fact in an approved draft is discovered to be outdated or contradicted by current evidence—downgrade draft to `needs_update` and halt its scheduled publish task.
4. Daily engagement rate-limit cap is reached—pause further actions until cooldown resets.
5. Three consecutive runs fail on the same platform endpoint—halt that platform's queue, log diagnostic evidence, and if the failure indicates a plugin bug or upstream platform API/UI change, offer to submit a redacted report per `references/issue-reporting.md` (after user confirmation).

## Multi-Workspace Relay Handoff

When separate Spaces or workspaces handle monitoring, drafting, publishing, and analytics:
- **Shared root discovery**: register the canonical workspace once as a global Local Folder (recommended slug `content-ops`, default path `~/.ducoro/workspaces/content-ops`; use an external directory only if the user explicitly asks to store it outside `~/.ducoro/`). Every Space discovers its resolved path automatically via `ducoro-cli local-folder list --json` / `ducoro-cli space resources get <space-id> --json`.
- **Cross-Space handoff**: notify the downstream Space via `ducoro-cli space send` instead of relying on silent file polling.
- **Single-writer ownership** (prevents lost updates on mutable JSON files):
  - **Monitoring / Engagement / Analytics workspace**: writes `inbox/*.md`, `engagement/inbox.json`, `analytics/snapshots.jsonl`, `analytics/retros/*.md`.
  - **Drafting workspace**: exclusively owns `topics/topics.json`, `topics/briefs/*.md`, and `drafts/<id>/**` (including `meta.json`).
  - **Publishing workspace**: exclusively owns `calendar.json` (slot creation, Gate 2 `approvalRef` + `approvedVariantHash`, status updates), `publish-log.jsonl`, and `engagement/action-log.jsonl`. Publishing state truth lives in `calendar.json` and `publish-log.jsonl`—Publishing never concurrently mutates `drafts/<id>/meta.json`.
- **Tamper & drift guard**: before publishing any `approved` slot, the Publishing workspace recomputes the 16-char sha256 prefix of `variants/<platform>.md` and verifies it equals `slot.approvedVariantHash` (and `draft.status != "needs_update"`). On mismatch, halt, revert slot to `awaiting_approval` with a note, and request re-approval.
- Always run `validate_workspace.py` after mutating shared JSON files and `build_boards.py` after state transitions. Never overwrite append-only `.jsonl` logs—append new lines only.
