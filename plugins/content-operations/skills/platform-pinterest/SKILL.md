---
name: platform-pinterest
description: Run Pinterest end-to-end visual search operations: evergreen search-keyword Pin planning, 2:3 vertical Pin and destination-link packaging, Pinterest API v5 board/Pin publishing and updates, and outbound-click plus save retrospectives.
---

# Pinterest Operations Playbook

Pinterest is a long-tail visual search engine, not a real-time social feed. A single well-indexed `2:3` Pin with clear keyword placement and a matching landing URL can compound saves and outbound clicks for months.

## 1. Topic Discovery (Platform-Native)
- **Visual search signals**: Pinterest Trends, search bar keyword completions, seasonal planning spikes (Pinterest users search 30–60 days ahead of holidays), and evergreen how-to checklists.
- **Winning angles**: clean infographics, step-by-step visual guides, product/workspace inspiration, templates, and high-contrast comparison charts that link to a genuinely matching landing page.

## 2. Native Content & Packaging Structure
- **Visual ratio**: `2:3` vertical (`1000x1500`) optimal; supports `jpg`/`jpeg`/`png`/`webp`/`bmp`/`tiff` (`<= 20 MB`, 1 image per Pin) or `mp4`/`mov`/`m4v` video (`<= 300s`).
- **Title (`<= 100` chars)**: front-load the exact visual search phrase.
- **Description (`<= 800` chars)**: natural keyword-rich summary explaining what the reader gets on click; no hashtag spam (no native topic field).
- **Required destination**: always attach a valid `board_id` (from `GET /v5/boards`) and matching HTTPS `link` when driving traffic.

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate against `references/specs.json` via `check_media_specs.py` (enforces `options.board_id` for API mode).
2. **Default zero-config path (Official Pin Creation Tool)**: open `https://www.pinterest.com/pin-creation-tool/` in the user's browser session (pause for login/2FA if prompted), upload the local `2:3` image or video directly from `drafts/<id>/assets/`, fill title, description, destination link, alt text, and board, save draft (`draft_saved`) or pause before **Publish** until Gate 2 confirmation, then record the live Pin URL.
3. **Optional official API v5 path** (requires `PINTEREST_ACCESS_TOKEN`):
   - Query boards via `scripts/client.py list-boards` to get `board_id`.
   - Just before publishing, upload the local image via `ducoro-cli media upload <local-file> --json` to get a 5-hour temporary `publicUrl` (on non-Ducoro hosts, use your own HTTPS storage/CDN).
   - Use `scripts/client.py`: `create-pin`, `get-pin`, `update-pin`, and `pin-analytics` (video Pins follow `references/protocol.md`).
4. Record verified `https://www.pinterest.com/pin/<pinId>` in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- Never point multiple spammy duplicate Pins at broken or mismatched URLs—Pinterest penalizes low-trust domains.
- Keep Pin frequency steady (e.g., 1–5 fresh Pins/day) rather than dumping 50 in one hour.

## 5. North-Star Metrics (`platformMetrics`)
Track `outboundClickRate`, `saveRate`, `pinClicks`, and `30DayCompoundingImpressions`.
