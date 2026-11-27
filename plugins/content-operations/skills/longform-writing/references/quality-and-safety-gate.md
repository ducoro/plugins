# Pre-Publish Quality & Safety Gate

Run this checklist before moving any draft from `in_review` to `ready` or scheduling it at Gate 2.

## 1. Factual, Experience & Originality Integrity
- Every number, date, product capability, and price across variants matches `master.md` and remains accurate today.
- **Zero fabricated experiences**: no invented first-person anecdotes unless supplied by the operator.
- Links resolve cleanly (or are converted to numbered footnotes for WeChat Official Account HTML).
- Illustrative mockups or sample numbers are labeled clearly as examples.
- Optional physical telemetry: `scripts/check_writing_quality.py probe` reports objective length/paragraph/sentence/repeated-ngram stats (no subjective score); `similarity` checks whether multi-platform adaptations were natively rewritten instead of copy-pasted.
- For high-risk external releases or final long-form sign-off, complete isolated fresh read-only review via `ducoro-cli job dispatch` across orthogonal lenses (fact/provenance tracing, platform red lines/compliance, reader subtraction) before finalizing `assessment.json`.

## 2. Spec & Media Integrity
- `python3 ../content-ops-loop/scripts/check_media_specs.py <draft-dir>` exits `0` with zero blocking issues (includes unfinished placeholder detection).
- No mixed images + video on platforms that disallow mixed media.
- Cover images remain legible at thumbnail scale with no clipped text in platform UI safe zones.

## 3. Compliance, Copyright & Platform Rules
- **Child safety & consent**: comply strictly with platform child-safety rules and guardian consent laws; never generate or publish exploitative, unsafe, or non-consensual depictions of minors.
- **No fabricated endorsements**: never invent customer testimonials, partner logos, or official affiliations.
- **Truthful disclosure**: enable platform AIGC / sponsored / paid-partnership disclosures (`is_aigc`, `made_with_ai`, `paid_partnership`, `brand_content_toggle`) whenever applicable.
- **Copyright**: verify font, music, stock footage, and repost permissions; never strip creator watermarks from third-party work.
- **Platform red lines**: avoid prohibited absolute, medical, or guaranteed-return claims and banned off-platform diversion phrasing (check the target `platform-<name>/SKILL.md`).
