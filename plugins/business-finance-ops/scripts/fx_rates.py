#!/usr/bin/env python3
"""Official keyless ECB FX rate fetcher (via Frankfurter) with manual non-ECB rate overrides and locked atomic Decimal caching."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.parse
import urllib.request

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

DEFAULT_UA = 'DucoroFinanceOps/1.0 (+https://ducoro.ai)'
TWO_DP = Decimal('0.01')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


@contextmanager
def _exclusive_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+', encoding='utf-8') as lock_fh:
        if fcntl is not None:
            fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _read_cache(cache_path: Path) -> dict:
    if not cache_path.is_file():
        return {'schemaVersion': 'business-finance-fx/1', 'snapshots': {}}
    try:
        data = json.loads(cache_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'{cache_path}: corrupted fx-cache.json ({exc.msg})') from exc
    if not isinstance(data, dict):
        raise ValueError(f'{cache_path}: expected JSON object in fx-cache.json')
    data.setdefault('schemaVersion', 'business-finance-fx/1')
    data.setdefault('snapshots', {})
    return data


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


def _merge_snapshot(existing: dict | None, incoming: dict) -> dict:
    merged_rates = dict((existing or {}).get('rates') or {})
    merged_rates.update(incoming.get('rates') or {})
    return {
        **incoming,
        'rates': merged_rates,
    }


def update_fx_cache(
    workspace: Path,
    base: str,
    *,
    symbols: list[str] | None = None,
    date_str: str = 'latest',
    api_base: str = 'https://api.frankfurter.dev/v1',
) -> dict:
    data_dir = workspace.expanduser().resolve()
    snap = fetch_ecb_rates(base, symbols=symbols, date_str=date_str, api_base=api_base)
    cache_path = data_dir / 'fx-cache.json'
    lock_path = data_dir / '.fx-cache.lock'
    with _exclusive_lock(lock_path):
        cache = _read_cache(cache_path)
        snaps = cache.setdefault('snapshots', {})
        key = f'{snap["base"]}:{snap["date"]}'
        snaps[key] = _merge_snapshot(snaps.get(key), snap)
        latest_key = f'{snap["base"]}:latest'
        snaps[latest_key] = _merge_snapshot(snaps.get(latest_key), snap)
        cache['updatedAt'] = utc_now()
        _atomic_write_text(cache_path, json.dumps(cache, indent=2, ensure_ascii=False) + '\n')
    return snaps[key]


def set_manual_rates(
    workspace: Path,
    base: str,
    rates_map: dict[str, str],
    *,
    date_str: str = 'latest',
) -> dict:
    """Record manual FX rates (1 base = R foreign) for currencies not covered by ECB."""
    data_dir = workspace.expanduser().resolve()
    base_ccy = base.strip().upper()
    if not re.fullmatch(r'[A-Z]{3}', base_ccy):
        raise ValueError(f'Invalid base currency code: {base!r}')
    if not rates_map:
        raise ValueError('At least one CCY=RATE pair is required')

    clean_rates: dict[str, str] = {base_ccy: '1'}
    for raw_ccy, raw_val in rates_map.items():
        ccy = raw_ccy.strip().upper()
        if not re.fullmatch(r'[A-Z]{3}', ccy):
            raise ValueError(f'Invalid currency code: {raw_ccy!r}')
        try:
            dec = Decimal(str(raw_val).strip())
        except InvalidOperation as exc:
            raise ValueError(f'Invalid FX rate for {ccy}: {raw_val!r}') from exc
        if dec <= 0:
            raise ValueError(f'FX rate for {ccy} must be positive: {raw_val!r}')
        clean_rates[ccy] = str(dec)

    effective_date = date_str.strip() if date_str and date_str.strip() != 'latest' else utc_now()[:10]
    incoming = {
        'base': base_ccy,
        'date': effective_date,
        'source': 'manual',
        'fetchedAt': utc_now(),
        'rates': clean_rates,
    }
    cache_path = data_dir / 'fx-cache.json'
    lock_path = data_dir / '.fx-cache.lock'
    with _exclusive_lock(lock_path):
        cache = _read_cache(cache_path)
        snaps = cache.setdefault('snapshots', {})
        key = f'{base_ccy}:{effective_date}'
        snaps[key] = _merge_snapshot(snaps.get(key), incoming)
        latest_key = f'{base_ccy}:latest'
        snaps[latest_key] = _merge_snapshot(snaps.get(latest_key), incoming)
        cache['updatedAt'] = utc_now()
        _atomic_write_text(cache_path, json.dumps(cache, indent=2, ensure_ascii=False) + '\n')
    return snaps[key]


def convert_to_base(
    amount: Decimal,
    from_currency: str,
    base_currency: str,
    fx_cache: dict,
    *,
    tx_date: str | None = None,
) -> tuple[Decimal, str]:
    """Convert exact Decimal amount into base_currency using cached ECB/manual rates (1 base = R foreign)."""
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
            # base=dst means 1 dst = rate src -> amount_in_dst = amount_in_src / rate
            converted = (amount / rate).quantize(TWO_DP, rounding=ROUND_HALF_UP)
            return converted, str(rate)

    raise ValueError(f'Missing FX rate to convert {src} -> {dst} (date={tx_date}). Run fx_rates.py first.')


def _parse_set_rates(entries: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in entries:
        for pair in entry.split(','):
            pair = pair.strip()
            if not pair:
                continue
            if '=' not in pair:
                raise ValueError(f'Expected CCY=RATE format for --set-rate, got {pair!r}')
            k, v = pair.split('=', 1)
            out[k.strip().upper()] = v.strip()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Fetch ECB FX rates or record manual non-ECB FX rates into fx-cache.json.')
    parser.add_argument('data_dir', metavar='data-dir', help='Active finance data directory')
    parser.add_argument('--base', default='USD')
    parser.add_argument('--symbols', default='CNY,EUR,GBP,JPY,HKD,SGD')
    parser.add_argument('--date', default='latest', help='latest or YYYY-MM-DD')
    parser.add_argument('--api-base', default='https://api.frankfurter.dev/v1')
    parser.add_argument(
        '--set-rate',
        action='append',
        default=[],
        help='Manually record non-ECB rate as CCY=RATE (1 base = RATE foreign); repeatable or comma-separated',
    )
    args = parser.parse_args()

    try:
        if args.set_rate:
            rates_map = _parse_set_rates(args.set_rate)
            snap = set_manual_rates(Path(args.data_dir), args.base, rates_map, date_str=args.date)
        else:
            syms = [s.strip() for s in args.symbols.split(',') if s.strip()]
            snap = update_fx_cache(Path(args.data_dir), args.base, symbols=syms, date_str=args.date, api_base=args.api_base)
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': {'code': 'FX_ERROR', 'message': str(exc)}}, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(snap, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
