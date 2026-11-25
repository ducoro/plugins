#!/usr/bin/env python3
"""Exact Decimal P&L, budget tracking, duplicate-charge/price-hike anomaly detection, and cash runway calculation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import importlib.util
import json
from pathlib import Path
from statistics import median

SCRIPT_DIR = Path(__file__).resolve().parent
TWO_DP = Decimal('0.01')
ONE_DP = Decimal('0.1')
DEFAULT_COGS_CATS = {'cloud_infra', 'payment_fees', 'cogs', 'hosting', 'api_usage'}
DEFAULT_VARIABLE_OPEX_CATS = {'marketing', 'ads', 'contractors', 'events', 'travel'}


def _prev_month(ym: str) -> str:
    year, mon = int(ym[:4]), int(ym[5:7])
    return f'{year - 1}-12' if mon == 1 else f'{year:04d}-{mon - 1:02d}'


def _classify_row(row: dict) -> str:
    explicit = str(row.get('costClass') or '').strip().lower()
    if explicit in {'recurring_revenue', 'one_time_revenue', 'cogs', 'fixed_opex', 'variable_opex'}:
        return explicit
    cat = str(row.get('category') or '').strip().lower()
    if row.get('direction') == 'inflow':
        return 'one_time_revenue' if cat in {'one_time_revenue', 'grant', 'refund_received', 'consulting_one_time'} else 'recurring_revenue'
    if cat in DEFAULT_COGS_CATS:
        return 'cogs'
    if cat in DEFAULT_VARIABLE_OPEX_CATS:
        return 'variable_opex'
    return 'fixed_opex'


def _runway_months(cash: Decimal, burn: Decimal) -> str | None:
    if burn <= 0:
        return None
    return str((cash / burn).quantize(ONE_DP, rounding=ROUND_HALF_UP))


def _load_fx():
    spec = importlib.util.spec_from_file_location('bfo_fx', SCRIPT_DIR / 'fx_rates.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fx_rates = _load_fx()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _load_ledger(workspace: Path) -> list[dict]:
    p = workspace / 'ledger.jsonl'
    if not p.is_file():
        return []
    rows = []
    for ln in p.read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            if isinstance(obj, dict) and obj.get('txHash'):
                rows.append(obj)
        except json.JSONDecodeError:
            continue
    return rows


def analyze_workspace(
    workspace: Path,
    *,
    month: str | None = None,
    write_report: bool = True,
    scenario_extra_burn: str = '0',
) -> dict:
    workspace = workspace.expanduser().resolve()
    accounts = json.loads((workspace / 'accounts.json').read_text(encoding='utf-8'))
    budgets_doc = json.loads((workspace / 'budgets.json').read_text(encoding='utf-8'))
    fx_cache = json.loads((workspace / 'fx-cache.json').read_text(encoding='utf-8')) if (workspace / 'fx-cache.json').is_file() else {'snapshots': {}}

    base_ccy = str(accounts.get('baseCurrency', 'USD')).upper()
    thresholds = accounts.get('thresholds') or {}
    dup_window_h = Decimal(str(thresholds.get('duplicateWindowHours', 72)))
    hike_pct = Decimal(str(thresholds.get('vendorHikePct', '20')))
    budget_warn_pct = Decimal(str(thresholds.get('budgetWarnPct', '80')))
    min_runway_m = Decimal(str(thresholds.get('minRunwayMonths', '6')))
    flux_min_abs = Decimal(str(thresholds.get('fluxMinAbs', '100')))
    flux_min_pct = Decimal(str(thresholds.get('fluxMinPct', '15')))
    extra_burn_dec = Decimal(str(scenario_extra_burn or '0'))

    all_rows = _load_ledger(workspace)
    all_rows.sort(key=lambda r: (r.get('timestamp') or r.get('date') or '', r.get('txHash', '')))

    # Convert every row to base currency using exact Decimal
    enriched: list[dict] = []
    for r in all_rows:
        orig_amt = Decimal(str(r['amount']))
        base_amt, rate_used = fx_rates.convert_to_base(orig_amt, r['currency'], base_ccy, fx_cache, tx_date=r.get('date'))
        enriched.append({**r, 'costClass': _classify_row(r), 'baseAmount': str(base_amt), 'fxRateUsed': rate_used, '_baseDec': base_amt})

    target_month = month or (enriched[-1]['date'][:7] if enriched else utc_now()[:7])
    prior_month = _prev_month(target_month)
    month_rows = [r for r in enriched if str(r.get('date', '')).startswith(target_month)]
    prior_rows = [r for r in enriched if str(r.get('date', '')).startswith(prior_month)]

    inflow_total = Decimal('0.00')
    recurring_inflow = Decimal('0.00')
    one_time_inflow = Decimal('0.00')
    outflow_total = Decimal('0.00')
    cogs_total = Decimal('0.00')
    fixed_opex_total = Decimal('0.00')
    variable_opex_total = Decimal('0.00')
    spend_by_cat: dict[str, Decimal] = {}
    prior_spend_by_cat: dict[str, Decimal] = {}

    for r in prior_rows:
        if r['direction'] == 'outflow':
            cat = r.get('category') or 'uncategorized'
            prior_spend_by_cat[cat] = prior_spend_by_cat.get(cat, Decimal('0.00')) + r['_baseDec']

    for r in month_rows:
        amt = r['_baseDec']
        cls = r['costClass']
        if r['direction'] == 'inflow':
            inflow_total += amt
            if cls == 'one_time_revenue':
                one_time_inflow += amt
            else:
                recurring_inflow += amt
        else:
            outflow_total += amt
            if cls == 'cogs':
                cogs_total += amt
            elif cls == 'variable_opex':
                variable_opex_total += amt
            else:
                fixed_opex_total += amt
            cat = r.get('category') or 'uncategorized'
            spend_by_cat[cat] = spend_by_cat.get(cat, Decimal('0.00')) + amt

    gross_profit = (inflow_total - cogs_total).quantize(TWO_DP, rounding=ROUND_HALF_UP)
    gross_margin_pct: str | None = (
        str(((gross_profit / inflow_total) * Decimal('100')).quantize(ONE_DP, rounding=ROUND_HALF_UP))
        if inflow_total > 0
        else None
    )
    net_cash_flow = (inflow_total - outflow_total).quantize(TWO_DP, rounding=ROUND_HALF_UP)

    # Exact total cash balance in base currency
    total_cash = Decimal('0.00')
    for ccy, bal_str in (accounts.get('cashBalances') or {}).items():
        bal_dec = Decimal(str(bal_str))
        conv, _ = fx_rates.convert_to_base(bal_dec, ccy, base_ccy, fx_cache)
        total_cash += conv
    total_cash = total_cash.quantize(TWO_DP, rounding=ROUND_HALF_UP)

    monthly_net_burn = (outflow_total - inflow_total).quantize(TWO_DP, rounding=ROUND_HALF_UP)
    recurring_net_burn = (outflow_total - recurring_inflow).quantize(TWO_DP, rounding=ROUND_HALF_UP)
    downside_burn = (outflow_total - (recurring_inflow * Decimal('0.80'))).quantize(TWO_DP, rounding=ROUND_HALF_UP)
    runway_months = _runway_months(total_cash, monthly_net_burn)

    scenarios = {
        'base': {
            'monthlyNetBurn': str(monthly_net_burn if monthly_net_burn > 0 else Decimal('0.00')),
            'runwayMonths': runway_months,
        },
        'recurringOnly': {
            'monthlyNetBurn': str(recurring_net_burn if recurring_net_burn > 0 else Decimal('0.00')),
            'runwayMonths': _runway_months(total_cash, recurring_net_burn),
        },
        'downsideRev20': {
            'monthlyNetBurn': str(downside_burn if downside_burn > 0 else Decimal('0.00')),
            'runwayMonths': _runway_months(total_cash, downside_burn),
        },
    }
    if extra_burn_dec > 0:
        exp_burn = (recurring_net_burn + extra_burn_dec).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        scenarios['proposedExpansion'] = {
            'extraMonthlyBurn': str(extra_burn_dec.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'monthlyNetBurn': str(exp_burn if exp_burn > 0 else Decimal('0.00')),
            'runwayMonths': _runway_months(total_cash, exp_burn),
        }

    # Month-over-Month Flux (Variance) Analysis
    flux_rows = []
    for cat in sorted(set(spend_by_cat.keys()) | set(prior_spend_by_cat.keys())):
        curr = spend_by_cat.get(cat, Decimal('0.00')).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        prev = prior_spend_by_cat.get(cat, Decimal('0.00')).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        delta = (curr - prev).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        if prev > 0:
            pct = ((delta / prev) * Decimal('100')).quantize(ONE_DP, rounding=ROUND_HALF_UP)
            pct_str: str | None = str(pct)
            is_material = abs(delta) >= flux_min_abs and abs(pct) >= flux_min_pct
        else:
            pct_str = None
            is_material = abs(delta) >= flux_min_abs
        flux_rows.append({
            'category': cat,
            'priorMonth': prior_month,
            'priorSpend': str(prev),
            'currentSpend': str(curr),
            'delta': str(delta),
            'changePct': pct_str,
            'isMaterial': is_material,
        })
    flux_rows.sort(key=lambda x: abs(Decimal(x['delta'])), reverse=True)

    anomalies: list[dict] = []

    # 1. Duplicate charge detector (outflows with identical merchant + exact amount + currency within window)
    outflows = [r for r in enriched if r['direction'] == 'outflow']
    seen_outflows: dict[tuple[str, str, str], list[dict]] = {}
    for r in outflows:
        key = (r.get('merchant', '').strip().lower(), r['amount'], r['currency'].upper())
        prev_list = seen_outflows.get(key, [])
        ts = datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00'))
        for prev in prev_list:
            prev_ts = datetime.fromisoformat(prev['timestamp'].replace('Z', '+00:00'))
            delta_h = Decimal(str(abs((ts - prev_ts).total_seconds()))) / Decimal('3600')
            if delta_h <= dup_window_h:
                anomalies.append({
                    'alertId': f'dup-{r["txHash"]}',
                    'type': 'duplicate_charge',
                    'severity': 'high',
                    'merchant': r['merchant'],
                    'amount': r['amount'],
                    'currency': r['currency'],
                    'summary': f'Potential duplicate outflow to {r["merchant"]} ({r["amount"]} {r["currency"]}) within {delta_h.quantize(ONE_DP)}h.',
                    'evidence': [
                        {'txHash': prev['txHash'], 'sourceFile': prev.get('sourceFile', ''), 'sourceLine': prev.get('sourceLine')},
                        {'txHash': r['txHash'], 'sourceFile': r.get('sourceFile', ''), 'sourceLine': r.get('sourceLine')},
                    ],
                })
                break
        prev_list.append(r)
        seen_outflows[key] = prev_list

    # 2. Recurring vendor price hike detector (requires >= 2 historical charges prior to latest)
    by_merchant: dict[str, list[dict]] = {}
    for r in outflows:
        by_merchant.setdefault(r.get('merchant', '').strip().lower(), []).append(r)
    for mkey, items in sorted(by_merchant.items()):
        if len(items) < 3:
            continue
        hist_vals = [x['_baseDec'] for x in items[:-1]]
        latest = items[-1]
        med = Decimal(str(median(hist_vals)))
        if med > 0:
            pct_change = ((latest['_baseDec'] - med) / med * Decimal('100')).quantize(ONE_DP, rounding=ROUND_HALF_UP)
            if pct_change >= hike_pct:
                anomalies.append({
                    'alertId': f'hike-{latest["txHash"]}',
                    'type': 'vendor_price_hike',
                    'severity': 'medium',
                    'merchant': latest['merchant'],
                    'amount': latest['baseAmount'],
                    'currency': base_ccy,
                    'summary': f'{latest["merchant"]} charge ({latest["baseAmount"]} {base_ccy}) rose {pct_change}% above historical median ({med.quantize(TWO_DP)} {base_ccy}).',
                    'evidence': [{'txHash': latest['txHash'], 'sourceFile': latest.get('sourceFile', ''), 'sourceLine': latest.get('sourceLine')}],
                })

    # 3. Budget status & breaches
    budget_rows = []
    for cat, limit_str in sorted((budgets_doc.get('monthlyBudgets') or {}).items()):
        limit_dec = Decimal(str(limit_str)).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        spent_dec = spend_by_cat.get(cat, Decimal('0.00')).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        pct = ((spent_dec / limit_dec) * Decimal('100')).quantize(ONE_DP, rounding=ROUND_HALF_UP) if limit_dec > 0 else Decimal('0.0')
        status = 'ok'
        if pct >= Decimal('100'):
            status = 'exceeded'
            anomalies.append({
                'alertId': f'budget-exceeded-{target_month}-{cat}',
                'type': 'budget_exceeded',
                'severity': 'high',
                'merchant': cat,
                'amount': str(spent_dec),
                'currency': base_ccy,
                'summary': f'Category {cat} spent {spent_dec} {base_ccy} ({pct}% of {limit_dec} budget) in {target_month}.',
                'evidence': [],
            })
        elif pct >= budget_warn_pct:
            status = 'warning'
            anomalies.append({
                'alertId': f'budget-warn-{target_month}-{cat}',
                'type': 'budget_warning',
                'severity': 'medium',
                'merchant': cat,
                'amount': str(spent_dec),
                'currency': base_ccy,
                'summary': f'Category {cat} reached {pct}% of monthly budget ({spent_dec} / {limit_dec} {base_ccy}).',
                'evidence': [],
            })
        budget_rows.append({
            'category': cat,
            'budget': str(limit_dec),
            'spent': str(spent_dec),
            'remaining': str((limit_dec - spent_dec).quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'utilizationPct': str(pct),
            'status': status,
        })

    # 4. Low cash runway warning
    if runway_months is not None and Decimal(runway_months) < min_runway_m:
        anomalies.append({
            'alertId': f'runway-{target_month}',
            'type': 'low_runway',
            'severity': 'high',
            'merchant': 'Cash Runway',
            'amount': str(total_cash),
            'currency': base_ccy,
            'summary': f'Projected cash runway is {runway_months} months (< {min_runway_m} months threshold) at {monthly_net_burn} {base_ccy}/mo net burn.',
            'evidence': [],
        })

    report = {
        'schemaVersion': 'business-finance-report/1',
        'generatedAt': utc_now(),
        'month': target_month,
        'baseCurrency': base_ccy,
        'summary': {
            'inflowTotal': str(inflow_total.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'recurringInflow': str(recurring_inflow.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'oneTimeInflow': str(one_time_inflow.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'outflowTotal': str(outflow_total.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'cogsTotal': str(cogs_total.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'fixedOpexTotal': str(fixed_opex_total.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'variableOpexTotal': str(variable_opex_total.quantize(TWO_DP, rounding=ROUND_HALF_UP)),
            'grossProfit': str(gross_profit),
            'grossMarginPct': gross_margin_pct,
            'netCashFlow': str(net_cash_flow),
            'totalCashBalance': str(total_cash),
            'monthlyNetBurn': str(monthly_net_burn if monthly_net_burn > 0 else Decimal('0.00')),
            'recurringNetBurn': str(recurring_net_burn if recurring_net_burn > 0 else Decimal('0.00')),
            'runwayMonths': runway_months,
            'transactionCount': len(month_rows),
            'anomalyCount': len(anomalies),
            'highAnomalyCount': sum(1 for a in anomalies if a['severity'] == 'high'),
        },
        'scenarios': scenarios,
        'fluxAnalysis': flux_rows,
        'budgets': budget_rows,
        'spendByCategory': {k: str(v.quantize(TWO_DP, rounding=ROUND_HALF_UP)) for k, v in sorted(spend_by_cat.items())},
        'anomalies': anomalies,
        'transactions': [
            {k: v for k, v in r.items() if not k.startswith('_')}
            for r in reversed(month_rows)
        ][:200],
    }

    if write_report:
        (workspace / 'finance-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Run exact Decimal financial reconciliation, budgets, and anomaly detection.')
    parser.add_argument('workspace')
    parser.add_argument('--month', default=None, help='YYYY-MM target month (defaults to latest ledger month)')
    parser.add_argument('--scenario-extra-burn', default='0', help='Optional proposed extra monthly burn in base currency')
    parser.add_argument('--write-report', action='store_true')
    args = parser.parse_args()
    print(json.dumps(
        analyze_workspace(Path(args.workspace), month=args.month, write_report=args.write_report, scenario_extra_burn=args.scenario_extra_burn),
        indent=2,
        ensure_ascii=False,
    ))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
