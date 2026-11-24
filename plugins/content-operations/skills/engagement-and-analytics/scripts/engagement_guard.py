#!/usr/bin/env python3
"""Deterministic anti-spam budget, idempotency, and append-only action-log guard (zero dependencies)."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import uuid

# Canonical per-platform caps matching engagement-and-analytics/references/rate-limit-safety.md
PLATFORM_CAPS: dict[str, tuple[int, int]] = {
    'x-twitter': (15, 80),
    'youtube': (12, 60),
    'facebook': (12, 60),
    'threads': (12, 60),
    'bilibili': (10, 50),
    'tiktok': (10, 50),
    'instagram': (10, 50),
    'pinterest': (10, 50),
    'xiaohongshu': (6, 40),
    'douyin': (6, 40),
    'wechat-channels': (6, 40),
    'kuaishou': (6, 40),
    'linkedin': (6, 40),
    'wechat-official': (6, 30),
}
DEFAULT_CAP = (6, 30)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso(val: str | None) -> datetime | None:
    if not val or not isinstance(val, str):
        return None
    try:
        dt = datetime.fromisoformat(val.strip().replace('Z', '+00:00'))
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_actions(ws: Path) -> list[dict]:
    path = ws / 'engagement' / 'action-log.jsonl'
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                rows.append(obj)
        except ValueError:
            continue
    return rows


def check_budget(ws: Path, platform: str, account_id: str, now: datetime | None = None,
                 hourly_cap: int | None = None, daily_cap: int | None = None) -> dict:
    now = now or utc_now()
    default_h, default_d = PLATFORM_CAPS.get(platform, DEFAULT_CAP)
    cap_h = hourly_cap if hourly_cap is not None else default_h
    cap_d = daily_cap if daily_cap is not None else default_d
    today_prefix = now.astimezone(timezone.utc).strftime('%Y-%m-%d')
    hour_cutoff = now - timedelta(hours=1)

    used_day = 0
    used_hour = 0
    for row in load_actions(ws):
        if row.get('platform') != platform or row.get('accountId') != account_id:
            continue
        if row.get('result') == 'skipped':
            continue
        ts = parse_iso(row.get('executedAt'))
        if ts is None:
            continue
        if ts.astimezone(timezone.utc).strftime('%Y-%m-%d') == today_prefix:
            used_day += 1
        if ts >= hour_cutoff:
            used_hour += 1

    ok = (used_hour < cap_h) and (used_day < cap_d)
    reasons = []
    if used_hour >= cap_h:
        reasons.append(f'hourly cap reached ({used_hour}/{cap_h})')
    if used_day >= cap_d:
        reasons.append(f'daily cap reached ({used_day}/{cap_d})')
    return {
        'ok': ok,
        'platform': platform,
        'accountId': account_id,
        'usedHour': used_hour,
        'hourlyCap': cap_h,
        'usedDay': used_day,
        'dailyCap': cap_d,
        'reserveForHighIntent': used_day >= int(cap_d * 0.8),
        'reasons': reasons,
    }


def check_idempotent(ws: Path, platform: str, account_id: str, target_id: str, action_type: str) -> dict:
    for row in load_actions(ws):
        if (
            row.get('platform') == platform
            and row.get('accountId') == account_id
            and row.get('targetId') == target_id
            and row.get('actionType') == action_type
            and row.get('result', 'ok') == 'ok'
        ):
            return {
                'ok': False,
                'alreadyExecuted': True,
                'existingActionId': row.get('actionId'),
                'executedAt': row.get('executedAt'),
            }
    return {'ok': True, 'alreadyExecuted': False}


def record_action(
    ws: Path,
    *,
    platform: str,
    account_id: str,
    target_id: str,
    action_type: str,
    result: str = 'ok',
    summary: str = '',
    executed_at: str | None = None,
    action_id: str | None = None,
    bypass_checks: bool = False,
) -> dict:
    now = parse_iso(executed_at) if executed_at else utc_now()
    if now is None:
        raise ValueError(f'Invalid ISO timestamp: {executed_at}')

    if not bypass_checks and result == 'ok':
        idem = check_idempotent(ws, platform, account_id, target_id, action_type)
        if not idem['ok']:
            return {'ok': False, 'error': 'duplicate_action', 'idempotency': idem}
        bud = check_budget(ws, platform, account_id, now=now)
        if not bud['ok']:
            return {'ok': False, 'error': 'rate_limit_exceeded', 'budget': bud}

    entry = {
        'actionId': action_id or f'act-{uuid.uuid4().hex[:12]}',
        'executedAt': iso_utc(now),
        'platform': platform,
        'accountId': account_id,
        'targetId': target_id,
        'actionType': action_type,
        'result': result,
        'summary': summary.strip(),
    }
    log_path = ws / 'engagement' / 'action-log.jsonl'
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return {'ok': True, 'recorded': entry}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Enforce per-platform engagement rate caps, idempotency, and action-log integrity.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_bud = sub.add_parser('check-budget', help='Check hourly and daily UTC budget before an engagement action.')
    p_bud.add_argument('workspace')
    p_bud.add_argument('--platform', required=True)
    p_bud.add_argument('--account-id', required=True)
    p_bud.add_argument('--hourly-cap', type=int, default=None)
    p_bud.add_argument('--daily-cap', type=int, default=None)

    p_id = sub.add_parser('check-idempotent', help='Verify (platform, accountId, targetId, actionType) has not already succeeded.')
    p_id.add_argument('workspace')
    p_id.add_argument('--platform', required=True)
    p_id.add_argument('--account-id', required=True)
    p_id.add_argument('--target-id', required=True)
    p_id.add_argument('--action-type', required=True)

    p_rec = sub.add_parser('record-action', help='Check idempotency + budget (for result=ok) and append to engagement/action-log.jsonl.')
    p_rec.add_argument('workspace')
    p_rec.add_argument('--platform', required=True)
    p_rec.add_argument('--account-id', required=True)
    p_rec.add_argument('--target-id', required=True)
    p_rec.add_argument('--action-type', required=True)
    p_rec.add_argument('--result', choices=['ok', 'error', 'skipped'], default='ok')
    p_rec.add_argument('--summary', default='')
    p_rec.add_argument('--executed-at', default='')
    p_rec.add_argument('--action-id', default='')

    args = ap.parse_args(argv)
    ws = Path(args.workspace).expanduser().resolve()
    try:
        if args.cmd == 'check-budget':
            res = check_budget(ws, args.platform, args.account_id, hourly_cap=args.hourly_cap, daily_cap=args.daily_cap)
        elif args.cmd == 'check-idempotent':
            res = check_idempotent(ws, args.platform, args.account_id, args.target_id, args.action_type)
        else:
            res = record_action(
                ws,
                platform=args.platform,
                account_id=args.account_id,
                target_id=args.target_id,
                action_type=args.action_type,
                result=args.result,
                summary=args.summary,
                executed_at=args.executed_at or None,
                action_id=args.action_id or None,
            )
    except ValueError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, indent=2, ensure_ascii=False))
        return 2

    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
