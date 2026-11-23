---
name: platform-wechat-channels
description: "Run WeChat Channels (视频号) end-to-end operations: social-graph shareable topic selection, crisp 16-char short-title video packaging, browser-based Creator Studio draft staging with human publish confirmation, and forward-rate retrospectives."
---

# WeChat Channels (视频号) Operations Playbook

WeChat Channels combines interest recommendations with WeChat social-graph amplification—every "Like (♥)" or forward to a WeChat group directly exposes the video to the viewer's real-life network.

## 1. Topic Discovery (Platform-Native)
- **Social-currency signals**: topics a viewer feels proud or helpful sharing into a work/family/founder group; practical explanations, clear insights, and relatable industry stories.
- **Synergy**: cross-link with your WeChat Official Account articles and private-domain communities.

## 2. Native Content & Packaging Structure
- **Short title (`<= 16` chars)**: WeChat Channels displays a tight short title in Moments/chat cards—make every character carry the hook.
- **Description (`<= 1000` chars)**: clear context + 3–5 native `#topic` tags + optional Official Account article link.
- **Video**: `9:16` vertical (preferred) or `16:9` horizontal (`mp4`/`mov`/`mkv`, `<= 1 GB`, `<= 3600s`; sweet spot 45–150s with clear subtitles for muted autoplay).

## 3. Publishing & Verification (`references/protocol.md`)
- General creator posting runs via **WeChat Channels Creator Studio** (`channels.weixin.qq.com`) using a tool-agnostic browser workflow (no open general posting API without enterprise Channels EC/partner qualifications):
  1. Validate with `check_media_specs.py` against `references/specs.json`.
  2. Upload video, set cover, short title (`<= 16` chars), description (`<= 1000` chars), `#topic` tags, and optional schedule in Creator Studio.
  3. **Save draft** and pause at Gate 2 for human review/publish confirmation.
  4. Read back the published work ID/link from **动态管理** and log it in `publish-log.jsonl`.

## 4. Engagement & Risk Guardrails
- Reply promptly to early comments (social-graph commenters are often real connections or high-trust leads).
- Keep browser interactions gentle (max 30–40 actions/day, 6–8/hour, 90–180s spacing); stop on any WeChat scan/verification gate.

## 5. North-Star Metrics (`platformMetrics`)
Track `forwardCount` (chat/Moments shares), `recommendationShareRate` (♥), `completionRate`, and `officialAccountClickThrough`.
