# Real Data Sources & Adapter Priority

Never fabricate competitor metrics, pricing, releases, or filings from model memory. Collect live facts in strict priority order:

## Priority 1: Ducoro Core Connectors

Always inspect connected account-level tools first:
```sh
ducoro-cli mcp catalog list --json
ducoro-cli mcp catalog status <slug> --json
ducoro-cli mcp catalog tools <slug> --json
```
Use mounted Connector tools (or `ducoro-cli mcp catalog call <slug> <tool> --args-file <path|-> --json`) when monitoring authenticated channels such as X, GitHub private repos, Slack, Linear, Notion, or Google Drive.

## Priority 2: Verified Keyless Public APIs (`scripts/fetch_sources.py`)

Zero API keys required; all endpoints return official, publicly accessible data:

| Source Type (`kind`) | Official Public Endpoint | What It Tracks (Invisible to Model Memory) |
|---|---|---|
| `webpage` | Any public pricing / changelog / docs URL | Normalized DOM text & price/heading lines for objective diffing |
| `rss` | Any RSS 2.0 / Atom feed (blogs, Atlassian Statuspage `/history.atom`) | Official announcements, outages, changelogs |
| `github_releases` | `https://api.github.com/repos/<owner>/<repo>/releases` | Exact release tags, publish timestamps, release notes |
| `appstore_ios` | `https://itunes.apple.com/lookup?id=<appId>` (or `bundleId`) | Live iOS version, release notes, rating average & review count |
| `npm` | `https://registry.npmjs.org/<package>/latest` | Exact latest package version, dependencies, publish signals |
| `pypi` | `https://pypi.org/pypi/<package>/json` | Exact latest Python release version and metadata |
| `greenhouse_jobs` | `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` | Live hiring headcount, departments, and new role titles |
| `ashby_jobs` | `https://api.ashbyhq.com/posting-api/job-board/<slug>` | Live hiring signals for Ashby-hosted startups |
| `lever_jobs` | `https://api.lever.co/v0/postings/<slug>?mode=json` | Live hiring signals for Lever-hosted companies |
| `sec_edgar` | `https://data.sec.gov/submissions/CIK<10-digit>.json` | Official US SEC filings (10-K, 10-Q, 8-K, S-1) with compliant User-Agent |
| `hn_algolia` | `https://hn.algolia.com/api/v1/search_by_date?query=<q>&tags=story` | Live Hacker News community mentions and point/comment velocity |

## Priority 3: Built-in Web Search / Official Browser / Local Documents

- Use built-in `web_search` / `web_fetch` for primary press releases or investor-relations pages.
- For login-gated portals or JS-heavy pricing calculators, use the host browser and pause immediately for human login/CAPTCHA; never extract browser cookies or bypass anti-bot gates.
- Human-supplied PDFs, earnings transcripts, or customer interview notes live under `entities/<slug>/local-docs/` and are cited by relative path plus page/line excerpt.
