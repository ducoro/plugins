#!/usr/bin/env python3
"""Deterministic Decimal statement parsers (Stripe, Alipay, WeChat Pay, OFX/QFX, generic CSV) with txHash dedupe."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
import re

TWO_DP = Decimal('0.01')


def clean_decimal(raw: str) -> Decimal:
    s = str(raw or '').strip()
    s = re.sub(r'[¥$€£,\s]', '', s)
    if not s:
        raise ValueError('Empty numeric amount')
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f'Invalid decimal amount: {raw!r}') from exc


def parse_timestamp(raw: str) -> tuple[str, str]:
    s = str(raw or '').strip()
    # OFX format: YYYYMMDDHHMMSS or YYYYMMDD
    m_ofx = re.match(r'^(\d{4})(\d{2})(\d{2})(?:(\d{2})(\d{2})(\d{2}))?', s)
    if m_ofx and '-' not in s and '/' not in s:
        y, mo, d, hh, mm, ss = m_ofx.groups()
        dt = datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0), tzinfo=timezone.utc)
        return dt.strftime('%Y-%m-%d'), dt.isoformat().replace('+00:00', 'Z')

    norm = s.replace('/', '-').replace('Z', '+00:00')
    for candidate in (norm, f'{norm}T00:00:00+00:00' if len(norm) == 10 else norm):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt_utc = dt.astimezone(timezone.utc).replace(microsecond=0)
            return dt_utc.strftime('%Y-%m-%d'), dt_utc.isoformat().replace('+00:00', 'Z')
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


def categorize_merchant(merchant: str, description: str, rules: list[dict], fallback: str = 'uncategorized') -> str:
    haystack = f'{merchant} {description}'.strip()
    for rule in rules:
        pat = rule.get('pattern')
        cat = rule.get('category')
        if pat and cat and re.search(pat, haystack, re.I):
            return str(cat)
    return fallback


def _decode_bytes(raw: bytes) -> str:
    for enc in ('utf-8-sig', 'gb18030', 'gbk', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def parse_stripe_csv(path: Path, rules: list[dict]) -> list[dict]:
    text = _decode_bytes(path.read_bytes())
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    for line_no, r in enumerate(reader, start=2):
        lower = {(k or '').strip().lower(): (v or '').strip() for k, v in r.items()}
        ext_id = lower.get('id') or lower.get('balance transaction id') or ''
        ccy = (lower.get('currency') or 'USD').upper()
        date_s, ts_s = parse_timestamp(lower.get('created (utc)') or lower.get('created') or '')
        gross = clean_decimal(lower.get('amount') or '0')
        fee = clean_decimal(lower.get('fee') or '0')
        desc = lower.get('description') or lower.get('type') or 'Stripe transaction'
        merchant = lower.get('customer email') or lower.get('description') or 'Stripe'

        if gross != 0:
            direction = 'inflow' if gross > 0 else 'outflow'
            amt = abs(gross).quantize(TWO_DP, rounding=ROUND_HALF_UP)
            cat = 'revenue' if direction == 'inflow' else categorize_merchant(merchant, desc, rules)
            rows.append({
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
            })
        if fee > 0:
            fee_amt = fee.quantize(TWO_DP, rounding=ROUND_HALF_UP)
            fee_id = f'{ext_id}:fee' if ext_id else ''
            rows.append({
                'txHash': make_tx_hash('stripe', fee_id, date_s, 'outflow', str(fee_amt), ccy, 'Stripe Fee'),
                'externalId': fee_id,
                'date': date_s,
                'timestamp': ts_s,
                'direction': 'outflow',
                'amount': str(fee_amt),
                'currency': ccy,
                'merchant': 'Stripe Fee',
                'description': f'Processing fee for {ext_id or desc}',
                'category': 'payment_fees',
                'sourceFormat': 'stripe',
                'sourceFile': path.name,
                'sourceLine': line_no,
            })
    return rows


def _parse_cn_wallet_csv(path: Path, rules: list[dict], *, fmt: str, header_marker: str) -> list[dict]:
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
        date_s, ts_s = parse_timestamp(cleaned.get('交易时间') or '')
        merchant = cleaned.get('交易对方') or fmt
        desc = cleaned.get('商品说明') or cleaned.get('商品') or ''
        ext_id = cleaned.get('交易订单号') or cleaned.get('交易单号') or ''
        cat = 'revenue' if direction == 'inflow' else categorize_merchant(merchant, desc, rules)
        rows.append({
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
        })
    return rows


def parse_ofx(path: Path, rules: list[dict]) -> list[dict]:
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
        date_s, ts_s = parse_timestamp(dt_raw)
        ext_id = tag_val(blk, 'FITID')
        merchant = tag_val(blk, 'NAME') or tag_val(blk, 'MEMO') or 'Bank Entry'
        desc = tag_val(blk, 'MEMO') or merchant
        cat = 'revenue' if direction == 'inflow' else categorize_merchant(merchant, desc, rules)
        rows.append({
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
        })
    return rows


def parse_generic_csv(path: Path, rules: list[dict], *, default_currency: str = 'USD', mapping: dict | None = None) -> list[dict]:
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

        raw_amt = lower.get(amt_col)
        if not raw_amt:
            continue
        dec = clean_decimal(raw_amt)
        if dec == 0:
            continue
        direction = 'inflow' if dec > 0 else 'outflow'
        amt = abs(dec).quantize(TWO_DP, rounding=ROUND_HALF_UP)
        date_s, ts_s = parse_timestamp(lower.get(date_col) or lower.get('timestamp') or '')
        ccy = (lower.get(ccy_col) or default_currency).upper()
        merchant = lower.get(merch_col) or lower.get('counterparty') or lower.get('name') or 'Unknown'
        desc = lower.get(desc_col) or lower.get('memo') or merchant
        ext_id = lower.get(id_col) or ''
        cat = lower.get('category') or ('revenue' if direction == 'inflow' else categorize_merchant(merchant, desc, rules))
        rows.append({
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
        })
    return rows


def ingest_statement(
    workspace: Path,
    statement_path: Path,
    *,
    fmt: str,
    default_currency: str = 'USD',
    mapping: dict | None = None,
) -> dict:
    workspace = workspace.expanduser().resolve()
    statement_path = statement_path.expanduser().resolve()
    rules_path = workspace / 'category-rules.json'
    rules = json.loads(rules_path.read_text(encoding='utf-8')).get('rules', []) if rules_path.is_file() else []

    if fmt == 'stripe':
        parsed = parse_stripe_csv(statement_path, rules)
    elif fmt == 'alipay':
        parsed = _parse_cn_wallet_csv(statement_path, rules, fmt='alipay', header_marker='交易时间')
    elif fmt == 'wechat':
        parsed = _parse_cn_wallet_csv(statement_path, rules, fmt='wechat', header_marker='交易时间')
    elif fmt == 'ofx':
        parsed = parse_ofx(statement_path, rules)
    elif fmt == 'csv':
        parsed = parse_generic_csv(statement_path, rules, default_currency=default_currency, mapping=mapping)
    else:
        raise ValueError(f'Unsupported statement format: {fmt}')

    ledger_path = workspace / 'ledger.jsonl'
    existing_hashes: set[str] = set()
    if ledger_path.is_file():
        for ln in ledger_path.read_text(encoding='utf-8').splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                existing_hashes.add(json.loads(ln)['txHash'])
            except (json.JSONDecodeError, KeyError):
                continue

    added = 0
    deduped = 0
    with ledger_path.open('a', encoding='utf-8') as fh:
        for row in parsed:
            if row['txHash'] in existing_hashes:
                deduped += 1
                continue
            fh.write(json.dumps(row, ensure_ascii=False) + '\n')
            existing_hashes.add(row['txHash'])
            added += 1

    return {
        'format': fmt,
        'sourceFile': statement_path.name,
        'parsedCount': len(parsed),
        'addedCount': added,
        'dedupedCount': deduped,
        'totalLedgerCount': len(existing_hashes),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Ingest real bank/payment statements into exact Decimal ledger.jsonl.')
    parser.add_argument('workspace')
    parser.add_argument('--file', required=True)
    parser.add_argument('--format', required=True, choices=('stripe', 'alipay', 'wechat', 'ofx', 'csv'))
    parser.add_argument('--default-currency', default='USD')
    parser.add_argument('--mapping', default=None, help='Optional JSON column mapping file for generic csv')
    args = parser.parse_args()

    mapping = json.loads(Path(args.mapping).expanduser().resolve().read_text(encoding='utf-8')) if args.mapping else None
    result = ingest_statement(
        Path(args.workspace),
        Path(args.file),
        fmt=args.format,
        default_currency=args.default_currency,
        mapping=mapping,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
