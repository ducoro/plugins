# Root-Cause & Pain-Point Spikes Board

Displays clustered customer issues, 7-day spike ratios, and verbatim ticket citations projected from `customer-support-ops`.

## Location IDs
- Summary KPIs: `data-card="rc-kpis"` (`kpi-clusters`, `kpi-spikes`, `kpi-linked`)
- Cluster cards: `data-card="issue-<rootCauseId>"`, `data-mark-item="issue-<rootCauseId>"`

## Agent Commands (`ducoro-cli board command`)
- `filterSpikes` (`{ "spikesOnly": true|false }`)
- `focusIssue` (`{ "rootCauseId": "<id>" }`)
- `resetFilters` (`{}`)
