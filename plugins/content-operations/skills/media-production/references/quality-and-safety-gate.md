# Pre-Publish Quality & Safety Gate

Run this checklist before moving any draft from `in_review` to `ready` or scheduling it at Gate 2.

## 1. Factual & Source Integrity
- Every number, date, product capability, and price in every variant matches `master.md` and is still accurate today.
- All links resolve (HTTP 200) and point to the intended canonical page.
- Any illustrative mockup or sample data is explicitly labeled as an example.

## 2. Spec & Media Integrity
- `python3 scripts/check_media_specs.py <draft-dir>` exits `0` with zero blocking issues.
- No mixed images + video on platforms that forbid mixed media.
- Cover images are legible at thumbnail scale with no clipped text in platform UI safe zones.
- No leftover placeholder text (`TODO`, `TBD`, `[insert link]`, template names).

## 3. Content Safety & Compliance
- **No minors**: never depict or generate children or individuals who appear under 18 in promotional visuals, video prompts, or scripts.
- **No fabricated endorsements**: never fabricate testimonials, logos, or partner claims.
- **Disclosure**: set platform AIGC / paid-partnership flags (`is_aigc`, `made_with_ai`, `paid_partnership`, `brand_content_toggle`) truthfully whenever applicable.
- **Copyright**: verify font, music, stock media, and repost rights before publishing; never strip creator watermarks from third-party content to repost as original.
- **Platform compliance**: avoid banned absolute/medical/financial-guarantee claims and off-platform diversion phrasing that triggers shadowbans (check the target `platform-<name>/SKILL.md`).
