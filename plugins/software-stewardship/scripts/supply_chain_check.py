#!/usr/bin/env python3
"""Parse real project lockfiles, query keyless OSV.dev batch API for live CVEs, and flag copyleft licenses."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.request

DEFAULT_OSV_BATCH_URL = 'https://api.osv.dev/v1/querybatch'
COPYLEFT_RE = re.compile(r'\b(AGPL(?:-[0-9.]+)?|GPL(?:-[0-9.]+)?|SSPL(?:-[0-9.]+)?)\b', re.I)
REQ_PIN_RE = re.compile(r'^\s*([A-Za-z0-9_.-]+)\s*==\s*([A-Za-z0-9_.+-]+)')
GO_REQ_RE = re.compile(r'^\s*([A-Za-z0-9_./-]+)\s+v([0-9][^\s]+)')
PNPM_PKG_RE = re.compile(r"^\s*'?/?((?:@[^/@\s]+/)?[^/@:\s]+)@([0-9][^('\s:]+)")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_package_lock(path: Path) -> list[dict]:
    deps = []
    data = json.loads(path.read_text(encoding='utf-8'))
    packages = data.get('packages')
    if isinstance(packages, dict):
        for key, meta in packages.items():
            if not key or not isinstance(meta, dict):
                continue
            ver = meta.get('version')
            if not isinstance(ver, str) or not ver:
                continue
            name = meta.get('name') or key.split('node_modules/')[-1]
            if name:
                deps.append({'ecosystem': 'npm', 'name': name, 'version': ver, 'source': path.name})
    elif isinstance(data.get('dependencies'), dict):
        for name, meta in data['dependencies'].items():
            if isinstance(meta, dict) and isinstance(meta.get('version'), str):
                deps.append({'ecosystem': 'npm', 'name': name, 'version': meta['version'], 'source': path.name})
    return deps


def parse_pnpm_lock(path: Path) -> list[dict]:
    deps = []
    in_packages = False
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if re.match(r'^packages:\s*$', line):
            in_packages = True
            continue
        if in_packages and line and not line.startswith(' '):
            in_packages = False
        if not in_packages:
            continue
        m = PNPM_PKG_RE.match(line)
        if m:
            deps.append({'ecosystem': 'npm', 'name': m.group(1), 'version': m.group(2), 'source': path.name})
    return deps


def parse_requirements(path: Path) -> list[dict]:
    deps = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        clean = line.split('#', 1)[0].strip()
        m = REQ_PIN_RE.match(clean)
        if m:
            deps.append({'ecosystem': 'PyPI', 'name': m.group(1), 'version': m.group(2), 'source': path.name})
    return deps


def parse_pyproject(path: Path) -> list[dict]:
    deps = []
    text = path.read_text(encoding='utf-8', errors='replace')
    for m in re.finditer(r'["\']([A-Za-z0-9_.-]+)==([A-Za-z0-9_.+-]+)["\']', text):
        deps.append({'ecosystem': 'PyPI', 'name': m.group(1), 'version': m.group(2), 'source': path.name})
    return deps


def parse_cargo_lock(path: Path) -> list[dict]:
    deps = []
    name = None
    version = None
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        stripped = line.strip()
        if stripped == '[[package]]':
            if name and version:
                deps.append({'ecosystem': 'crates.io', 'name': name, 'version': version, 'source': path.name})
            name = None
            version = None
        elif stripped.startswith('name = '):
            name = stripped.split('=', 1)[1].strip().strip('"')
        elif stripped.startswith('version = '):
            version = stripped.split('=', 1)[1].strip().strip('"')
    if name and version:
        deps.append({'ecosystem': 'crates.io', 'name': name, 'version': version, 'source': path.name})
    return deps


def parse_go_mod(path: Path) -> list[dict]:
    deps = []
    in_block = False
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        clean = line.split('//', 1)[0].strip()
        if clean.startswith('require ('):
            in_block = True
            continue
        if in_block and clean == ')':
            in_block = False
            continue
        candidate = clean[len('require '):].strip() if clean.startswith('require ') else (clean if in_block else '')
        m = GO_REQ_RE.match(candidate)
        if m:
            deps.append({'ecosystem': 'Go', 'name': m.group(1), 'version': f'v{m.group(2)}', 'source': path.name})
    return deps


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments plus trailing commas outside string literals."""
    out = []
    i = 0
    n = len(text)
    in_str = False
    escape = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == '/' and i + 1 < n and text[i + 1] == '/':
            i += 2
            while i < n and text[i] != '\n':
                i += 1
            continue
        if ch == '/' and i + 1 < n and text[i + 1] == '*':
            i += 2
            while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    no_comments = ''.join(out)
    # Remove trailing commas before } or ] (safe outside strings via simple token scan)
    cleaned = []
    in_str = False
    escape = False
    j = 0
    m = len(no_comments)
    while j < m:
        ch = no_comments[j]
        if in_str:
            cleaned.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == '"':
                in_str = False
            j += 1
            continue
        if ch == '"':
            in_str = True
            cleaned.append(ch)
            j += 1
            continue
        if ch == ',':
            k = j + 1
            while k < m and no_comments[k] in ' \t\r\n':
                k += 1
            if k < m and no_comments[k] in '}]':
                j += 1
                continue
        cleaned.append(ch)
        j += 1
    return ''.join(cleaned)


def parse_bun_lock(path: Path) -> list[dict]:
    deps = []
    data = json.loads(strip_jsonc(path.read_text(encoding='utf-8')))
    packages = data.get('packages')
    if not isinstance(packages, dict):
        return deps
    for entry in packages.values():
        if not isinstance(entry, list) or not entry or not isinstance(entry[0], str):
            continue
        spec = entry[0].strip()
        at_idx = spec.rfind('@')
        if at_idx <= 0:
            continue
        name = spec[:at_idx]
        ver = spec[at_idx + 1:]
        if not name or not ver or not re.match(r'^\d+\.\d+', ver):
            continue
        deps.append({'ecosystem': 'npm', 'name': name, 'version': ver, 'source': path.name})
    return deps


def parse_yarn_lock(path: Path) -> list[dict]:
    deps = []
    current_name: str | None = None
    ver_re = re.compile(r'^\s+version(?::\s*|\s+)"?([^"\s]+)"?')
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line or line.startswith('#'):
            continue
        if not line.startswith(' '):
            current_name = None
            if line.rstrip().endswith(':'):
                header = line.rstrip()[:-1].split(',')[0].strip().strip('"').strip("'")
                if header and not header.startswith('__metadata'):
                    at_idx = header.rfind('@')
                    if at_idx > 0:
                        cand = header[:at_idx]
                        # Yarn Berry uses name@npm:^1.0.0 -> strip @npm if nested
                        if '@' in cand and not cand.startswith('@'):
                            cand = cand.split('@', 1)[0]
                        current_name = cand
            continue
        if current_name:
            m = ver_re.match(line)
            if m:
                ver = m.group(1)
                if re.match(r'^\d+\.\d+', ver) and 'use.local' not in ver:
                    deps.append({'ecosystem': 'npm', 'name': current_name, 'version': ver, 'source': path.name})
                current_name = None
    return deps


def parse_toml_pypi_lock(path: Path) -> list[dict]:
    """Parse [[package]] tables from uv.lock or poetry.lock, skipping local virtual/editable roots."""
    deps = []
    name = None
    version = None
    is_local = False

    def flush() -> None:
        if name and version and not is_local:
            deps.append({'ecosystem': 'PyPI', 'name': name, 'version': version, 'source': path.name})

    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        stripped = line.strip()
        if stripped == '[[package]]':
            flush()
            name = None
            version = None
            is_local = False
        elif stripped.startswith('name = '):
            name = stripped.split('=', 1)[1].strip().strip('"').strip("'")
        elif stripped.startswith('version = '):
            version = stripped.split('=', 1)[1].strip().strip('"').strip("'")
        elif stripped.startswith('source = ') and any(tok in stripped for tok in ('virtual', 'editable', 'directory')):
            is_local = True
    flush()
    return deps


def discover_dependencies(repo: Path) -> tuple[list[dict], list[str]]:
    parsers = (
        ('package-lock.json', parse_package_lock),
        ('pnpm-lock.yaml', parse_pnpm_lock),
        ('bun.lock', parse_bun_lock),
        ('yarn.lock', parse_yarn_lock),
        ('requirements.txt', parse_requirements),
        ('pyproject.toml', parse_pyproject),
        ('uv.lock', parse_toml_pypi_lock),
        ('poetry.lock', parse_toml_pypi_lock),
        ('Cargo.lock', parse_cargo_lock),
        ('go.mod', parse_go_mod),
    )
    found_files = []
    seen = set()
    deduped = []
    for filename, fn in parsers:
        fpath = repo / filename
        if not fpath.is_file():
            continue
        found_files.append(filename)
        try:
            rows = fn(fpath)
        except (OSError, ValueError):
            continue
        for row in rows:
            key = (row['ecosystem'], row['name'].lower(), row['version'])
            if key not in seen:
                seen.add(key)
                deduped.append(row)
    return deduped, found_files


def scan_copyleft_licenses(repo: Path) -> list[dict]:
    alerts = []
    pkg_lock = repo / 'package-lock.json'
    if pkg_lock.is_file():
        try:
            data = json.loads(pkg_lock.read_text(encoding='utf-8'))
            for key, meta in (data.get('packages') or {}).items():
                if not key or not isinstance(meta, dict):
                    continue
                lic = str(meta.get('license') or '')
                m = COPYLEFT_RE.search(lic)
                if m:
                    name = meta.get('name') or key.split('node_modules/')[-1]
                    alerts.append({
                        'source': 'package-lock.json',
                        'package': name,
                        'license': lic,
                        'matched': m.group(1).upper(),
                    })
        except (OSError, ValueError):
            pass

    for manifest_name in ('package.json', 'pyproject.toml', 'Cargo.toml'):
        mpath = repo / manifest_name
        if not mpath.is_file():
            continue
        text = mpath.read_text(encoding='utf-8', errors='replace')
        for line_no, line in enumerate(text.splitlines(), start=1):
            if 'license' not in line.lower():
                continue
            m = COPYLEFT_RE.search(line)
            if m:
                alerts.append({
                    'source': f'{manifest_name}:{line_no}',
                    'package': repo.name,
                    'license': line.strip()[:120],
                    'matched': m.group(1).upper(),
                })
    return alerts


def query_osv_batch(
    dependencies: list[dict],
    *,
    osv_url: str = DEFAULT_OSV_BATCH_URL,
    timeout: int = 20,
    batch_size: int = 250,
) -> tuple[str, list[dict], str | None]:
    if not dependencies:
        return 'no_dependencies', [], None

    vulns = []
    for i in range(0, len(dependencies), batch_size):
        chunk = dependencies[i:i + batch_size]
        payload = {
            'queries': [
                {'version': d['version'], 'package': {'name': d['name'], 'ecosystem': d['ecosystem']}}
                for d in chunk
            ]
        }
        req = urllib.request.Request(
            osv_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'User-Agent': 'ducoro-software-stewardship/1.0'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode('utf-8'))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as err:
            return 'query_failed', [], str(err)

        results = body.get('results')
        if not isinstance(results, list) or len(results) != len(chunk):
            return 'query_failed', [], 'Unexpected OSV batch response shape'

        for dep, item in zip(chunk, results):
            for v in (item.get('vulns') or []):
                vid = v.get('id')
                if not vid:
                    continue
                vulns.append({
                    'id': vid,
                    'package': dep['name'],
                    'ecosystem': dep['ecosystem'],
                    'version': dep['version'],
                    'source': dep['source'],
                    'modified': v.get('modified'),
                    'advisoryUrl': f'https://osv.dev/vulnerability/{vid}',
                })
    return 'ok', vulns, None


def run_supply_chain_check(
    repo: Path,
    *,
    offline: bool = False,
    osv_url: str = DEFAULT_OSV_BATCH_URL,
    timeout: int = 20,
    exclude_prefixes: list[str] | tuple[str, ...] = (),
) -> dict:
    repo = repo.expanduser().resolve()
    if not repo.is_dir():
        raise ValueError(f'{repo}: repository directory does not exist')

    all_deps, lockfiles = discover_dependencies(repo)
    norm_prefixes = tuple(p.strip().lower() for p in exclude_prefixes if p and p.strip())
    if norm_prefixes:
        deps = [d for d in all_deps if not d['name'].lower().startswith(norm_prefixes)]
        excluded_count = len(all_deps) - len(deps)
    else:
        deps = all_deps
        excluded_count = 0

    license_alerts = scan_copyleft_licenses(repo)

    if offline:
        osv_status, vulns, osv_error = 'skipped_offline', [], None
    else:
        osv_status, vulns, osv_error = query_osv_batch(deps, osv_url=osv_url, timeout=timeout)

    return {
        'schemaVersion': 'software-stewardship-supply-chain/1',
        'generatedAt': utc_now(),
        'repoName': repo.name,
        'lockfilesFound': lockfiles,
        'dependencyCount': len(deps),
        'excludedDependencyCount': excluded_count,
        'osvStatus': osv_status,
        'osvError': osv_error,
        'vulnerabilityCount': len(vulns),
        'vulnerabilities': vulns,
        'licenseAlertCount': len(license_alerts),
        'licenseAlerts': license_alerts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit repository lockfiles against live OSV.dev CVEs and copyleft licenses.')
    parser.add_argument('--repo', required=True, help='Path to target repository')
    parser.add_argument('--offline', action='store_true', help='Skip live OSV network query (honestly marked skipped_offline)')
    parser.add_argument('--osv-url', default=DEFAULT_OSV_BATCH_URL, help='Override OSV batch API endpoint')
    parser.add_argument('--timeout', type=int, default=20)
    parser.add_argument('--exclude-prefix', action='append', default=[], help='Repeatable package name prefix to exclude from public OSV queries (e.g., @my-company/)')
    parser.add_argument('--fail-on-vuln', action='store_true')
    parser.add_argument('--fail-on-copyleft', action='store_true')
    parser.add_argument('--out', default=None, help='Optional output JSON path inside Space files/')
    args = parser.parse_args()

    try:
        report = run_supply_chain_check(
            Path(args.repo),
            offline=args.offline,
            osv_url=args.osv_url,
            timeout=args.timeout,
            exclude_prefixes=args.exclude_prefix,
        )
    except ValueError as err:
        print(json.dumps({'ok': False, 'error': str(err)}, indent=2), file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f'.{out_path.name}.', suffix='.tmp', dir=str(out_path.parent))
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                fh.write(rendered)
            os.replace(tmp_path, out_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
    print(rendered, end='')

    if report['osvStatus'] == 'query_failed':
        return 2
    if args.fail_on_vuln and report['vulnerabilityCount'] > 0:
        return 3
    if args.fail_on_copyleft and report['licenseAlertCount'] > 0:
        return 4
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
