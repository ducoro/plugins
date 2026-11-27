#!/usr/bin/env python3
"""Deterministic Decimal statement parsers (Stripe, Alipay, WeChat Pay, OFX/QFX, generic CSV, connector JSON) with txHash dedupe and fail-closed ledger I/O."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

TWO_DP = Decimal('0.01')
VALID_COST_CLASSES = frozenset({
    'recurring_revenue',
    'one_time_revenue',
    'cogs',
    'fixed_opex',
    'variable_opex',
})


class LedgerCorruptionError(ValueError):
    """Raised when ledger.jsonl contains a malformed or schema-invalid line."""

    def __init__(self, path: Path, line: int, reason: str):
        self.path = str(path)
        self.line = line
        self.reason = reason
        super().__init__(f'{self.path}:{self.line}: corrupted ledger line ({reason})')


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


def _resolve_tz(tz_name: str) -> tzinfo:
    raw = (tz_name or 'UTC').strip()
    if not raw or raw.upper() in ('UTC', 'Z'):
        return timezone.utc
    m_off = re.fullmatch(r'([+-])(\d{2}):?(\d{2})', raw)
    if m_off:
        sign = 1 if m_off.group(1) == '+' else -1
        hours, mins = int(m_off.group(2)), int(m_off.group(3))
        if hours > 23 or mins > 59:
            raise ValueError(f'Invalid timezone offset: {tz_name!r}')
        return timezone(sign * timedelta(hours=hours, minutes=mins))
    try:
        return ZoneInfo(raw)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f'Unknown timezone: {tz_name!r}') from exc


def _format_dt(dt: datetime) -> tuple[str, str]:
    dt_clean = dt.replace(microsecond=0)
    offset = dt_clean.utcoffset()
    if offset == timedelta(0):
        return dt_clean.strftime('%Y-%m-%d'), dt_clean.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    return dt_clean.strftime('%Y-%m-%d'), dt_clean.isoformat()


def clean_decimal(raw: str) -> Decimal:
    s = str(raw or '').strip()
    s = re.sub(r'[¥$€£,\s]', '', s)
    if not s:
        raise ValueError('Empty numeric amount')
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f'Invalid decimal amount: {raw!r}') from exc


def parse_timestamp(raw: str, *, tz_name: str = 'UTC') -> tuple[str, str]:
    s = str(raw or '').strip()
    if not s:
        raise ValueError('Empty timestamp')
    default_tz = _resolve_tz(tz_name)

    # OFX format: YYYYMMDDHHMMSS[.fff][[-+]H[:TZ]] or YYYYMMDD
    m_ofx = re.match(
        r'^(\d{4})(\d{2})(\d{2})(?:(\d{2})(\d{2})(\d{2}))?(?:\.\d+)?(?:\[([+-]?\d+(?:\.\d+)?)(?::[^\]]+)?\])?$',
        s,
    )
    if m_ofx and '-' not in s and '/' not in s:
        y, mo, d, hh, mm, ss, ofx_off = m_ofx.groups()
        if ofx_off is not None:
            tz = timezone(timedelta(hours=float(ofx_off)))
        else:
            tz = default_tz
        dt = datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0), tzinfo=tz)
        return _format_dt(dt)

    norm = s.replace('/', '-').replace('Z', '+00:00')
    candidates = [norm]
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', norm):
        candidates.append(f'{norm}T00:00:00')
    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=default_tz)
            else:
                dt = dt.astimezone(timezone.utc)
            return _format_dt(dt)
        except ValueError:
            continue
    raise ValueError(f'Unrecognized timestamp format: {raw!r}')


def make_tx_hash(source_format: str, external_id: str, date_str: str, direction: str, amount_str: str, currency: str, merchant: str) -> str:
    payload = {
        'fmt': source_format,
        'ext': external_id.strip(),
        'date': date_str,
        'dir': direction,
        'amt': amount_str,
        'ccy': currency.upper(),
        'merchant': merchant.strip().lower() if not external_id.strip() else '',
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def _match_category_rule(
    merchant: str,
    description: str,
    rules: list[dict],
    *,
    direction: str,
    fallback: str,
) -> tuple[str, str | None]:
    haystack = f'{merchant} {description}'.strip()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_dir = str(rule.get('direction') or '').strip().lower()
        if rule_dir and rule_dir not in {'any', '*'} and rule_dir != direction:
            continue
        pat = rule.get('pattern')
        cat = rule.get('category')
        if pat and cat and re.search(pat, haystack, re.I):
            raw_cls = str(rule.get('costClass') or '').strip().lower()
            cost_cls = raw_cls if raw_cls in VALID_COST_CLASSES else None
            return str(cat), cost_cls
    return fallback, None


def categorize_merchant(
    merchant: str,
    description: str,
    rules: list[dict],
    fallback: str = 'uncategorized',
    *,
    direction: str = 'outflow',
) -> str:
    cat, _ = _match_category_rule(merchant, description, rules, direction=direction, fallback=fallback)
    return cat


def _resolve_category_and_class(
    merchant: str,
    description: str,
    rules: list[dict],
    *,
    direction: str,
    explicit_category: str = '',
    explicit_cost_class: str = '',
) -> tuple[str, str | None]:
    fallback = 'revenue' if direction == 'inflow' else 'uncategorized'
    matched_cat, matched_cls = _match_category_rule(
        merchant,
        description,
        rules,
        direction=direction,
        fallback=fallback,
    )
    cat = explicit_category.strip() if explicit_category.strip() else matched_cat
    cls_norm = explicit_cost_class.strip().lower()
    if cls_norm:
        if cls_norm not in VALID_COST_CLASSES:
            raise ValueError(f'Invalid costClass {explicit_cost_class!r}; expected one of {sorted(VALID_COST_CLASSES)}')
        cost_cls: str | None = cls_norm
    else:
        cost_cls = matched_cls
    return cat, cost_cls


def _decode_bytes(raw: bytes) -> str:
    for enc in ('utf-8-sig', 'gb18030', 'gbk', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def _attach_cost_class(row: dict, cost_cls: str | None) -> dict:
    if cost_cls:
        row['costClass'] = cost_cls
    return row


def parse_stripe_csv(path: Path, rules: list[dict], *, tz_name: str = 'UTC') -> list[dict]:
    text = _decode_bytes(path.read_bytes())
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for line_no, r in enumerate(reader, start=2):
        lower = {(k or '').strip().lower(): (v or '').strip() for k, v in r.items()}
        ext_id = lower.get('id') or lower.get('balance transaction id') or ''
        ccy = (lower.get('currency') or 'USD').upper()
        date_s, ts_s = parse_timestamp(lower.get('created (utc)') or lower.get('created') or '', tz_name=tz_name)
        gross = clean_decimal(lower.get('amount') or '0')
        fee = clean_decimal(lower.get('fee') or '0')
        desc = lower.get('description') or lower.get('type') or 'Stripe transaction'
        merchant = lower.get('customer email') or lower.get('description') or 'Stripe'

        if gross != 0:
            direction = 'inflow' if gross > 0 else 'outflow'
            amt = abs(gross).quantize(TWO_DP, rounding=ROUND_HALF_UP)
            cat, cost_cls = _resolve_category_and_class(merchant, desc, rules, direction=direction)
            rows.append(_attach_cost_class({
                'txHash': make_tx_hash('stripe', ext_id, date_s, direction, str(amt), ccy, merchant),
                'externalId': ext_id,
                'date': date_s,
                'timestamp': ts_s,
                'direction': direction,
                'amount': str(amt),
                'currency': ccy,
                'merchant': merchant,
                'description': desc,
                'category': cat,
                'sourceFormat': 'stripe',
                'sourceFile': path.name,
                'sourceLine': line_no,
            }, cost_cls))
        if fee != 0:
            fee_dir = 'outflow' if fee > 0 else 'inflow'
            fee_amt = abs(fee).quantize(TWO_DP, rounding=ROUND_HALF_UP)
            fee_id = f'{ext_id}:fee' if ext_id else ''
            fee_desc = (
                f'Processing fee for {ext_id or desc}'
                if fee > 0
                else f'Processing fee refund for {ext_id or desc}'
            )
            fee_row = {
                'txHash': make_tx_hash('stripe', fee_id, date_s, fee_dir, str(fee_amt), ccy, 'Stripe Fee'),
                'externalId': fee_id,
                'date': date_s,
                'timestamp': ts_s,
                'direction': fee_dir,
                'amount': str(fee_amt),
                'currency': ccy,
                'merchant': 'Stripe Fee',
                'description': fee_desc,
                'category': 'payment_fees',
                'sourceFormat': 'stripe',
                'sourceFile': path.name,
                'sourceLine': line_no,
            }
            if fee < 0:
                fee_row['costClass'] = 'one_time_revenue'
            rows.append(fee_row)
    return rows


def _parse_cn_wallet_csv(path: Path, rules: list[dict], *, fmt: str, header_marker: str, tz_name: str = 'UTC') -> list[dict]:
    lines = _decode_bytes(path.read_bytes()).splitlines()
    header_idx = None
    for idx, ln in enumerate(lines):
        if header_marker in ln and '金额' in ln:
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError(f'Could not find {fmt} bill header row containing {header_marker!r}')

    reader = csv.DictReader(io.StringIO('\n'.join(lines[header_idx:])))
    rows: list[dict] = []
    for offset, r in enumerate(reader, start=1):
        line_no = header_idx + 1 + offset
        cleaned = {(k or '').strip(): (v or '').strip() for k, v in r.items()}
        io_flag = cleaned.get('收/支', '')
        if io_flag not in {'收入', '支出'}:
            continue
        status = cleaned.get('交易状态') or cleaned.get('当前状态') or ''
        if any(skip in status for skip in ('交易关闭', '已全额退款', '失败')):
            continue
        amt = abs(clean_decimal(cleaned.get('金额') or cleaned.get('金额(元)') or '0')).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        if amt == 0:
            continue
        direction = 'inflow' if io_flag == '收入' else 'outflow'
        date_s, ts_s = parse_timestamp(cleaned.get('交易时间') or '', tz_name=tz_name)
        merchant = cleaned.get('交易对方') or fmt
        desc = cleaned.get('商品说明') or cleaned.get('商品') or ''
        ext_id = cleaned.get('交易订单号') or cleaned.get('交易单号') or ''
        cat, cost_cls = _resolve_category_and_class(merchant, desc, rules, direction=direction)
        rows.append(_attach_cost_class({
            'txHash': make_tx_hash(fmt, ext_id, date_s, direction, str(amt), 'CNY', merchant),
            'externalId': ext_id,
            'date': date_s,
            'timestamp': ts_s,
            'direction': direction,
            'amount': str(amt),
            'currency': 'CNY',
            'merchant': merchant,
            'description': desc,
            'category': cat,
            'sourceFormat': fmt,
            'sourceFile': path.name,
            'sourceLine': line_no,
        }, cost_cls))
    return rows


def parse_ofx(path: Path, rules: list[dict], *, tz_name: str = 'UTC') -> list[dict]:
    text = _decode_bytes(path.read_bytes())
    cur_match = re.search(r'<CURDEF>\s*([A-Za-z]{3})', text, re.I)
    currency = cur_match.group(1).upper() if cur_match else 'USD'

    blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', text, re.S | re.I)
    if not blocks:
        # Fallback for unclosed SGML <STMTTRN> blocks
        parts = re.split(r'<STMTTRN>', text, flags=re.I)
        blocks = parts[1:]

    def tag_val(block: str, tag: str) -> str:
        m = re.search(rf'<{tag}>\s*([^<\r\n]+)', block, re.I)
        return m.group(1).strip() if m else ''

    rows: list[dict] = []
    for idx, blk in enumerate(blocks, start=1):
        amt_raw = tag_val(blk, 'TRNAMT')
        dt_raw = tag_val(blk, 'DTPOSTED')
        if not amt_raw or not dt_raw:
            continue
        dec = clean_decimal(amt_raw)
        if dec == 0:
            continue
        direction = 'inflow' if dec > 0 else 'outflow'
        amt = abs(dec).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        date_s, ts_s = parse_timestamp(dt_raw, tz_name=tz_name)
        ext_id = tag_val(blk, 'FITID')
        merchant = tag_val(blk, 'NAME') or tag_val(blk, 'MEMO') or 'Bank Entry'
        desc = tag_val(blk, 'MEMO') or merchant
        cat, cost_cls = _resolve_category_and_class(merchant, desc, rules, direction=direction)
        rows.append(_attach_cost_class({
            'txHash': make_tx_hash('ofx', ext_id, date_s, direction, str(amt), currency, merchant),
            'externalId': ext_id,
            'date': date_s,
            'timestamp': ts_s,
            'direction': direction,
            'amount': str(amt),
            'currency': currency,
            'merchant': merchant,
            'description': desc,
            'category': cat,
            'sourceFormat': 'ofx',
            'sourceFile': path.name,
            'sourceLine': idx,
        }, cost_cls))
    return rows


def parse_generic_csv(
    path: Path,
    rules: list[dict],
    *,
    default_currency: str = 'USD',
    mapping: dict | None = None,
    tz_name: str = 'UTC',
) -> list[dict]:
    text = _decode_bytes(path.read_bytes())
    reader = csv.DictReader(io.StringIO(text))
    m = mapping or {}
    rows: list[dict] = []
    for line_no, r in enumerate(reader, start=2):
        lower = {(k or '').strip().lower(): (v or '').strip() for k, v in r.items()}
        date_col = m.get('date', 'date').lower()
        amt_col = m.get('amount', 'amount').lower()
        ccy_col = m.get('currency', 'currency').lower()
        merch_col = m.get('merchant', 'merchant').lower()
        desc_col = m.get('description', 'description').lower()
        id_col = m.get('id', 'id').lower()
        cat_col = m.get('category', 'category').lower()
        cost_cls_col = m.get('costClass', 'costclass').lower()

        raw_amt = lower.get(amt_col)
        if not raw_amt:
            continue
        dec = clean_decimal(raw_amt)
        if dec == 0:
            continue
        direction = 'inflow' if dec > 0 else 'outflow'
        amt = abs(dec).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        date_s, ts_s = parse_timestamp(lower.get(date_col) or lower.get('timestamp') or '', tz_name=tz_name)
        ccy = (lower.get(ccy_col) or default_currency).upper()
        merchant = lower.get(merch_col) or lower.get('counterparty') or lower.get('name') or 'Unknown'
        desc = lower.get(desc_col) or lower.get('memo') or merchant
        ext_id = lower.get(id_col) or ''
        cat, cost_cls = _resolve_category_and_class(
            merchant,
            desc,
            rules,
            direction=direction,
            explicit_category=lower.get(cat_col) or '',
            explicit_cost_class=lower.get(cost_cls_col) or '',
        )
        rows.append(_attach_cost_class({
            'txHash': make_tx_hash('csv', ext_id, date_s, direction, str(amt), ccy, merchant),
            'externalId': ext_id,
            'date': date_s,
            'timestamp': ts_s,
            'direction': direction,
            'amount': str(amt),
            'currency': ccy,
            'merchant': merchant,
            'description': desc,
            'category': cat,
            'sourceFormat': 'csv',
            'sourceFile': path.name,
            'sourceLine': line_no,
        }, cost_cls))
    return rows


def parse_connector_json(
    path: Path,
    rules: list[dict],
    *,
    default_currency: str = 'USD',
    tz_name: str = 'UTC',
) -> list[dict]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'{path}: invalid connector JSON ({exc.msg})') from exc

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = None
        for key in ('transactions', 'items', 'data', 'records'):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break
        if items is None:
            raise ValueError(f'{path}: connector JSON object must contain a list under transactions/items/data/records')
    else:
        raise ValueError(f'{path}: connector JSON must be an array or object containing transaction records')

    rows: list[dict] = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f'{path}: record #{idx} must be a JSON object')
        raw_amt = item.get('amount')
        if raw_amt is None or str(raw_amt).strip() == '':
            raise ValueError(f'{path}: record #{idx} is missing amount')
        dec = clean_decimal(str(raw_amt))
        if dec == 0:
            continue

        raw_dir = str(item.get('direction') or '').strip().lower()
        if raw_dir in {'inflow', 'outflow'}:
            direction = raw_dir
        elif not raw_dir:
            direction = 'inflow' if dec > 0 else 'outflow'
        else:
            raise ValueError(f'{path}: record #{idx} has invalid direction {raw_dir!r}')

        amt = abs(dec).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        raw_ts = item.get('timestamp') or item.get('date') or item.get('createdAt') or item.get('created')
        if not raw_ts:
            raise ValueError(f'{path}: record #{idx} is missing date/timestamp')
        date_s, ts_s = parse_timestamp(str(raw_ts), tz_name=tz_name)
        ccy = str(item.get('currency') or default_currency).strip().upper()
        merchant = str(item.get('merchant') or item.get('counterparty') or item.get('name') or item.get('vendor') or 'Connector Entry').strip()
        desc = str(item.get('description') or item.get('memo') or merchant).strip()
        ext_id = str(item.get('externalId') or item.get('id') or item.get('transactionId') or '').strip()

        source_fmt = str(item.get('sourceFormat') or 'connector').strip() or 'connector'
        source_file = str(item.get('sourceFile') or path.name).strip() or path.name
        source_line = item.get('sourceLine') if isinstance(item.get('sourceLine'), int) else idx

        cat, cost_cls = _resolve_category_and_class(
            merchant,
            desc,
            rules,
            direction=direction,
            explicit_category=str(item.get('category') or ''),
            explicit_cost_class=str(item.get('costClass') or ''),
        )
        tx_hash = str(item.get('txHash') or '').strip() or make_tx_hash(
            source_fmt, ext_id, date_s, direction, str(amt), ccy, merchant
        )
        rows.append(_attach_cost_class({
            'txHash': tx_hash,
            'externalId': ext_id,
            'date': date_s,
            'timestamp': ts_s,
            'direction': direction,
            'amount': str(amt),
            'currency': ccy,
            'merchant': merchant,
            'description': desc,
            'category': cat,
            'sourceFormat': source_fmt,
            'sourceFile': source_file,
            'sourceLine': source_line,
        }, cost_cls))
    return rows


def load_existing_hashes(ledger_path: Path) -> set[str]:
    existing_hashes: set[str] = set()
    if not ledger_path.is_file():
        return existing_hashes
    for line_no, raw in enumerate(ledger_path.read_text(encoding='utf-8').splitlines(), start=1):
        ln = raw.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError as exc:
            raise LedgerCorruptionError(ledger_path, line_no, f'invalid JSON: {exc.msg}') from exc
        if not isinstance(obj, dict):
            raise LedgerCorruptionError(ledger_path, line_no, 'expected JSON object')
        tx_hash = obj.get('txHash')
        if not isinstance(tx_hash, str) or not tx_hash.strip():
            raise LedgerCorruptionError(ledger_path, line_no, 'missing non-empty txHash')
        existing_hashes.add(tx_hash)
    return existing_hashes


def parse_statement(
    statement_path: Path,
    rules: list[dict],
    *,
    fmt: str,
    default_currency: str = 'USD',
    mapping: dict | None = None,
    tz_name: str = 'UTC',
) -> list[dict]:
    statement_path = statement_path.expanduser().resolve()
    if fmt == 'stripe':
        return parse_stripe_csv(statement_path, rules, tz_name=tz_name)
    if fmt == 'alipay':
        return _parse_cn_wallet_csv(statement_path, rules, fmt='alipay', header_marker='交易时间', tz_name=tz_name)
    if fmt == 'wechat':
        return _parse_cn_wallet_csv(statement_path, rules, fmt='wechat', header_marker='交易时间', tz_name=tz_name)
    if fmt == 'ofx':
        return parse_ofx(statement_path, rules, tz_name=tz_name)
    if fmt == 'csv':
        return parse_generic_csv(statement_path, rules, default_currency=default_currency, mapping=mapping, tz_name=tz_name)
    if fmt == 'connector':
        return parse_connector_json(statement_path, rules, default_currency=default_currency, tz_name=tz_name)
    raise ValueError(f'Unsupported statement format: {fmt}')


def ingest_statement(
    workspace: Path,
    statement_path: Path,
    *,
    fmt: str,
    default_currency: str = 'USD',
    mapping: dict | None = None,
    tz_name: str = 'UTC',
    stage_out: Path | None = None,
) -> dict:
    data_dir = workspace.expanduser().resolve()
    statement_path = statement_path.expanduser().resolve()
    rules_path = data_dir / 'category-rules.json'
    rules = json.loads(rules_path.read_text(encoding='utf-8')).get('rules', []) if rules_path.is_file() else []

    parsed = parse_statement(
        statement_path,
        rules,
        fmt=fmt,
        default_currency=default_currency,
        mapping=mapping,
        tz_name=tz_name,
    )

    if stage_out is not None:
        out_path = stage_out.expanduser().resolve()
        _atomic_write_text(out_path, json.dumps({'transactions': parsed}, indent=2, ensure_ascii=False) + '\n')
        return {
            'format': fmt,
            'sourceFile': statement_path.name,
            'stagedFile': str(out_path),
            'parsedCount': len(parsed),
            'staged': True,
        }

    ledger_path = data_dir / 'ledger.jsonl'
    lock_path = data_dir / '.ledger.lock'
    with _exclusive_lock(lock_path):
        existing_hashes = load_existing_hashes(ledger_path)
        added = 0
        deduped = 0
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with ledger_path.open('a', encoding='utf-8') as fh:
            for row in parsed:
                if row['txHash'] in existing_hashes:
                    deduped += 1
                    continue
                fh.write(json.dumps(row, ensure_ascii=False) + '\n')
                existing_hashes.add(row['txHash'])
                added += 1
            fh.flush()
            os.fsync(fh.fileno())

    return {
        'format': fmt,
        'sourceFile': statement_path.name,
        'parsedCount': len(parsed),
        'addedCount': added,
        'dedupedCount': deduped,
        'totalLedgerCount': len(existing_hashes),
    }


def _emit_error(code: str, message: str, *, file_path: str | None = None, line: int | None = None) -> int:
    err: dict[str, object] = {'code': code, 'message': message}
    if file_path is not None:
        err['file'] = file_path
    if line is not None:
        err['line'] = line
    print(json.dumps({'ok': False, 'error': err}, indent=2, ensure_ascii=False), file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description='Ingest real bank/payment statements into exact Decimal ledger.jsonl.')
    parser.add_argument('data_dir', metavar='data-dir', help='Active finance data directory')
    parser.add_argument('--file', required=True, help='Path to raw statement or normalized connector JSON file')
    parser.add_argument('--format', required=True, choices=('stripe', 'alipay', 'wechat', 'ofx', 'csv', 'connector'))
    parser.add_argument('--default-currency', default='USD')
    parser.add_argument('--timezone', default='UTC', help='IANA timezone or offset (e.g. Asia/Shanghai, +08:00) for naive timestamps')
    parser.add_argument('--mapping', default=None, help='Optional JSON column mapping file for generic csv')
    parser.add_argument('--stage-out', default=None, help='Parse and write staged connector JSON to an isolated file without mutating ledger.jsonl')
    args = parser.parse_args()

    try:
        mapping = json.loads(Path(args.mapping).expanduser().resolve().read_text(encoding='utf-8')) if args.mapping else None
        result = ingest_statement(
            Path(args.data_dir),
            Path(args.file),
            fmt=args.format,
            default_currency=args.default_currency,
            mapping=mapping,
            tz_name=args.timezone,
            stage_out=Path(args.stage_out) if args.stage_out else None,
        )
    except LedgerCorruptionError as exc:
        return _emit_error('CORRUPTED_LEDGER_LINE', str(exc), file_path=exc.path, line=exc.line)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _emit_error('INGEST_ERROR', str(exc))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
