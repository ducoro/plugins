# Account Matrix & Publish Ledger Board

## What This Board Is
Tracks connected account authorization health (`accounts.json`, env var names only) and the append-only verified publish log (`publish-log.jsonl`).

## How to Add or Update Content
Update `accounts.json` or append verified entries to `publish-log.jsonl` in the active data directory, then run:
```sh
python3 scripts/build_boards.py <data-dir> --board publish-ledger-board --board-dir <this-board-dir>
```
Content identity conventions:
- Sections: `data-card="accounts-matrix"` and `data-card="publish-ledger"`.
- Items: `data-mark-item="acct-<accountId>"` and `data-mark-item="pub-<publishId>"`.
- Export frame for `ducoro-cli render check` / `render shot`: `[data-export-frame="ledger-summary"]`.

## Declared View Commands
- `filterPlatform` (`platform`): `ducoro-cli board command filterPlatform --space <space-id> --board <board> --arg platform=youtube`
- `onlyFailed` (`enabled`: `"true"` | `"false"`): `ducoro-cli board command onlyFailed --space <space-id> --board <board> --arg enabled=true`
- `focusRecord` (`pubId`): `ducoro-cli board command focusRecord --space <space-id> --board <board> --arg pubId=pub-001`

## Runtime Ownership
- `runtime/board-sdk-bridge.js`, `runtime/board-ui.css`, and `assets/data.json`.

## Human Controls
- **Platform / Failed Only** filters persist via `ducoro.storage`.
- **Draft Re-Auth Check** and **Draft Failure Triage**: stage Composer prompts (`ducoro.composer.draft`) for human review before sending.

## Excluded Behavior
- Never renders or stores raw API tokens, cookies, or passwords.
