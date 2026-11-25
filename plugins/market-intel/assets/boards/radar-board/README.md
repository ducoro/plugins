# Market Intel Radar Board

Displays verified, evidence-backed competitor and sector changes projected from `market-intel/events.jsonl`.

## Location IDs
- KPI block: `data-card="radar-kpis"` (`kpi-entities`, `kpi-sources`, `kpi-events`, `kpi-high`)
- Change rows: `data-card="event-<eventId>"`, `data-mark-item="event-<eventId>"`

## Agent Commands (`ducoro-cli board command`)
- `filterEntity` (`{ "entity": "<slug|all>" }`)
- `filterSeverity` (`{ "severity": "all|high|medium|low" }`)
- `focusEvent` (`{ "eventId": "<eventId>" }`)
- `resetFilters` (`{}`)

## Visible Controls & Boundaries
- **Stage Sweep** / **Discuss**: Enabled only when embedded and connected in a Ducoro Space; stages a draft in Composer without bypassing human confirmation.
- Read-only in standalone and `data-ducoro-render="shot"` modes; does not write directly to workspace files.
