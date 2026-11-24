# Platform Visual Craft, Layout Trade-Offs & Cover Mechanics

Domain-specific platform visual facts and trade-offs so the agent can advise neutrally and match the user's goal rather than forcing a single style.

## 1. Platform Feed & Crop Mechanics (What Platforms Actually Do to Your Images)

- **Xiaohongshu (RedNote) dual-column feed**: covers appear at ~170–190px width on mobile with the note title directly underneath; `3:4` (`1080×1440`) occupies maximum vertical real estate without cropping. Inside the detail view, pagination dots sit at the bottom ~6%—keep critical captions above the bottom margin.
- **Instagram feed vs. profile grid**: feed favors `4:5` (`1080×1350`), while the modern profile grid crops thumbnails to `3:4`. Keeping key faces/titles inside the central `3:4` safe zone protects both surfaces.
- **X / Twitter multi-image grids**: single images render at `16:9` (`1200×675`) or `4:3`; 2 images crop side-by-side (`7:8` each); 4 images crop into a `2×2` `16:9` grid. Place text/subjects near center when posting multi-image sets.
- **WeChat Official Account cover pair (`2.35:1` + `1:1`)**: the `900×383` primary cover appears in the subscription list, while chat forwards, Moments, and secondary slots display a `1:1` (`1080×1080`) square. If only `2.35:1` is uploaded, WeChat center-crops it. Composing a dedicated `1:1` cover—either a short 4–10 char headline or a clean visual crop—prevents clipped text.
- **Compression gotchas**: platforms re-encode uploaded PNGs to JPEG with `4:2:0` chroma subsampling—saturated red/orange thin text on dark backgrounds blurs more easily than high-luminance contrast pairs.

## 2. Visual Style Spectrum & Conversion Trade-Offs

Different audiences and niches win with different visual styles—present trade-offs neutrally and follow the user's brand preference:

| Style Family | Typical Strengths | Best-Fit Goals & Niches |
|---|---|---|
| **Restrained Editorial / Magazine** (starter: `paper-studio`) | High trust, calm differentiation in noisy feeds, strong saves | Essays, travel guides, reading notes, lifestyle, design |
| **Structured Grid / Spec Sheet** (starter: `grid-spec`) | Fast scanning, clear hierarchy, high perceived rigor | Tool benchmarks, SOPs, tutorials, AI/product teardowns |
| **Dark Studio / Cinematic** (starter: `darkroom-frame`) | Highlights glowing UI, hardware, night/gaming/film visuals | Dark-mode software, hardware reviews, film & gaming |
| **Bold Headline / Big-Type Poster** | High scroll-stop CTR in dual-column feeds | Hot takes, pitfall warnings, career/exam tips, checklists |
| **Photo-Led / Aesthetic / Plog / Collage** | High authenticity, emotional resonance, strong likes & follows | Travel diaries, OOTD, food, home decor, personal stories |

## 3. Image Sourcing & Text-on-Image Practical Guidance

- **Evidence & asset options**: when a user provides text only, offer clear options once—(A) user's own photos/screenshots, (B) `image_generate` for illustrations/artwork without dense small CJK text, or (C) free-tier stock/web images downloaded into local `assets/` with provenance logged in `assets/SOURCES.md` and copyright status disclosed to the user.
- **Text over photos**: inspect where faces, products, or focal action sit before placing typography; set explicit `object-position` so tall/wide crops never slice faces. If a photo has a calm quiet zone, clean type without a mask preserves depth; if the background is busy, a localized gradient or soft atmospheric scrim keeps headlines legible at mobile thumbnail width (~360px).
- **UI screenshots**: keep text legible with `object-fit: contain` (avoid cropping sidebars or labels); optional browser/phone framing (`.device-browser` / `.device-phone`) helps separate light screenshots from light canvases.
- **Vertical rhythm (`3:4`)**: avoid unintentional empty lower thirds on thin bullet lists (either tighten the deck or give charts/screenshots/quotes room to breathe), while remembering that deliberate negative space is completely valid for minimalist quotes or photo-led covers.
