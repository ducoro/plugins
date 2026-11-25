#!/usr/bin/env python3
"""Official keyless ECB FX rate fetcher (via Frankfurter) with local Decimal caching."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import urllib.parse
import urllib.request

DEFAULT_UA = 'DucoroFinanceOps/1.0 (+https://ducoro.ai)'
TWO_DP = Decimal('0.01')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def fetch_ecb_rates(
    base: str,
    *,
    symbols: list[str] | None = None,
    date_str: str = 'latest',
    api_base: str = 'https://api.frankfurter.dev/v1',
    timeout: int = 12,
) -> dict:
    base_ccy = base.strip().upper()
    endpoint = f'{api_base.rstrip("/")}/{urllib.parse.quote(date_str)}?base={urllib.parse.quote(base_ccy)}'
    if symbols:
        clean_syms = sorted({s.strip().upper() for s in symbols if s.strip() and s.strip().upper() != base_ccy})
        if clean_syms:
            endpoint += f'&symbols={urllib.parse.quote(",".join(clean_syms))}'
    req = urllib.request.Request(endpoint, headers={'User-Agent': DEFAULT_UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read(500_000).decode('utf-8'))
    rates = {k.upper(): str(v) for k, v in (data.get('rates') or {}).items()}
    rates[base_ccy] = '1'
    return {
        'base': base_ccy,
        'date': data.get('date', date_str),
        'source': 'ecb-frankfurter',
        'fetchedAt': utc_now(),
        'rates': rates,
    }


def update_fx_cache(
    workspace: Path,
    base: str,
    *,
    symbols: list[str] | None = None,
    date_str: str = 'latest',
    api_base: str = 'https://api.frankfurter.dev/v1',
) -> dict:
    workspace = workspace.expanduser().resolve()
    snap = fetch_ecb_rates(base, symbols=symbols, date_str=date_str, api_base=api_base)
    cache_path = workspace / 'fx-cache.json'
    cache = (
        json.loads(cache_path.read_text(encoding='utf-8'))
        if cache_path.is_file()
        else {'schemaVersion': 'business-finance-fx/1', 'snapshots': {}}
    )
    snaps = cache.setdefault('snapshots', {})
    key = f'{snap["base"]}:{snap["date"]}'
    snaps[key] = snap
    snaps[f'{snap["base"]}:latest'] = snap
    cache['updatedAt'] = utc_now()
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return snap


def convert_to_base(
    amount: Decimal,
    from_currency: str,
    base_currency: str,
    fx_cache: dict,
    *,
    tx_date: str | None = None,
) -> tuple[Decimal, str]:
    """Convert exact Decimal amount into base_currency using cached ECB rates (1 base = R foreign)."""
    src = from_currency.strip().upper()
    dst = base_currency.strip().upper()
    if src == dst:
        return amount.quantize(TWO_DP, rounding=ROUND_HALF_UP), '1'

    snaps = fx_cache.get('snapshots') or {}
    candidates = []
    if tx_date:
        candidates.append(f'{dst}:{tx_date}')
    candidates.append(f'{dst}:latest')
    for k in sorted(snaps.keys(), reverse=True):
        if k.startswith(f'{dst}:') and k not in candidates:
            candidates.append(k)

    for key in candidates:
        snap = snaps.get(key)
        if not isinstance(snap, dict):
            continue
        rates = snap.get('rates') or {}
        if src in rates:
            rate = Decimal(str(rates[src]))
            if rate <= 0:
                raise ValueError(f'Non-positive FX rate for {src}: {rate}')
            # Frankfurter base=dst means 1 dst = rate src -> amount_in_dst = amount_in_src / rate
            converted = (amount / rate).quantize(TWO_DP, rounding=ROUND_HALF_UP)
            return converted, str(rate)

    raise ValueError(f'Missing FX rate to convert {src} -> {dst} (date={tx_date}). Run fx_rates.py first.')


def main() -> int:
    parser = argparse.ArgumentParser(description='Fetch and cache official ECB FX rates.')
    parser.add_argument('workspace')
    parser.add_argument('--base', default='USD')
    parser.add_argument('--symbols', default='CNY,EUR,GBP,JPY,HKD,SGD')
    parser.add_argument('--date', default='latest', help='latest or YYYY-MM-DD')
    parser.add_argument('--api-base', default='https://api.frankfurter.dev/v1')
    args = parser.parse_args()
    syms = [s.strip() for s in args.symbols.split(',') if s.strip()]
    snap = update_fx_cache(Path(args.workspace), args.base, symbols=syms, date_str=args.date, api_base=args.api_base)
    print(json.dumps(snap, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
