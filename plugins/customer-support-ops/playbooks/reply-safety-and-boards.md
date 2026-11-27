# Reply Safety Guard, Isolated Review & Interactive Boards

## 1. Unified Approval Policy & Tamper-Proof Outbound Flow (`scripts/reply_guard.py`)

Authority precedence is strictly `Human live instructions > Bot PROFILE.md > local sla-policy.json > plugin defaults`.

- **High-risk or commitment-bearing replies** (tickets with `requiresHumanApproval: true`, or any draft containing refund/SLA/ship-date/legal-liability commitments): `stage` sets status to `awaiting_approval`; explicit human confirmation and hash pinning via `approve` are mandatory before sending.
- **Routine P2/P3 replies** (no risk flags, no SLA breach, clean safety scan, and `requireApprovalForRoutine` is `false`): `stage` sets status to `ready_to_send`; `check-send` still enforces leak/placeholder blocking, duplicate-hash protection, and cooldown rules.

Every outbound reply passes through four deterministic checkpoints:

1. **Stage draft**:
   ```sh
   python3 scripts/reply_guard.py <data-dir> stage --ticket <ticket-id> --body-file <draft.txt>
   ```
   Computes a 16-char `sha256` `draftHash` and scans for secrets/tokens, local filesystem paths, unresolved `{{...}}` / `[TODO]` placeholders, and unauthorized commitments.
2. **Independent read-only review (mandatory before human sign-off on high-risk replies)**:
   Before routing a P0, security/privacy, billing/refund, legal, or commitment-bearing draft to the human, dispatch an isolated read-only reviewer job (with zero write permissions to the draft file) so author bias cannot hide defects:
   ```sh
   ducoro-cli space participant list <space-id> --json
   ducoro-cli job dispatch --space <space-id> --agent <reviewer-agent-id> \
     --name "review-reply-<ticket-id>" \
     "Read-only audit of draft <draft-id> against ticket <ticket-id> in <data-dir>. Do NOT edit files. Check three orthogonal dimensions and report concrete defects only: (1) Factual grounding—every symptom, status, or workaround matches raw ticket/log evidence with zero invented root causes; (2) Implicit commitments or legal liability—flag any unapproved refund, credit, ETA, SLA guarantee, or admission of fault; (3) Customer question coverage—flag any direct question in the customer's latest message left unanswered or unacknowledged."
   ducoro-cli job status <job-id> --json
   ducoro-cli job log <job-id>
   ```
   Resolve every concrete finding and re-stage before requesting human confirmation.
3. **Approve & pin hash** (after explicit human confirmation via Inbox/Composer):
   ```sh
   python3 scripts/reply_guard.py <data-dir> approve --draft-id <id> --approved-by "<human>"
   ```
   Pins `approvedBodyHash = draftHash` and `approvedAt`.
4. **Pre-send gate check & commit**:
   ```sh
   python3 scripts/reply_guard.py <data-dir> check-send --draft-id <id>
   # After actual delivery via Connector or official portal:
   python3 scripts/reply_guard.py <data-dir> record-sent --draft-id <id> --external-reply-id "<id>"
   ```
   - `record-sent` writes **only** `outbound-queue.json` and appends to `reply-log.jsonl` (never touches `tickets/tickets.json`, preserving single-writer ownership).
   - All validation/runtime errors emit structured JSON to `stderr` with a non-zero exit code (`check-send` prints structured JSON to `stdout` and exits with code `2` when blocked).

## 2. Cooldown Unlocking & Failure Recovery

### Legitimate Follow-Ups Within Cooldown
- **Exact duplicate body hash (`duplicate_reply_hash`)**: Always blocked permanently for the same ticket—no flag can bypass it.
- **New follow-up content within `replyCooldownHours`**: Automatically unlocked when either:
  1. The customer sent a newer inbound message (`ticket.lastInboundAt > lastSentAt`), OR
  2. A human explicitly approved this new follow-up draft after the previous send (`draft.approvedAt > lastSentAt` with matching `approvedBodyHash`).
  - Pass `--force-followup` on `check-send` / `record-sent` only if a human explicitly approved the follow-up draft earlier and wants to override the time window (it never bypasses `duplicate_reply_hash` or unapproved spam).

### Send Timeout / Disconnect Reconciliation
If an external Connector or helpdesk API call times out or disconnects after sending:
1. **Never blindly retry** and **never blindly call `record-sent`**.
2. Read back the upstream ticket thread first to verify whether the message actually landed.
3. If the message landed upstream, capture its real `externalReplyId` and call `record-sent` to reconcile local state.
4. If confirmed absent upstream, re-run `check-send` before deciding whether to transmit once.

### Recovery from `tampered_after_approval`
When `check-send` detects any post-approval edit (`liveHash != approvedBodyHash`), it fails closed, clears `approvedBy`/`approvedAt`/`approvedBodyHash`, and resets status to `awaiting_approval`. To recover:
1. Show the human the exact diff between the previously approved text and the modified draft.
2. Fix or re-stage the intended text (`stage`), re-run isolated review if risk semantics changed, and obtain fresh explicit human confirmation.
3. Run `approve` again to pin the new `approvedBodyHash`, then re-run `check-send`.

## 3. Two Bundled shadcn/ui Boards

Boards live inside the displaying Space's own `boards/<board-id>/` directory—never inside `<data-dir>`:

```sh
ducoro-cli board list --space <space-id> --json
ducoro-cli board new --space <space-id> --title "Support Triage & SLA Queue" --json
ducoro-cli board link --space <space-id> --board boards/<board-id> --json
python3 scripts/build_boards.py <data-dir> --board triage-sla-board --board-dir <space-work-root>/boards/<board-id> --overwrite-templates
ducoro-cli render check --file <space-work-root>/boards/<board-id>/index.html --json
ducoro-cli render shot --file <space-work-root>/boards/<board-id>/index.html --out <space-work-root>/files/board-preview.png --json
```

| Board | Purpose | Agent Commands (`ducoro-cli board command`) |
|---|---|---|
| `triage-sla-board` | Live ticket queue, monotonic escalations, SLA breaches, derived replied status, and latest staged draft status | `filterPriority`, `filterEscalated`, `focusTicket`, `resetFilters` |
| `root-cause-board` | Clustered product issues, real 7d vs prior-7d `clusterMetrics` trends, anti-false-consensus unique customers, and verbatim citations | `filterSpikes`, `focusIssue`, `resetFilters` |
