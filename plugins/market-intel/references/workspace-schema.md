# Market Intel Data Schema

This directory layout works inside the human's existing research folder, a single Space's `files/` directory, or an optional cross-Space Local Folder (`<data-dir>`). `scripts/init_workspace.py` initializes only the data structure below and never creates `boards/` inside `<data-dir>`.

```text
<data-dir>/
├── watchlist.json                # Monitored entities and their real source adapters
├── seen-events.json              # Deduplication registry keyed by canonical diff fingerprint
├── events.jsonl                  # Append-only grounded change ledger (committed only via evidence_gate.py)
├── captures/
│   ├── <entity-slug>.json        # Optional per-entity shards from parallel child jobs
│   ├── external.json             # Optional Connector / browser / web_fetch records (market-intel-signal/1)
│   ├── latest.json               # Merged envelope schema: market-intel-signal/1
│   ├── diff.json                 # Output from snapshot_diff.py (market-intel-diff/1)
│   └── candidates.json           # Candidate claims fed into evidence_gate.py
├── snapshots/
│   └── <entity-slug>/
│       └── <source-id>.json      # Latest normalized baseline snapshot for deterministic diffing
├── entities/
│   └── <entity-slug>/
│       ├── profile.json          # Structured entity facts (pricing, latest version, headcount signals)
│       └── local-docs/           # Human-supplied filings, transcripts, decks, or call notes
├── battlecards/
│   └── <entity-slug>.json        # Structured comparison card backed by evidenceUrls
└── briefs/
    └── YYYY-MM-DD-brief.md       # Optional grounded periodic or ad-hoc briefs
```

## 1. `watchlist.json` Contract & All 11 Keyless Adapter Keys

```json
{
  "schemaVersion": "market-intel-watchlist/1",
  "updatedAt": "2026-11-25T00:00:00Z",
  "entities": [
    {
      "slug": "acme-cloud",
      "name": "Acme Cloud",
      "category": "direct-competitor",
      "sources": [
        { "id": "pricing", "kind": "webpage", "url": "https://example.com/pricing" },
        { "id": "releases", "kind": "github_releases", "repo": "owner/repo", "limit": 5 },
        { "id": "jobs", "kind": "greenhouse_jobs", "boardToken": "acme" }
      ]
    }
  ]
}
```

Every source object accepts an optional `"id"` (defaults to `kind`) and an optional `"apiUrl"` override for testing or custom mirrors where noted:

| `kind` | Required Keys | Optional Keys | Notes |
|---|---|---|---|
| `webpage` | `url` | `id` | Fetches HTML and extracts normalized visible text lines (max 400 lines) |
| `rss` | `url` | `id`, `limit` (default `10`) | Supports RSS 2.0 and Atom feeds (including Statuspage `/history.atom`) |
| `github_releases` | `repo` (`owner/repo`) | `id`, `limit` (default `5`), `apiUrl` | Uses `GITHUB_TOKEN` env var if set; falls back to public `.atom` on HTTP 403 |
| `appstore_ios` | `appId` or `bundleId` | `id`, `country` (default `"us"`), `apiUrl` | Queries Apple iTunes Lookup API |
| `npm` | `package` | `id`, `apiUrl` | Supports scoped packages (e.g., `@scope/pkg`) |
| `pypi` | `package` | `id`, `apiUrl` | Queries PyPI JSON API |
| `greenhouse_jobs` | `boardToken` | `id`, `apiUrl` | Queries Greenhouse public board jobs endpoint |
| `ashby_jobs` | `boardSlug` | `id`, `apiUrl` | Queries Ashby public job-board API (includes `departments`) |
| `lever_jobs` | `siteSlug` | `id`, `apiUrl` | Queries Lever public postings API |
| `sec_edgar` | `cik` | `id`, `forms` (default `["10-K","10-Q","8-K","S-1"]`), `limit` (default `10`), `apiUrl` | Zero-pads CIK to 10 digits with SEC-compliant `User-Agent` |
| `hn_algolia` | `query` | `id`, `limit` (default `10`), `apiUrl` | Queries Hacker News Algolia `search_by_date` stories |

## 2. Capture Envelope (`captures/latest.json`, `market-intel-signal/1`)

Used by `fetch_sources.py`, `snapshot_diff.py`, and `evidence_gate.py`. Priority 1 Connectors and Priority 3 browser / `web_fetch` / `local_doc` observations append records in the same shape:

```json
{
  "schemaVersion": "market-intel-signal/1",
  "generatedAt": "2026-11-27T10:00:00Z",
  "dataDir": "/path/to/data-dir",
  "totalSources": 2,
  "okCount": 2,
  "failedCount": 0,
  "records": [
    {
      "entitySlug": "acme",
      "sourceId": "pricing",
      "kind": "webpage",
      "ok": true,
      "url": "https://acme.example/pricing",
      "observedAt": "2026-11-27T10:00:00Z",
      "structured": { "title": "Acme Pricing", "lines": ["Pro Plan", "$49/mo"] }
    },
    {
      "entitySlug": "acme",
      "sourceId": "x-official",
      "kind": "connector:x",
      "ok": true,
      "url": "https://x.com/acme/status/123456",
      "observedAt": "2026-11-27T09:50:00Z",
      "structured": { "excerpt": "Enterprise SSO is now included on Business plans." }
    }
  ]
}
```

## 3. `candidates.json` Input & `evidence_gate.py` Exit-Code Contract

`evidence_gate.py --candidates <path>` accepts either a top-level JSON array `[ ... ]` or `{ "candidates": [ ... ] }`:

```json
[
  {
    "entitySlug": "acme",
    "severity": "high",
    "category": "pricing",
    "confidence": "triangulated",
    "summary": "Acme raised Pro Plan pricing from $29/mo to $49/mo while expanding Enterprise AE hiring.",
    "evidenceUrls": [
      "https://acme.example/pricing",
      "https://boards.greenhouse.io/acme"
    ],
    "localRef": "entities/acme/local-docs/q3-call-notes.txt",
    "observedAt": "2026-11-27T10:00:00Z",
    "quote": "Pro Plan $49/mo"
  }
]
```

### Gate Invariants & Exit Codes
- **Fail-closed watchlist**: Rejects all candidates if `watchlist.json` has zero registered entities or `entitySlug` is unknown.
- **Per-entity isolation**: Every URL in `evidenceUrls` must exist in an `ok: true` capture record belonging to the **same** `entitySlug`.
- **Multi-tier evidence**: Each candidate must supply at least one verified `evidenceUrls` entry or an existing relative `localRef` inside `<data-dir>` (absolute paths and `..` traversal are rejected).
- **Quote verification**: Normalized `quote` (>= 5 chars, collapsed whitespace, case-insensitive) must appear verbatim inside the referenced entity capture records or `localRef` file.
- **Triangulation guard**: `confidence: "triangulated"` requires `>= 2` distinct captured `sourceKinds` for that entity (`local_doc` counts as a distinct source kind).
- **Exit codes**:
  - `0`: All candidates accepted (`rejectedCount == 0`).
  - `2`: One or more candidates rejected (`rejectedCount > 0`; inspect `rejected[].errors`).
  - Non-zero exception (`1`): Invalid capture schemaVersion, missing/invalid `generatedAt`, or stale capture (`> --max-age-hours`, default `24.0`).

## 4. Grounded Event Ledger (`events.jsonl`)

Append-only JSONL committed solely through `scripts/evidence_gate.py --commit-events`:

- `eventId`: deterministic 16-char sha256 fingerprint (idempotent deduplication key)
- `entitySlug`: registered entity slug from `watchlist.json`
- `severity`: `"high"` | `"medium"` | `"low"`
- `category`: `"pricing"` | `"release"` | `"hiring"` | `"filing"` | `"outage"` | `"positioning"` | `"community"`
- `confidence`: `"triangulated"` | `"single_source"` (computed by `evidence_gate.py`)
- `sourceKinds`: sorted list of distinct verified source kinds backing this event
- `summary`: concise factual change statement (>= 8 chars)
- `evidenceUrls`: sorted list of canonicalized verified `http(s)://` URLs (may be `[]` when grounded via `localRef`)
- `localRef` *(optional)*: normalized POSIX relative path inside `<data-dir>` when backed by a local document
- `observedAt`: timezone-aware ISO-8601 UTC timestamp
- `quote`: verbatim snippet verified against the referenced capture record or `localRef` file
- `verifiedAt`: ISO-8601 UTC timestamp stamped by `evidence_gate.py`

## 5. Entity Profile (`entities/<slug>/profile.json`)

Baseline factual summary used as fallback values by `build_boards.py`:

```json
{
  "slug": "acme",
  "name": "Acme Corp",
  "category": "direct-competitor",
  "updatedAt": "2026-11-27T10:00:00Z",
  "pricingSummary": "Free / Pro $49/mo / Enterprise custom",
  "latestVersion": "v2.1.0 (CLI), 4.2.0 (iOS)",
  "hiringSignal": "14 open roles (4 Enterprise AE, 3 Security)",
  "notes": "Focuses on mid-market to enterprise teams.",
  "evidenceUrls": ["https://acme.example/pricing"]
}
```

## 6. Battlecard (`battlecards/<slug>.json`)

Structured comparison record projected into `battlecard-board`:

```json
{
  "slug": "acme",
  "updatedAt": "2026-11-27T10:00:00Z",
  "threatLevel": "high",
  "oneLiner": "Developer-first workflow suite pivoting upmarket with enterprise SSO.",
  "pricingSummary": "Pro $49/mo per seat; Enterprise custom",
  "latestVersion": "v2.1.0",
  "hiringSignal": "14 open roles; heavy Enterprise AE expansion",
  "whenWeWin": "Teams needing zero-config local ownership and transparent flat pricing.",
  "whenWeLose": "Large enterprises standardized on Acme's legacy compliance bundle.",
  "strengths": ["Mature SSO and SCIM provisioning", "Broad IDE integrations"],
  "gaps": ["No offline mode", "Seat-based pricing escalates sharply above 25 users"],
  "landmines": ["Ask how pricing scales once external collaborators need read-only access."],
  "objectionHandlers": [
    {
      "objection": "Acme ships faster on enterprise compliance.",
      "response": "Acknowledge their SCIM bundle; contrast total 12-month cost and deployment speed."
    }
  ],
  "evidenceUrls": [
    "https://acme.example/pricing",
    "https://boards.greenhouse.io/acme"
  ]
}
```
