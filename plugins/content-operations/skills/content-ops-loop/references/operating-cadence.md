# Operating Cadence, Native Scheduling & Stop Conditions

## Native Ducoro Scheduling First (No Polling Loops)

Do **not** create a polling cron job to repeatedly scan `calendar.json` for due slots. Ducoro natively schedules exact one-shot and recurring tasks, projects them onto the top-level **Plan** calendar (`ducoro-cli plan read`), catches up after offline restarts, and dispatches parallel runs:

- **Exact single- or multi-platform publish (`--at`)**: Publishing to 1 platform or 5 platforms uses the same native primitive—create an exact one-shot schedule task for the approved slot(s):
  ```sh
  ducoro-cli task create --space <space-id> \
    --at "2026-11-26T10:00:00+08:00" --timezone "Asia/Shanghai" \
    --title "Publish <draft-id> (X + LinkedIn + YouTube)" \
    --instruction "Verify Gate 2 variantHash for <slot-ids>, publish via connected Connectors/browser/API, record live URLs to publish-log.jsonl, and rebuild boards."
  ```
  - For concurrent multi-platform execution, isolated review, or heavy local work, inspect seated peers via `ducoro-cli space participant list <space-id> --json`, fan out with `ducoro-cli job dispatch [--space <space-id>] --agent <agent-id> --name "<channel>" "<prompt>"` (or `ducoro-cli job start` for long local scripts such as `ffmpeg` slicing), and collect results via `ducoro-cli job status <job-id> --json` and `ducoro-cli job log <job-id>`.
  - For **immediate human sign-off** (without waiting for a scheduled slot), look up `<human-id>` via `ducoro-cli identity get --json`, create a manual task with native Inbox routing, and fire it immediately:
    ```sh
    ducoro-cli identity get --json
    ducoro-cli task create --space <space-id> --manual --title "Gate 2 approval: <slot-id>" \
      --human <human-id> --ask confirm --request-summary "<one-line action and target>" \
      --instruction "<verification and release instructions>" --json
    ducoro-cli task fire <task-id> --space <space-id> --json
    ```
- **Role of `calendar.json` & `calendar-board`**: They hold the **content-domain ledger** (draft/variant links, Gate 2 `approvalRef` + tamper-proof `approvedVariantHash`, platform spec status, holiday anchors, and live readback URLs), while Ducoro's `task` + **Plan** own the actual wake-up clock.

## Recommended Recurring Loop Schedule (`--daily` / `--cron`)

| Rhythm | Suggested Schedule (`ducoro-cli task create`) | Scope & Output |
| --- | --- | --- |
| **Morning intake & topic scoring** | `--daily 09:00` (or `--cron "0 9 * * 1-5"`) | Scan Connectors/radars into `inbox/`, run `signal_gate.py` + `score_topics.py`, rebuild Pipeline Board, notify human (`--ask confirm` / Inbox) when shortlisted topics await Gate 1 |
| **Post-publish engagement sweep** | `--cron "0 12,18 * * *"` (plus one-shot `--at` T+1h golden window after major launches) | Pull new comments (Connector-first), triage into 4 tiers, check `engagement_guard.py` caps, draft replies, rebuild Engagement Board |
| **Due analytics & breakout check** | `--daily 10:00` | Run `aggregate_metrics.py --days 14 --stage-breakouts` to inspect `dueSnapshots` (`24h`/`72h`/`7d`/`30d`) and `breakoutCandidates`, pull live metrics, append `analytics/snapshots.jsonl`, rebuild boards |
| **Weekly retrospective** | `--cron "0 17 * * 5"` | Run `aggregate_metrics.py --days 7`, analyze topic × hook × format × timing, write `analytics/retros/YYYY-Www.md`, feed `## Next-Cycle Actions` into `inbox/`, rebuild all 5 boards |

## Stop, Circuit-Breaker & Recovery Conditions

Stop and hand back to the human immediately (via Inbox / direct confirmation) when:
1. A platform Connector or token is expired/revoked or returns `401`/`403` after one refresh attempt.
2. A platform triggers CAPTCHA, login challenge, or anti-bot friction—never attempt to bypass anti-bot gates.
3. A fact in an approved draft is discovered to be outdated or contradicted by current evidence—downgrade draft to `needs_update` and halt its scheduled publish task.
4. Daily engagement rate-limit cap is reached—pause further actions until cooldown resets.
5. Three consecutive runs fail on the same platform endpoint—trip the circuit breaker for that platform's queue, log diagnostic evidence, and if the failure indicates a plugin bug or upstream platform API/UI change, offer to submit a redacted report per `references/issue-reporting.md` (after user confirmation).

### Circuit-Breaker Halt & Recovery Path
- **Halt / retire stale or failing tasks**: inspect active tasks with `ducoro-cli task list --space <space-id> --json`, pause affected recurring tasks with `ducoro-cli task disable <task-id> --space <space-id>`, and delete obsolete or cancelled one-shot tasks with `ducoro-cli task rm <task-id> --space <space-id>`.
- **Recover after root-cause fix**: once credentials are refreshed, facts are corrected, `check_media_specs.py` passes, and Gate 2 re-approval (if needed) is recorded, re-enable recurring tasks via `ducoro-cli task enable <task-id> --space <space-id>` (or create a fresh `--at` task for rescheduled releases) and verify recent executions via `ducoro-cli task history <task-id> --space <space-id> --json`.

## Multi-Space Relay Handoff

When separate Spaces handle monitoring, drafting, publishing, and analytics:
- **Shared root discovery (only when relaying across multiple Spaces)**: prefer the human's existing folder if one is already mounted; otherwise register a shared folder once per initiative as a global Local Folder (after human confirmation, never inside `~/.ducoro/local-folders/`). Every participating Space discovers its own `<space-work-root>` via `ducoro-cli space info <space-id> --json` and shared folders via `ducoro-cli space resources get <space-id> --json` / `ducoro-cli local-folder list --json`. Single-Space runs use the Space's own `files/` directly without creating a global Local Folder.
- **Cross-Space handoff**: notify the downstream Space via explicit Mail instead of relying on silent file polling:
  ```sh
  ducoro-cli space mail send <recipient> --subject "<subject>" --body "<body>"
  ```
- **Single-writer ownership** (prevents lost updates on mutable JSON files):
  - **Monitoring / Engagement / Analytics Space**: writes `inbox/*.md`, `engagement/inbox.json`, `analytics/snapshots.jsonl`, `analytics/retros/*.md`.
  - **Drafting Space**: exclusively owns `topics/topics.json`, `topics/briefs/*.md`, and `drafts/<id>/**` (including `meta.json`).
  - **Publishing Space**: exclusively owns `calendar.json` (slot creation, Gate 2 `approvalRef` + `approvedVariantHash`, status updates), `publish-log.jsonl`, and `engagement/action-log.jsonl`. Publishing state truth lives in `calendar.json` and `publish-log.jsonl`—Publishing never concurrently mutates `drafts/<id>/meta.json`.
- **Tamper & drift guard**: before publishing any `approved` slot, the Publishing Space recomputes the 16-char sha256 prefix of `variants/<platform>.md` and verifies it equals `slot.approvedVariantHash` (and `draft.status != "needs_update"`). On mismatch, halt, revert slot to `awaiting_approval` with a note, disable/remove the scheduled task, and request re-approval.
- Always run `validate_workspace.py` after mutating shared JSON files and `build_boards.py` after state transitions. Never overwrite append-only `.jsonl` logs—append new lines only.
