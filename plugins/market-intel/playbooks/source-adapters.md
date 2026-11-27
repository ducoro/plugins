# Real Data Sources & Adapter Priority

Never fabricate competitor metrics, pricing, releases, rankings, or filings from model memory. Collect live facts in strict priority order and ground every tier into `evidence_gate.py`.

## Priority 1: Ducoro Core Connectors

Always inspect connected account-level tools first:
```sh
ducoro-cli mcp catalog list --json
ducoro-cli mcp catalog status <slug> --json
ducoro-cli mcp catalog tools <slug> --json
```
Use mounted Connector tools (or `ducoro-cli mcp catalog call <slug> <tool> --args-file <path|-> --json`) first whenever monitoring platforms with active Connectors such as **Reddit**, **X**, **GitHub**, Slack, Linear, Notion, or Google Drive.

## Priority 2: Verified Public Source Fetchers (`scripts/fetch_sources.py`)

Zero API keys required for default public endpoints (optional `GITHUB_TOKEN` / `PRODUCTHUNT_TOKEN` unlock higher rate limits or richer GraphQL fields). Full `watchlist.json` source keys live in `references/workspace-schema.md`.

| Source Type (`kind`) | Official Public Endpoint | What It Tracks (Invisible to Model Memory) |
|---|---|---|
| `webpage` | Any public pricing / changelog / docs URL | Normalized DOM text & price/heading lines for objective diffing |
| `rss` | Any RSS 2.0 / Atom feed (blogs, Medium `/feed/@author` or `/feed/tag/<tag>`, Statuspage `/history.atom`) | Official announcements, outages, free blog/Medium articles, changelogs |
| `github_releases` | `https://api.github.com/repos/<owner>/<repo>/releases` (Atom fallback on 403) | Exact release tags, publish timestamps, release notes |
| `github_repo_activity` | `https://api.github.com/repos/<owner>/<repo>/commits` & `/issues?state=all&sort=updated` | Default-branch commits plus strictly separated `issues` vs `prs`, preserving `authorAssociation` to separate external user feedback from maintainers |
| `github_file` | `https://api.github.com/repos/<owner>/<repo>/contents/<path>` (or `/readme`) | Blob SHA and normalized lines for README or key manifests so doc edits are not mistaken for feature releases |
| `github_trending` | `https://github.com/trending[/<language>]?since=daily\|weekly\|monthly` | Full ordered trending board with row-completeness checks (fails closed as `parse_error` if partial, preventing false drop alerts) |
| `producthunt` | Official GraphQL (`PRODUCTHUNT_TOKEN` optional) with zero-key Atom feed fallback (`https://www.producthunt.com/feed`) | Daily launches; GraphQL separates `commentsCount` (launch comments) from `reviewsCount` (product reviews) |
| `appstore_ios` | `https://itunes.apple.com/lookup?id=<appId>` (or `bundleId`) | Live iOS version, release notes, rating average & review count |
| `npm` | `https://registry.npmjs.org/<package>/latest` | Exact latest package version, dependencies, publish signals |
| `pypi` | `https://pypi.org/pypi/<package>/json` | Exact latest Python release version and metadata |
| `greenhouse_jobs` | `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` | Live hiring headcount, departments, and new role titles |
| `ashby_jobs` | `https://api.ashbyhq.com/posting-api/job-board/<slug>` | Live hiring signals for Ashby-hosted startups |
| `lever_jobs` | `https://api.lever.co/v0/postings/<slug>?mode=json` | Live hiring signals for Lever-hosted companies |
| `sec_edgar` | `https://data.sec.gov/submissions/CIK<10-digit>.json` | Official US SEC filings (10-K, 10-Q, 8-K, S-1) with compliant User-Agent |
| `hn_algolia` | `https://hn.algolia.com/api/v1/search_by_date?query=<q>&tags=story` | Live Hacker News community mentions and point/comment velocity |

## Priority 3: Computer Use Fallback, Web Search & Local Documents

Use Priority 3 when a source sits behind login walls, paywalls, or anti-bot gates where no Connector or public API exists:

- **Computer Use (final fallback for gated/restricted sites)**:
  - Applies to authenticated member articles (e.g., paywalled Medium stories), login-only communities, Product Hunt deep reviews/launch threads behind Cloudflare, or interactive JS pricing calculators.
  - Operates inside the user's already-authenticated desktop/browser session via Ducoro Computer Use—**never extract browser cookies, call undocumented private APIs, or bypass CAPTCHAs/anti-bot gates**. Pause immediately for human login or verification when prompted.
  - **Availability boundary**: Computer Use requires an unlocked desktop host with Computer Use enabled and a supported agent runtime. Never schedule unattended overnight runs that silently skip Computer Use sources—if unavailable or locked, explicitly report `skipped / uncovered` instead of `no_material_change`.
  - **Paywall hygiene**: Record only verifiable metadata, URL, timestamp, and short verbatim quotes (or local notes/screenshots under `<data-dir>` or Space `files/`); never dump full copyrighted paywalled articles into version-controlled repos.
- **Built-in `web_search` / `web_fetch`**: Use for primary press releases, investor-relations pages, or corroborating public coverage.
- **Local Documents**: Human-supplied filings, earnings transcripts, decks, or call notes live under `<data-dir>/entities/<slug>/local-docs/`.

## Grounding Priority 1 & Priority 3 Findings Through `evidence_gate.py`

All three source tiers flow through the exact same deterministic evidence gate so no tier bypasses verification:

1. **Append Connector, Computer Use, Web Fetch, or Browser records into `market-intel-signal/1`**:
   Write a capture shard (e.g., `<data-dir>/captures/external.json`) using `schemaVersion: "market-intel-signal/1"` with `ok: true`, the exact `entitySlug`, a descriptive `kind` (e.g., `"connector:reddit"`, `"connector:x"`, `"connector:github"`, `"computer_use"`, `"browser"`, `"web_fetch"`), the real `url`, ISO `observedAt`, and `structured` containing the verbatim observed excerpt (`lines` or `excerpt`). Merge it with public captures via:
   ```sh
   python3 scripts/fetch_sources.py <data-dir> \
     --merge <data-dir>/captures/keyless.json <data-dir>/captures/external.json \
     --out <data-dir>/captures/latest.json
   ```
2. **Cite human-supplied local documents or Computer Use notes via `localRef`**:
   Store the source file inside `<data-dir>` (typically `entities/<slug>/local-docs/<filename>.txt` or `.md`) and set `"localRef": "entities/<slug>/local-docs/<filename>.txt"` on the candidate claim (with or without `evidenceUrls`). `scripts/evidence_gate.py` verifies that `localRef` stays inside `<data-dir>`, exists on disk, counts `local_doc` as a distinct `sourceKind` for triangulation, and checks that the normalized `quote` appears verbatim in the file or referenced capture record.
