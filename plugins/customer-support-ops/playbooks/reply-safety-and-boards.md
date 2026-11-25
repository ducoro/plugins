# Reply Safety Guard & Interactive Boards

## 1. Tamper-Proof Outbound Reply Workflow (`scripts/reply_guard.py`)

Every outbound customer reply passes through three deterministic stages:

1. **Stage draft**:
   ```sh
   python3 scripts/reply_guard.py <workspace> stage --ticket <ticket-id> --body-file <draft.txt>
   ```
   Computes a 16-char `sha256` `draftHash`, scans for secrets/tokens, local filesystem paths, unresolved `{{...}}` / `[TODO]` placeholders, and unauthorized refund/legal/SLA promises.
2. **Approve & pin hash** (after explicit human confirmation):
   ```sh
   python3 scripts/reply_guard.py <workspace> approve --draft-id <id> --approved-by "<human>"
   ```
   Pins `approvedBodyHash = draftHash`.
3. **Pre-send gate check & commit**:
   ```sh
   python3 scripts/reply_guard.py <workspace> check-send --draft-id <id>
   # After actual send via Connector or official portal:
   python3 scripts/reply_guard.py <workspace> record-sent --draft-id <id> --external-reply-id "<id>"
   ```
   If the draft body was edited by even a single character after approval, or if the same ticket already received an identical reply within the cooldown window, `check-send` fails closed with non-zero exit code.

## 2. Two Bundled shadcn/ui Boards

| Board | Purpose | Agent Commands |
|---|---|---|
| `triage-sla-board` | Live ticket queue, P0/security/refund escalations, SLA breaches, and pending reply drafts | `filterPriority`, `filterEscalated`, `focusTicket`, `resetFilters` |
| `root-cause-board` | Clustered product issues, 7d vs prior-7d spike ratios, and verbatim customer citations | `filterSpikes`, `focusIssue`, `resetFilters` |

Project via `scripts/build_boards.py <workspace> --board <name> --board-dir <space-work-root>/boards/<id>` (add `--overwrite-templates` on initial setup).
