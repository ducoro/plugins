# Live External Truth: Supply-Chain Security & Pinned-Version Docs

Never guess third-party APIs or vulnerability status from model training memory. Verify against the exact versions pinned in the repository's lockfiles.

## 1. Live Vulnerability & License Audit (`scripts/supply_chain_check.py`)

Run against the target repository to parse root-level lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `bun.lock`, `yarn.lock`, `requirements.txt`, `pyproject.toml`, `uv.lock`, `poetry.lock`, `Cargo.lock`, `go.mod`), query the keyless public **OSV.dev Batch API** (`https://api.osv.dev/v1/querybatch`), and scan for copyleft license declarations (`GPL-*`, `AGPL-*`, `SSPL-*`):

```sh
python3 <plugin-root>/scripts/supply_chain_check.py --repo <repo-path> --out <state-dir>/supply-chain.json
```

- **Honest scope & limitations**:
  - Lockfile discovery currently scans the **repository root** (for monorepos with nested lockfiles, inspect subpackages explicitly or use native package-manager audit tools alongside).
  - License scanning inspects dependency entries in root `package-lock.json` plus root `package.json`, `pyproject.toml`, and `Cargo.toml` manifest declarations (it does not fetch transitive license metadata from registries; ignore self-license alerts if the repository itself is intentionally copyleft open source).
- **Private package name hygiene**: Public OSV queries send external package names and versions. For repositories using private registries (non-`workspace:` internal scopes), pass repeatable `--exclude-prefix <prefix>` (e.g., `--exclude-prefix @my-company/`) so internal package names are never sent to OSV.dev; excluded counts are reported honestly in `excludedDependencyCount`.
- **Offline & network failure behavior**:
  - Use `--offline` only in air-gapped environments or unit tests (explicitly marks `"osvStatus": "skipped_offline"`—never claim zero vulnerabilities when offline).
  - Running online without network access sets `"osvStatus": "query_failed"` and exits with code `2`—report the vulnerability state as **unverified/unknown**, never clean.
- **Exit codes & strict flags**: `0` = check completed cleanly; `1` = invalid repo path; `2` = live OSV query failed; `3` = vulnerabilities found with `--fail-on-vuln`; `4` = copyleft license alerts found with `--fail-on-copyleft`.
- Treat `GPL-*`, `AGPL-*`, and `SSPL-*` matches in proprietary repositories as explicit `Needs a Yes` escalations before merging.

## 2. Verifying Fast-Moving Upstream SDK & Framework APIs

Before writing code against a rapidly evolving dependency (web frameworks, cloud SDKs, AI SDKs, desktop shells):

1. Read the exact installed version from the repo's manifest/lockfile (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`).
2. Check connected live-documentation Connectors first (`ducoro-cli mcp catalog list --json`).
3. When local source truth is needed, inspect installed `node_modules` / `.venv` package types directly or register the upstream repo read-only via `ducoro-cli reference-material inspect <url> --json` and `ducoro-cli reference-material register <slug> <url>`.
4. Never invent flags, endpoints, or configuration fields that cannot be verified in the pinned version's types, source, or official docs.
