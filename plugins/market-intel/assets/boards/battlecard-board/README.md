# Competitor Battlecards Board

Displays structured entity comparison cards projected from `market-intel/battlecards/*.json` and `events.jsonl`.

## Location IDs
- Coverage KPIs: `data-card="bc-kpis"` (`kpi-tracked`, `kpi-covered`)
- Entity cards: `data-card="entity-<slug>"`, `data-mark-item="entity-<slug>"`

## Agent Commands (`ducoro-cli board command`)
- `filterCategory` (`{ "category": "<category|all>" }`)
- `focusEntity` (`{ "slug": "<entity-slug>" }`)
- `resetFilters` (`{}`)

## Visible Controls & Boundaries
- **Refresh Battlecards** / **Update Card**: Enabled only in embedded, connected Ducoro Space sessions; stages Composer drafts and never mutates files directly.
