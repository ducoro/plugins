---
name: platform-kuaishou
description: "Run Kuaishou (Kwai) end-to-end short-video operations: relatable practical topic selection, direct vertical video scripting, spec validation, Kuaishou OpenAPI chunked upload and publish polling, community engagement, and repeat-viewer retrospectives."
---

# Kuaishou (Kwai) Operations Playbook

Kuaishou combines fair-reach discovery with strong community loyalty ("老铁" repeat viewers). Clear, grounded, unpretentious delivery consistently outperforms glossy corporate ads.

## 1. Topic Discovery (Platform-Native)
- **Community signals**: Kuaishou hot lists, practical hands-on questions from comments, real workplace/daily-life demonstrations, and straightforward tool/product comparisons.
- **Winning angles**: plain-spoken tutorials, real demonstrations without jargon, candid pros/cons tests, and serialized episodes that encourage following.

## 2. Native Content & Script Structure
- **0–3s Direct Opening**: state the exact problem or visual result right away in plain everyday language.
- **Video**: `9:16` vertical (`mp4`/`mov`/`mkv`/`avi`/`webm`, OpenAPI baseline `<= 100 MB`, `<= 1800s`; sweet spot 30–90s).
- **Copy**: title `<= 30` chars, total text `<= 1000` chars, max **4** `#topic` tags. Provide a clear cover frame with large legible text.

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate against `references/specs.json` via `check_media_specs.py`.
2. **Default zero-config path (Official Browser Studio)**: open `https://cp.kuaishou.com/article/publish/video` in the user's browser session (pause for login/CAPTCHA if needed), upload local video & cover from `drafts/<id>/assets/`, fill caption and `#topic` tags, save draft (`draft_saved`) or pause before **发布** until Gate 2 confirmation, then read back the live URL from **作品管理**.
3. **Optional official OpenAPI path** (requires `KUAISHOU_APP_ID` & `KUAISHOU_ACCESS_TOKEN`): start upload via `scripts/client.py start-upload`, upload binary fragments and publish per `references/protocol.md`, and verify via `scripts/client.py photo-info --photo-id <id>` (`user-info` and `photo-list` also available).
4. Record verified `https://www.kuaishou.com/short-video/<photoId>` in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- Respond warmly and concretely to questions in comments; strong repeat commenter engagement feeds Kuaishou's follower tab.
- Stay under 40 actions/day and avoid off-platform contact spam or exaggerated claims.

## 5. North-Star Metrics (`platformMetrics`)
Track `completionRate`, `followerViewShare`, `commentRate`, and `profileFollowConversion`.
