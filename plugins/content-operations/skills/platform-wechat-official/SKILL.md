---
name: platform-wechat-official
description: Run WeChat Official Account (公众号) end-to-end operations: deep long-form topic selection, scannable HTML article authoring and cover specs, Official Account API draft-box and freepublish workflows, and open-rate plus share retrospectives.
---

# WeChat Official Account (公众号) Operations Playbook

WeChat Official Accounts serve high-trust, private-domain subscribers and WeChat Search readers. Distribution hinges on headline open rate, finish-reading rate, and forwarding to chats/Moments.

## 1. Topic Discovery (Platform-Native)
- **Trust & depth signals**: WeChat Search ("搜一搜") long-tail queries, high-forward industry essays, recurring reader replies in backend messages, and authoritative release/methodology deep dives.
- **Winning angles**: complete guides worth bookmarking, candid founder/practitioner retrospectives, structured industry analysis, and clear product changelogs.

## 2. Native Content & HTML Structure
- **Title (`<= 64` chars; sweet spot 16–28 Chinese chars)**: clear value proposition without cheap clickbait (which destroys finish rate and triggers unfollows).
- **Cover (`2.35:1` primary `900x383` + `1:1` secondary share thumb)**: clean visual, readable when forwarded to a chat card.
- **Body (`<= 20000` chars, HTML)**: short paragraphs (3–4 lines max on mobile), clear section headings, callout boxes, inline charts/screenshots (up to 20 images, `<= 10 MB` each), explicit `digest` (`<= 120` chars) and `author` (`<= 8` chars).
- **Topics**: no native `#topic` field in API; use WeChat article collections ("合集") in MP backend for series navigation.

## 3. Publishing & Verification (`references/protocol.md`)
1. Validate copy and images against `references/specs.json` via `check_media_specs.py`.
2. **Default zero-config path (Official MP Web Backend)**: open `https://mp.weixin.qq.com/` (pause for QR scan if needed), open **内容管理 → 草稿箱 → 新的创作**, paste formatted HTML/images and `2.35:1` cover directly from local `drafts/<id>/assets/`, save draft (`draft_saved`) for mobile preview at Gate 2, then publish/broadcast only after explicit human confirmation and record the verified `article_url`.
3. **Optional official API path** (requires `WECHAT_OFFICIAL_APP_ID`, `WECHAT_OFFICIAL_APP_SECRET`, and `WECHAT_OFFICIAL_ACCESS_TOKEN`):
   - Rotate expired 2h tokens via `scripts/client.py get-token`.
   - Upload inline images via `scripts/client.py upload-image --file <path>` and cover via `scripts/client.py upload-thumb --file <path>`.
   - Stage draft via `scripts/client.py add-draft ...`, pause at Gate 2 for mobile preview, then publish via `submit-publish` + `poll-publish` and pull analytics via `user-read`, `user-cumulate`, `article-total`.

## 4. Engagement & Risk Guardrails
- Configure `need_open_comment` and `only_fans_can_comment` per post sensitivity.
- Pin helpful author replies in the comment section; move recurring reader questions into `inbox/`.
- Respect WeChat original-declaration rules and avoid prohibited medical/financial promises or external download redirects.

## 5. North-Star Metrics (`platformMetrics`)
Track `openRate`, `finishReadingRate`, `shareToChatCount`, `momentsShareCount`, and `netFollowerDelta` (via `/datacube/getarticletotal`, `/datacube/getarticlesummary`, `/datacube/getuserread`, and `/datacube/getusercumulate`).
