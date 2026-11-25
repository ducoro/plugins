# Managerial Accounting, Flux Analysis & Runway Diagnostics Methodology

Bookkeeping exists for compliance; **managerial accounting exists so the principal can make better operating decisions**. Never stop at a raw cash-in minus cash-out ledger—translate exact `Decimal` numbers into four diagnostic lenses.

## 1. Cost & Revenue Structure (Managerial Classification)

Classify every ledger row by economic behavior, not only tax category:

| Class | Examples | Why Principals Care |
|---|---|---|
| `recurring_revenue` | Subscriptions, retainers, repeat usage billing | True repeatable baseline funding operations |
| `one_time_revenue` | Setup fees, consulting spikes, grants, asset sales | **Must be stripped out** when measuring real monthly burn—one large deposit can hide an unsustainable burn rate |
| `cogs` | Cloud/API compute, payment processing fees, direct fulfillment | Scales directly with revenue; defines **Gross Margin = (Revenue − COGS) / Revenue** |
| `fixed_opex` | Core SaaS seats, office/payroll commitments, insurance | Must be paid even if revenue drops to zero |
| `variable_opex` | Paid acquisition, discretionary contractors, events | First lever to dial down under cash pressure |

## 2. Month-over-Month Flux (Variance) Analysis

Never report "expenses went up this month." For every category that crosses the materiality threshold (`|delta| >= 100` in base currency AND `|changePct| >= 15%`), decompose the variance into one of four operational drivers:

1. **Price / Rate change**: Same vendor charged more per seat or unit (cross-check `vendor_price_hike` alerts).
2. **Volume / Usage growth**: Legitimate scaling with revenue (healthy only if Gross Margin holds steady).
3. **New vendor / commitment**: Newly added recurring tool or contractor (verify principal approval).
4. **Timing / Annual prepay**: Annual renewal hit a single month (explain cleanly so it is not confused with structural monthly burn).

## 3. Three-Scenario Cash Runway Stress Testing

A single headline runway figure creates false comfort. Compute three deterministic `Decimal` scenarios every close via `scripts/anomaly_and_runway.py`:

- **`base`**: Current total cash balance divided by net monthly burn (`outflow - inflow`).
- **`recurringOnly`**: Strips out `one_time_revenue` to expose true structural runway if no windfall repeats.
- **`downsideRev20`**: Assumes a 20% revenue shock while fixed costs stay sticky.
- **Optional `--scenario-extra-burn <amount>`**: Exact runway impact of a proposed hire or new monthly spend before the principal signs off.

## 4. One-Page Executive Finance Brief

Every weekly or monthly finance update must answer four decision questions in order:
1. **Unit & Margin Health**: What are Gross Margin % and Recurring Net Burn?
2. **Material Flux Drivers**: Which 2–3 categories moved most vs prior month, and why?
3. **Leakage & Controls**: Any duplicate charges, unexpected vendor hikes, or budget breaches (>=80% / >=100%)?
4. **Runway & Options**: Under `recurringOnly` and `downsideRev20`, do we have enough runway for the next milestone, and what concrete lever is recommended?
