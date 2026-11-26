# Market Intel

Continuous competitor, company, and sector intelligence plugin for Ducoro.

## What It Solves

- **Deterministic change detection**: Normalizes public web pages, feeds, release metadata, job boards, and filings into canonical snapshots and computes objective diffs (`scripts/snapshot_diff.py`). When nothing material changed, it honestly outputs `no_material_change` instead of padding weekly reports.
- **Grounded evidence gate**: Every reported intelligence claim must link to a real URL, observation timestamp, and excerpt present in the verified capture pool (`scripts/evidence_gate.py`).
- **Real zero-key data sources + Connectors first**: Checks Ducoro Core Connectors first, then pulls live public facts via `scripts/fetch_sources.py` (GitHub Releases, Apple App Store Lookup, npm, PyPI, RSS/Atom/Statuspage feeds, Greenhouse/Ashby/Lever public job boards, SEC EDGAR submissions, HN Algolia, and public web snapshots).
- **Interactive shadcn/ui Boards**: Projects verified changes and competitor comparisons into `radar-board` and `battlecard-board` via `scripts/build_boards.py`.

## Layout

- `PLUGIN.md` — Domain role contract and level-1 resource map.
- `playbooks/` — Operational loop, verified source adapters, and board/battlecard workflows.
- `references/workspace-schema.md` — Data file contracts (`watchlist.json`, `events.jsonl`, snapshots, battlecards).
- `scripts/` — Zero-dependency Python 3 stdlib scripts (`init_workspace.py`, `fetch_sources.py`, `snapshot_diff.py`, `evidence_gate.py`, `build_boards.py`).
- `assets/boards/` — Standalone + Ducoro Board SDK interactive dashboards (`radar-board`, `battlecard-board`).

## License

Apache License 2.0. See [LICENSE](LICENSE).
