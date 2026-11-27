# Managerial Accounting, Flux Analysis & Runway Diagnostics Methodology

Bookkeeping exists for compliance; **managerial accounting exists so the principal can make better operating decisions**. Beyond raw cash-in minus cash-out, use exact `Decimal` outputs from `scripts/anomaly_and_runway.py` to examine cost structure, variance drivers, and multi-scenario runway.

## 1. Cost & Revenue Structure (Configurable Managerial Classification)

Every ledger row resolves to one of five economic classes:

| Class | Default Examples | Why Principals Care |
|---|---|---|
| `recurring_revenue` | Subscriptions, retainers, repeat usage billing | Repeatable baseline funding ongoing operations |
| `one_time_revenue` | Setup fees, consulting spikes, grants, asset sales, fee refunds | Stripped out in `recurringOnly` runway so one large deposit never hides structural burn |
| `cogs` | Cloud/API compute, payment processing fees, direct fulfillment | Scales directly with revenue; defines **Gross Margin = (Revenue - COGS) / Revenue** |
| `fixed_opex` | Core SaaS seats, office/payroll commitments, insurance | Committed spend that persists even if revenue drops |
| `variable_opex` | Paid acquisition, discretionary contractors, events, travel | Primary lever to dial down under cash pressure |

### Customizing Classification for Non-SaaS Businesses

Built-in category defaults (`cloud_infra`, `payment_fees`, `cogs`, `hosting`, `api_usage` -> `cogs`; `marketing`, `ads`, `contractors`, `events`, `travel` -> `variable_opex`) are only starting defaults. Any business model (e-commerce, agency, manufacturing, marketplace) can override classification without editing code:
1. Per-row `costClass` in `ledger.jsonl` (highest precedence, or assigned via `category-rules.json` rule `costClass`).
2. `costClassMap` in `category-rules.json` (overrides `accounts.json`) or `accounts.json`—for example mapping `inventory`, `shipping`, `packaging`, or `subcontractors` to `cogs`, and `warehouse_rent` to `fixed_opex`.

## 2. Month-over-Month Flux (Variance) Analysis

Avoid flat statements like "expenses went up this month." For categories crossing materiality thresholds (`thresholds.fluxMinAbs`, default `100` in base currency, AND `thresholds.fluxMinPct`, default `15%`), separate the operational driver:

- **Price / Rate change**: Same vendor charged more per seat or unit (cross-check `vendor_price_hike` alerts).
- **Volume / Usage growth**: Scaling alongside revenue (verify whether Gross Margin holds steady).
- **New vendor / commitment**: Newly added recurring tool, contractor, or service (verify principal approval).
- **Timing / Annual prepay**: Annual renewal or irregular billing cycle landing in one month (distinguish from structural monthly burn).

## 3. Three-Scenario Cash Runway Stress Testing

A single headline runway figure can create false comfort. `scripts/anomaly_and_runway.py` computes deterministic `Decimal` scenarios on every run:

- **`base`**: Total cash balance divided by net monthly burn (`outflow - inflow`).
- **`recurringOnly`**: Strips out `one_time_revenue` to expose structural runway if windfalls do not repeat. Low-runway alerting checks **both** `base` and `recurringOnly` against `thresholds.minRunwayMonths`.
- **`downsideRev20`**: Assumes a 20% recurring revenue drop while costs remain sticky.
- **Optional `--scenario-extra-burn <amount>`**: Models the exact runway impact of a proposed hire or new monthly commitment before the principal approves it.

## 4. Optional Executive Diagnostic Lenses

Adapt reporting depth and presentation to the human's live question and the Bot's `PROFILE.md`. Choose whichever of these diagnostic lenses fit the current review:

- **Unit & Margin Health**: Gross Margin %, `cogs` vs `inflowTotal`, and `recurringNetBurn`.
- **Material Flux Drivers**: Top categories with `isMaterial: true` vs prior month and their underlying operational drivers.
- **Leakage & Controls**: Verified `duplicate_charge`, `vendor_price_hike`, and budget breaches (`>= budgetWarnPct` / `>= 100%`) traced to `sourceFile:sourceLine`.
- **Runway & Levers**: Structural runway under `recurringOnly`, `downsideRev20`, or `proposedExpansion`, paired with concrete cost or revenue options when below `minRunwayMonths`.
