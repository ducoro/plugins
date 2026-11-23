#!/usr/bin/env python3
"""Zero-dependency OKLCH color math, WCAG 2.1 contrast engine, and preset themes for visual social cards."""
from __future__ import annotations

import math
import re
from typing import Dict, List, Tuple

HEX_RE = re.compile(r'^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')

STYLES: Dict[str, Dict[str, object]] = {
    'paper-studio': {
        'label': 'Paper Studio',
        'mode': 'light',
        'defaultTheme': 'warm-linen',
        'description': 'Warm tactile paper base, serif display headlines, generous editorial rhythm.',
        'brandBounds': {'L': (0.34, 0.50), 'C': (0.07, 0.16)},
    },
    'grid-spec': {
        'label': 'Grid Spec',
        'mode': 'light',
        'defaultTheme': 'cobalt-grid',
        'description': 'Precision hairline grid, crisp sans display (lighter at larger scale), monospace indices, one vivid accent.',
        'brandBounds': {'L': (0.38, 0.54), 'C': (0.12, 0.24)},
    },
    'darkroom-frame': {
        'label': 'Darkroom Frame',
        'mode': 'dark',
        'defaultTheme': 'obsidian-gold',
        'description': 'Deep charcoal canvas, warm silver typography, subtle tonal borders for dark UI, hardware, and photography.',
        'brandBounds': {'L': (0.72, 0.86), 'C': (0.08, 0.17)},
    },
}

THEMES: Dict[str, Dict[str, str]] = {
    # Paper Studio (4 light tactile palettes)
    'warm-linen': {
        'style': 'paper-studio',
        'label': 'Warm Linen',
        'bg': '#F6F2EA',
        'surface': '#FFFDF8',
        'ink': '#1B1917',
        'muted': '#575149',
        'accent': '#9E3B28',
        'accentInk': '#FFFFFF',
        'accentSoft': '#F3E3DC',
        'border': '#DDD4C6',
        'tintRgb': '27, 25, 23',
    },
    'celadon-ink': {
        'style': 'paper-studio',
        'label': 'Celadon Ink',
        'bg': '#EEF3F1',
        'surface': '#F9FCFB',
        'ink': '#132522',
        'muted': '#425B56',
        'accent': '#1F6357',
        'accentInk': '#FFFFFF',
        'accentSoft': '#DCEBE7',
        'border': '#C7D7D2',
        'tintRgb': '19, 37, 34',
    },
    'slate-ivory': {
        'style': 'paper-studio',
        'label': 'Slate Ivory',
        'bg': '#F2F4F7',
        'surface': '#FFFFFF',
        'ink': '#141B29',
        'muted': '#4A5568',
        'accent': '#274C8F',
        'accentInk': '#FFFFFF',
        'accentSoft': '#E0E8F6',
        'border': '#CFD8E3',
        'tintRgb': '20, 27, 41',
    },
    'oat-umber': {
        'style': 'paper-studio',
        'label': 'Oat Umber',
        'bg': '#F2E9DC',
        'surface': '#FAF4EB',
        'ink': '#241911',
        'muted': '#5B4737',
        'accent': '#8A4519',
        'accentInk': '#FFFFFF',
        'accentSoft': '#EAD9C5',
        'border': '#D9C7B1',
        'tintRgb': '36, 25, 17',
    },
    # Grid Spec (4 high-contrast technical palettes)
    'cobalt-grid': {
        'style': 'grid-spec',
        'label': 'Cobalt Grid',
        'bg': '#F7F8FA',
        'surface': '#FFFFFF',
        'ink': '#0F172A',
        'muted': '#475569',
        'accent': '#1D4ED8',
        'accentInk': '#FFFFFF',
        'accentSoft': '#E0E7FF',
        'border': '#CBD5E1',
        'tintRgb': '15, 23, 42',
    },
    'vermilion-spec': {
        'style': 'grid-spec',
        'label': 'Vermilion Spec',
        'bg': '#F9F8F6',
        'surface': '#FFFFFF',
        'ink': '#18181B',
        'muted': '#52525B',
        'accent': '#C42E1B',
        'accentInk': '#FFFFFF',
        'accentSoft': '#FCE5E1',
        'border': '#D4D4D8',
        'tintRgb': '24, 24, 27',
    },
    'emerald-lab': {
        'style': 'grid-spec',
        'label': 'Emerald Lab',
        'bg': '#F5F8F6',
        'surface': '#FFFFFF',
        'ink': '#0F1F18',
        'muted': '#3F594D',
        'accent': '#0F764A',
        'accentInk': '#FFFFFF',
        'accentSoft': '#DCF2E7',
        'border': '#C5D8CE',
        'tintRgb': '15, 31, 24',
    },
    'amber-signal': {
        'style': 'grid-spec',
        'label': 'Amber Signal',
        'bg': '#F8F7F4',
        'surface': '#FFFFFF',
        'ink': '#171512',
        'muted': '#544D44',
        'accent': '#A64B07',
        'accentInk': '#FFFFFF',
        'accentSoft': '#FDEFD8',
        'border': '#D9D2C7',
        'tintRgb': '23, 21, 18',
    },
    # Darkroom Frame (3 dark editorial palettes)
    'obsidian-gold': {
        'style': 'darkroom-frame',
        'label': 'Obsidian Gold',
        'bg': '#111214',
        'surface': '#1A1C20',
        'ink': '#F2ECE1',
        'muted': '#A9A297',
        'accent': '#E2B15B',
        'accentInk': '#14120E',
        'accentSoft': '#2A2419',
        'border': '#2E3138',
        'tintRgb': '17, 18, 20',
    },
    'midnight-cyan': {
        'style': 'darkroom-frame',
        'label': 'Midnight Cyan',
        'bg': '#0D131A',
        'surface': '#151E28',
        'ink': '#E8F0F7',
        'muted': '#98AAB9',
        'accent': '#56CCF2',
        'accentInk': '#08131A',
        'accentSoft': '#142B38',
        'border': '#253545',
        'tintRgb': '13, 19, 26',
    },
    'plum-velvet': {
        'style': 'darkroom-frame',
        'label': 'Plum Velvet',
        'bg': '#161118',
        'surface': '#211924',
        'ink': '#F4ECF5',
        'muted': '#B6A6BC',
        'accent': '#E091B8',
        'accentInk': '#1B0E16',
        'accentSoft': '#311F2D',
        'border': '#382A3D',
        'tintRgb': '22, 17, 24',
    },
}


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def parse_hex(raw: str) -> Tuple[float, float, float]:
    """Parse #RGB or #RRGGBB into normalized [0, 1] sRGB floats."""
    if not isinstance(raw, str):
        raise ValueError('Hex color must be a string')
    m = HEX_RE.match(raw.strip())
    if not m:
        raise ValueError(f'Invalid hex color: {raw!r} (expected #RGB or #RRGGBB)')
    h = m.group(1)
    if len(h) == 3:
        h = ''.join(ch * 2 for ch in h)
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def to_hex(rgb: Tuple[float, float, float]) -> str:
    r, g, b = (round(clamp(c, 0.0, 1.0) * 255) for c in rgb)
    return f'#{r:02X}{g:02X}{b:02X}'


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    if c <= 0.0:
        return 0.0
    if c >= 1.0:
        return 1.0
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def relative_luminance(rgb: Tuple[float, float, float]) -> float:
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """Compute WCAG 2.1 contrast ratio between two hex colors."""
    la = relative_luminance(parse_hex(hex_a))
    lb = relative_luminance(parse_hex(hex_b))
    hi, lo = (la, lb) if la >= lb else (lb, la)
    return (hi + 0.05) / (lo + 0.05)


def rgb_to_oklch(rgb: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Convert normalized sRGB to OKLCH (L in [0,1], C >= 0, H in degrees [0,360))."""
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    l_ = math.copysign(abs(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1.0 / 3.0),
                       0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = math.copysign(abs(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1.0 / 3.0),
                       0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = math.copysign(abs(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1.0 / 3.0),
                       0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_val = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    C = math.hypot(a, b_val)
    H = math.degrees(math.atan2(b_val, a)) % 360.0
    return (L, C, H)


def _oklch_to_linear_rgb(L: float, C: float, H: float) -> Tuple[float, float, float]:
    rad = math.radians(H)
    a = C * math.cos(rad)
    b_val = C * math.sin(rad)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b_val
    m_ = L - 0.1055613458 * a - 0.0638541728 * b_val
    s_ = L - 0.0894841775 * a - 1.2914855480 * b_val
    l3, m3, s3 = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
    g = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
    b = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3
    return (r, g, b)


def _in_srgb_gamut(rgb_lin: Tuple[float, float, float]) -> bool:
    eps = 1e-6
    return all(-eps <= c <= 1.0 + eps for c in rgb_lin)


def oklch_to_gamut_hex(L: float, C: float, H: float) -> str:
    """Gamut-map OKLCH into sRGB by bisecting chroma C while preserving L and H."""
    L = clamp(L, 0.0, 1.0)
    C = max(0.0, C)
    lin = _oklch_to_linear_rgb(L, C, H)
    if _in_srgb_gamut(lin):
        return to_hex(tuple(_linear_to_srgb(c) for c in lin))
    lo, hi = 0.0, C
    for _ in range(28):
        mid = (lo + hi) * 0.5
        if _in_srgb_gamut(_oklch_to_linear_rgb(L, mid, H)):
            lo = mid
        else:
            hi = mid
    lin = _oklch_to_linear_rgb(L, lo, H)
    return to_hex(tuple(_linear_to_srgb(c) for c in lin))


def evaluate_palette_contrast(palette: Dict[str, str]) -> Dict[str, object]:
    """Check WCAG 2.1 contrast thresholds for a complete theme token set."""
    checks = {
        'ink_on_bg': (contrast_ratio(palette['ink'], palette['bg']), 7.0),
        'ink_on_surface': (contrast_ratio(palette['ink'], palette['surface']), 7.0),
        'muted_on_bg': (contrast_ratio(palette['muted'], palette['bg']), 4.5),
        'muted_on_surface': (contrast_ratio(palette['muted'], palette['surface']), 4.5),
        'accent_on_bg': (contrast_ratio(palette['accent'], palette['bg']), 4.5),
        'accent_on_surface': (contrast_ratio(palette['accent'], palette['surface']), 4.5),
        'accentInk_on_accent': (contrast_ratio(palette['accentInk'], palette['accent']), 4.5),
    }
    failures = [
        {'pair': pair, 'ratio': round(ratio, 2), 'minRequired': req}
        for pair, (ratio, req) in checks.items()
        if ratio < req
    ]
    return {
        'passed': len(failures) == 0,
        'ratios': {pair: round(ratio, 2) for pair, (ratio, _) in checks.items()},
        'failures': failures,
    }


def build_brand_theme(hex_color: str, style: str, theme_id: str = 'brand') -> Dict[str, object]:
    """Derive a WCAG-safe brand theme for the chosen style while preserving hue."""
    if style not in STYLES:
        raise ValueError(f'Unknown style {style!r}; expected one of: {", ".join(STYLES)}')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', theme_id):
        raise ValueError(f'Invalid theme id {theme_id!r}; use lowercase kebab-case')

    rgb = parse_hex(hex_color)
    orig_L, orig_C, orig_H = rgb_to_oklch(rgb)
    base_name = str(STYLES[style]['defaultTheme'])
    base = dict(THEMES[base_name])
    mode = str(STYLES[style]['mode'])
    bounds = STYLES[style]['brandBounds']
    l_lo, l_hi = bounds['L']  # type: ignore[index]
    c_lo, c_hi = bounds['C']  # type: ignore[index]

    # Achromatic inputs (black/white/grey) stay neutral; chromatic inputs stay expressive.
    target_C = orig_C if orig_C < 0.025 else clamp(orig_C, c_lo, c_hi)
    target_L = clamp(orig_L, l_lo, l_hi)

    def _pick_accent_ink(acc_hex: str) -> str:
        c_white = contrast_ratio('#FFFFFF', acc_hex)
        c_dark = contrast_ratio('#111214', acc_hex)
        return '#FFFFFF' if c_white >= c_dark else '#111214'

    def _is_valid_accent(acc_hex: str) -> bool:
        ink_c = _pick_accent_ink(acc_hex)
        return (
            contrast_ratio(acc_hex, base['bg']) >= 4.5
            and contrast_ratio(acc_hex, base['surface']) >= 4.5
            and contrast_ratio(ink_c, acc_hex) >= 4.5
        )

    accent_hex = oklch_to_gamut_hex(target_L, target_C, orig_H)
    if not _is_valid_accent(accent_hex):
        # Search outward along lightness in the style's contrast direction.
        step = -0.015 if mode == 'light' else 0.015
        candidate_L = target_L
        found = None
        for _ in range(45):
            candidate_L = clamp(candidate_L + step, 0.14, 0.94)
            cand = oklch_to_gamut_hex(candidate_L, target_C, orig_H)
            if _is_valid_accent(cand):
                found = cand
                target_L = candidate_L
                break
        if found is None:
            # Final fallback: moderate chroma slightly while keeping hue.
            for scale in (0.75, 0.55, 0.35):
                c_try = target_C * scale
                l_try = 0.36 if mode == 'light' else 0.80
                for _ in range(30):
                    cand = oklch_to_gamut_hex(l_try, c_try, orig_H)
                    if _is_valid_accent(cand):
                        found = cand
                        target_L = l_try
                        target_C = c_try
                        break
                    l_try = clamp(l_try + step, 0.14, 0.94)
                if found is not None:
                    break
        if found is None:
            raise ValueError(f'Unable to satisfy WCAG 4.5:1 contrast for {hex_color} in style {style}')
        accent_hex = found

    accent_ink = _pick_accent_ink(accent_hex)
    soft_L = 0.93 if mode == 'light' else 0.22
    soft_C = min(target_C * 0.28, 0.045)
    accent_soft = oklch_to_gamut_hex(soft_L, soft_C, orig_H)

    palette = dict(base)
    palette['style'] = style
    palette['label'] = f'Brand ({theme_id})'
    palette['accent'] = accent_hex
    palette['accentInk'] = accent_ink
    palette['accentSoft'] = accent_soft

    report = evaluate_palette_contrast(palette)
    if not report['passed']:
        raise ValueError(f'Generated brand theme failed contrast audit: {report["failures"]}')

    css = (
        f'html[data-style="{style}"][data-theme="{theme_id}"] {{\n'
        f'  --bg: {palette["bg"]};\n'
        f'  --surface: {palette["surface"]};\n'
        f'  --ink: {palette["ink"]};\n'
        f'  --muted: {palette["muted"]};\n'
        f'  --accent: {palette["accent"]};\n'
        f'  --accent-ink: {palette["accentInk"]};\n'
        f'  --accent-soft: {palette["accentSoft"]};\n'
        f'  --border: {palette["border"]};\n'
        f'  --tint-rgb: {palette["tintRgb"]};\n'
        f'}}'
    )
    return {
        'style': style,
        'themeId': theme_id,
        'inputHex': to_hex(rgb),
        'palette': palette,
        'contrast': report,
        'css': css,
    }


def list_themes_report() -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for theme_id, palette in THEMES.items():
        out.append({
            'id': theme_id,
            'style': palette['style'],
            'label': palette['label'],
            'palette': palette,
            'contrast': evaluate_palette_contrast(palette),
        })
    return out
