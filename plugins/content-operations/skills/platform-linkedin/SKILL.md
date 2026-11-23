---
name: platform-linkedin
description: "Run LinkedIn end-to-end operations: B2B practitioner topic discovery, high-dwell structured posts and media uploads, LinkedIn REST Posts API publishing and comment workflows, and dwell-time plus peer-comment retrospectives."
---

# LinkedIn Operations Playbook

LinkedIn rewards practitioner credibility, dwell time ("See more" expansion + time spent reading), and substantive comments from peers in the same industry.

## 1. Topic Discovery (Platform-Native)
- **B2B & operator signals**: real shipping postmortems, architecture/process trade-offs, hiring/org lessons, concrete ROI numbers, and contrarian field notes.
- **Avoid**: hollow motivational clichés, broetry one-word-per-line formatting, or hard sales pitches.

## 2. Native Content & Format Rules
- **Body (`<= 3000` chars; sweet spot 800–1600 chars)**: lines 1–2 must earn the "See more" click with a specific observation or concrete result; use crisp short paragraphs and bulleted takeaways.
- **Media**: `text`, `image_text` (up to **9** images `jpg`/`png`/`gif`, `<= 10 MB` each), or `video` (`mp4`, `<= 200 MB`, `<= 600s`).
- **Topics**: no separate API topic field; 0–3 relevant inline hashtags max.
- **Schedule**: weekday business mornings (`08:00–10:30` target audience local time, Tue–Thu strongest).

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate against `references/specs.json` with `check_media_specs.py`.
2. **Default zero-config path (Official LinkedIn Web Composer)**: open `https://www.linkedin.com/feed/` in the user's browser session (pause for sign-in/2FA if prompted), click **Start a post**, upload local images/video/document directly from `drafts/<id>/assets/`, paste formatted copy, save draft (`draft_saved`) or pause before **Post** until Gate 2 confirmation, then copy the live post URL.
3. **Optional official REST API path** (requires `LINKEDIN_ACCESS_TOKEN` & `LINKEDIN_AUTHOR_URN`; sends active `LinkedIn-Version`, default `202601`):
   - Upload a local image via `scripts/client.py [--dry-run] upload-image --file <path>` (returns `imageUrn`), then publish via `scripts/client.py post --text ... [--image-urn <urn>] [--alt-text ...] [--visibility PUBLIC|CONNECTIONS]` (multi-image/video upload endpoints in `references/protocol.md`).
   - Capture the returned `postUrn` (`x-restli-id`) and verify via `userinfo` / `list-comments` / `comment`.
4. Record `https://www.linkedin.com/feed/update/<urn>` in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- `scripts/client.py` supports `list-comments --post-urn <urn>` and `comment --post-urn <urn> --text ...` (comment deletion follows `references/protocol.md`).
- Engage thoughtfully with peer comments within 2 hours; keep total actions under 40/day.

## 5. North-Star Metrics (`platformMetrics`)
Track `seeMoreClickRate`, `substantiveCommentCount`, `repostCount`, and `profileViewsFromPost`. Note: LinkedIn's Member API does not expose personal-profile post analytics—log exported/manual numbers with `source: "manual"` for personal accounts, or use `organizationalEntityShareStatistics` for Organization Pages (see `references/protocol.md`).
