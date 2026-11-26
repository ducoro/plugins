# Market Intel Data Schema

This directory layout works inside the human's existing research folder, a single Space's `files/` directory, or an optional cross-Space Local Folder.

```text
market-intel/
├── watchlist.json                # Monitored entities and their real source adapters
├── seen-events.json              # Deduplication registry keyed by canonical diff/event fingerprint
├── events.jsonl                  # Append-only grounded change ledger (committed only via evidence_gate.py)
├── captures/
│   ├── latest.json               # Envelope schema: market-intel-signal/1
│   └── diff.json                 # Output from snapshot_diff.py
├── snapshots/
│   └── <entity-slug>/
│       └── <source-id>.json      # Latest normalized baseline snapshot for deterministic diffing
├── entities/
│   └── <entity-slug>/
│       ├── profile.json          # Structured entity facts (pricing, latest version, headcount signals)
│       └── local-docs/           # Human-supplied filings, decks, or call notes
├── battlecards/
│   └── <entity-slug>.json        # Structured comparison rows backed by evidenceUrls
└── briefs/
    └── YYYY-MM-DD-brief.md       # Grounded periodic executive briefs
```

## `watchlist.json` Entry Contract

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
        { "id": "releases", "kind": "github_releases", "repo": "owner/repo" },
        { "id": "jobs", "kind": "greenhouse_jobs", "boardToken": "acme" }
      ]
    }
  ]
}
```

## Grounded Event Record (`events.jsonl`)

Every line appended to `events.jsonl` must contain:
- `eventId`: deterministic 16-char sha256 fingerprint
- `entitySlug`: matches an entity in `watchlist.json`
- `severity`: `"high"` | `"medium"` | `"low"`
- `category`: `"pricing"` | `"release"` | `"hiring"` | `"filing"` | `"outage"` | `"positioning"` | `"community"`
- `summary`: concise factual change statement
- `evidenceUrls`: non-empty list of valid `http(s)://` URLs verified against the capture envelope
- `observedAt`: valid ISO-8601 UTC timestamp
- `quote`: verbatim snippet from the captured source
