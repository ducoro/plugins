#!/usr/bin/env python3
"""Cold-start corpus analyzer & style profile initializer for style-playbook bootstrapping (zero dependencies)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

TONE_PERSONA_MAP = (
    (('casual', 'friend', 'chat', '轻松', '有趣', '朋友', '聊天'), 'midnight-friend'),
    (('warm', 'story', 'essay', '温暖', '共鸣', '故事', '治愈'), 'warm-editor'),
    (('sharp', 'commentary', 'opinion', '犀利', '锐评', '观点', '新闻'), 'sharp-journalist'),
    (('data', 'finance', 'research', '严谨', '数据', '研究', '财经'), 'cold-analyst'),
    (('humor', 'funny', 'satire', '幽默', '搞笑', '段子'), 'humor-storyteller'),
    (('code', 'dev', 'tutorial', '技术', '代码', '教程', '开发'), 'tech-coder'),
    (('industry', 'analysis', 'deep', '专业', '分析', '深度', '行业'), 'industry-observer'),
)


def infer_persona(tone: str) -> str:
    lower = tone.lower()
    for keywords, persona in TONE_PERSONA_MAP:
        if any(k in lower for k in keywords):
            return persona
    return 'industry-observer'


def load_corpus(corpus_dir: Path) -> list[dict]:
    if not corpus_dir.is_dir():
        return []
    articles: list[dict] = []
    files = sorted(list(corpus_dir.glob('*.md')) + list(corpus_dir.glob('*.txt')))
    for fp in files:
        text = fp.read_text(encoding='utf-8', errors='replace').strip()
        if not text:
            continue
        lines = text.splitlines()
        title = fp.stem
        for ln in lines:
            s = ln.strip()
            if s.startswith('# ') and not s.startswith('## '):
                title = s[2:].strip()
                break
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        h2_count = sum(1 for ln in lines if ln.strip().startswith('## '))
        char_count = len(re.sub(r'\s+', '', text))
        articles.append({
            'filename': fp.name,
            'title': title,
            'charCount': char_count,
            'paragraphCount': len(paragraphs),
            'h2Count': h2_count,
            'excerpt': text[:2500] + ('\n\n[...truncated...]' if len(text) > 2500 else ''),
        })
    return articles


def compute_stats(articles: list[dict]) -> dict:
    if not articles:
        return {'totalArticles': 0}
    title_lens = [len(a['title']) for a in articles if a['title']]
    chars = [a['charCount'] for a in articles]
    paras = [a['paragraphCount'] for a in articles]
    h2s = [a['h2Count'] for a in articles]
    return {
        'totalArticles': len(articles),
        'avgCharCount': round(sum(chars) / len(chars)),
        'minCharCount': min(chars),
        'maxCharCount': max(chars),
        'avgTitleLength': round(sum(title_lens) / len(title_lens), 1) if title_lens else 0.0,
        'titleLengthRange': f'{min(title_lens)}-{max(title_lens)}' if title_lens else 'N/A',
        'avgParagraphs': round(sum(paras) / len(paras), 1),
        'avgH2Count': round(sum(h2s) / len(h2s), 1),
    }


def init_style_profile(
    workspace: Path,
    *,
    name: str,
    industry: str,
    topics: list[str],
    tone: str,
    persona: str = '',
    theme: str = 'professional-clean',
    audience: str = '',
    author: str = '',
    blacklist_words: list[str] | None = None,
) -> dict:
    ws = workspace.expanduser().resolve()
    style_dir = ws / 'style'
    (style_dir / 'corpus').mkdir(parents=True, exist_ok=True)
    (style_dir / 'themes').mkdir(parents=True, exist_ok=True)

    chosen_persona = persona.strip() or infer_persona(tone)
    profile = {
        'version': 1,
        'name': name.strip(),
        'industry': industry.strip(),
        'targetAudience': audience.strip() or f'{industry.strip()} practitioners and readers',
        'topics': [t.strip() for t in topics if t.strip()],
        'tone': tone.strip(),
        'writingPersona': chosen_persona,
        'theme': theme.strip() or 'professional-clean',
        'author': author.strip() or name.strip(),
        'blacklistWords': [w.strip() for w in (blacklist_words or []) if w.strip()],
        'updatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    out_path = style_dir / 'style-profile.json'
    out_path.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'profilePath': str(out_path), 'corpusDir': str(style_dir / 'corpus'), 'profile': profile}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Bootstrap style-profile.json or analyze historical corpus batches for style-playbook.md.')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p_init = sub.add_parser('init-style', help='Initialize <workspace>/style/style-profile.json and corpus/ folder.')
    p_init.add_argument('--workspace', required=True, help='Path to content-ops workspace.')
    p_init.add_argument('--name', required=True, help='Brand or publication name.')
    p_init.add_argument('--industry', required=True, help='Primary vertical or domain.')
    p_init.add_argument('--topics', required=True, help='Comma-separated core topics.')
    p_init.add_argument('--tone', required=True, help='Desired editorial tone.')
    p_init.add_argument('--persona', default='', help='Optional explicit persona override.')
    p_init.add_argument('--theme', default='professional-clean', help='Default WeChat theme name.')
    p_init.add_argument('--audience', default='')
    p_init.add_argument('--author', default='')
    p_init.add_argument('--blacklist', default='', help='Comma-separated taboo words/phrases.')

    p_an = sub.add_parser('analyze', help='Analyze historical articles in <workspace>/style/corpus/ in batches.')
    p_an.add_argument('--workspace', required=True, help='Path to content-ops workspace.')
    p_an.add_argument('--corpus-dir', default='', help='Optional custom corpus directory override.')
    p_an.add_argument('--batch-size', type=int, default=10, help='Articles per analysis batch.')
    p_an.add_argument('--stats-only', action='store_true', help='Output aggregate corpus statistics only.')
    p_an.add_argument('--json', action='store_true', help='Print structured JSON output.')

    args = ap.parse_args(argv)
    if args.cmd == 'init-style':
        res = init_style_profile(
            Path(args.workspace),
            name=args.name,
            industry=args.industry,
            topics=args.topics.split(','),
            tone=args.tone,
            persona=args.persona,
            theme=args.theme,
            audience=args.audience,
            author=args.author,
            blacklist_words=args.blacklist.split(',') if args.blacklist else [],
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0

    ws = Path(args.workspace).expanduser().resolve()
    corpus_dir = Path(args.corpus_dir).expanduser().resolve() if args.corpus_dir else (ws / 'style' / 'corpus')
    articles = load_corpus(corpus_dir)
    if not articles:
        print(json.dumps({
            'ok': False,
            'corpusDir': str(corpus_dir),
            'error': 'No .md or .txt articles found in corpus directory.',
            'nextStep': f'Drop 5-30 historical articles into {corpus_dir} and rerun analyze.',
        }, indent=2, ensure_ascii=False))
        return 1

    stats = compute_stats(articles)
    batch_size = max(1, int(args.batch_size))
    batches = [articles[i:i + batch_size] for i in range(0, len(articles), batch_size)]
    payload = {
        'ok': True,
        'corpusDir': str(corpus_dir),
        'playbookTarget': str(ws / 'style' / 'style-playbook.md'),
        'stats': stats,
        'batchCount': len(batches),
        'batches': [] if args.stats_only else [
            {'batchIndex': i + 1, 'articleCount': len(b), 'articles': b}
            for i, b in enumerate(batches)
        ],
    }
    if args.json or args.stats_only:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f'Corpus: {stats["totalArticles"]} articles · avg {stats["avgCharCount"]} chars · title len {stats["titleLengthRange"]} · avg {stats["avgH2Count"]} H2s')
        for i, batch in enumerate(batches, start=1):
            print(f'\n=== BATCH {i}/{len(batches)} ({len(batch)} articles) ===')
            for art in batch:
                print(f'--- {art["filename"]}: {art["title"]} ({art["charCount"]} chars) ---')
                print(art['excerpt'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
