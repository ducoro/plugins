"""End-to-end tests for WeChat formatting/validation, WeChat client staging/newspic/get-draft, writing quality, and edit learning."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'plugins' / 'content-operations' / 'skills'
WECHAT_SCRIPTS = SKILLS / 'platform-wechat-official' / 'scripts'
MEDIA_SCRIPTS = SKILLS / 'longform-writing' / 'scripts'
CN_RADAR_SCRIPTS = SKILLS / 'topic-research-cn' / 'scripts'
GLOBAL_RADAR_SCRIPTS = SKILLS / 'topic-research-global' / 'scripts'


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WeChatFormattingAndWritingTest(unittest.TestCase):
    def test_render_wechat_html_all_themes_containers_fixes_and_aigc_default_off(self):
        md_sample = """```json
{"platform": "wechat-official", "mode": "image_text", "title": "微信排版实测"}
```

# 微信排版实测

正文里混排AI工具2026年实测，注意**核心结论：**别再手动调格式。

查看[官方文档](https://example.com/docs)和[站内文章](https://mp.weixin.qq.com/s/demo123)。

## 第一节 列表与组件

- 第一条要点
- 第二条要点

1. 步骤一
2. 步骤二

:::callout tip
先看本地预览，再决定是否推草稿箱。
:::

:::steps
**准备素材** 放进草稿 assets 目录
**执行渲染** 自动内联全部样式
:::

:::timeline
**Day 1** 选题评审
**Day 2** 成稿与排版
:::

:::pullquote
好排版让长文读完率直接翻倍
:::

:::label pill
重点提示
:::

:::quote
慢即是快。
:::

:::dialogue
读者：复制进微信会掉样式吗？
> 作者：全内联加暗黑模式属性，直接粘不掉。
:::

:::highlight
关键边界：默认不附带 AIGC 声明。
:::

:::summary
- 样式全内联
- 外链转脚注
:::

![演示动图](assets/demo.gif)

| 列1 | 列2 | 列3 | 列4 | 列5 |
| --- | --- | --- | --- | --- |
| a | b | c | d | e |

```python
def hello():
    return "ok"
```
"""
        rwh = load_module(WECHAT_SCRIPTS / 'render_wechat_html.py', 'render_wechat_html_mod')
        themes = rwh.load_themes()
        self.assertEqual(len(themes), 18)

        for tname, theme in themes.items():
            with self.subTest(theme=tname):
                res = rwh.WeChatRenderer(theme).convert(md_sample)
                issues = rwh.validate_wechat_html(res['html'])
                errors = [i for i in issues if i['level'] == 'ERROR']
                self.assertEqual(errors, [], f'{tname} produced validation errors: {errors}')
                self.assertIn('混排 AI 工具 2026 年', res['html'])
                self.assertIn('</strong>：', res['html'])
                self.assertIn('[1]', res['html'])
                self.assertIn('https://example.com/docs', res['html'])
                self.assertIn('href="https://mp.weixin.qq.com/s/demo123"', res['html'])
                self.assertIn('data-darkmode-color=', res['html'])
                self.assertIn('>GIF<', res['html'])
                self.assertNotIn('人工智能辅助创作', res['html'])
                self.assertTrue(res['tableWarnings'])

        # Explicit --aigc-footer turns on disclosure
        res_aigc = rwh.WeChatRenderer(themes['sspai'], aigc_footer=True).convert(md_sample)
        self.assertIn('人工智能辅助创作', res_aigc['html'])

        # Edge cases absorbed from WeChat platform constraints:
        # 1) Digest strictly <= 120 UTF-8 bytes even for long Chinese prose; 2) Code block skips CJK spacing;
        # 3) Anchor links (#sec) do not create footnotes; 4) Empty workspace learn_edits summarize returns valid JSON.
        long_cn = '# 长文测试\n\n' + ('这是一段包含很多汉字的正文内容用来测试微信摘要一百二十字节上限截断。' * 4) + '\n\n看[节内跳转](#sec)。\n\n```python\nx = "AI2026年"\n```\n'
        res_edge = rwh.WeChatRenderer(themes['professional-clean']).convert(long_cn)
        self.assertLessEqual(len(res_edge['digest'].encode('utf-8')), 120)
        self.assertTrue(res_edge['digest'].endswith('…'))
        self.assertIn('AI2026年', res_edge['html'])
        self.assertEqual(res_edge['footnoteCount'], 0)
        self.assertNotIn('参考链接', res_edge['html'])

        with tempfile.TemporaryDirectory() as empty_ws:
            empty_sum = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'learn_edits.py'), 'summarize', empty_ws, '--json'],
                capture_output=True, text=True, check=True,
            )
            self.assertEqual(json.loads(empty_sum.stdout)['totalLessons'], 0)

        # Structural HTML attribute integrity & contrast guard (prevents broken style="..." quotes or invisible dark-theme text)
        from html.parser import HTMLParser
        ALLOWED_ATTRS = {'style', 'src', 'alt', 'href', 'leaf', 'data-lang', 'data-darkmode-color', 'data-darkmode-bgcolor'}

        def contrast_ratio(hex1: str, hex2: str) -> float:
            def rel_lum(h: str) -> float:
                h = h.lstrip('#')
                vals = []
                for i in (0, 2, 4):
                    c = int(h[i:i + 2], 16) / 255.0
                    vals.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
                return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
            l1, l2 = rel_lum(hex1), rel_lum(hex2)
            return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

        class AttrAuditor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.bad_attrs = []
                self.pre_styles = []
                self.callout_pairs = []

            def handle_starttag(self, tag, attrs):
                attr_map = dict(attrs)
                for k, _ in attrs:
                    if k not in ALLOWED_ATTRS:
                        self.bad_attrs.append((tag, k))
                if tag == 'pre':
                    self.pre_styles.append(attr_map.get('style', ''))
                st = attr_map.get('style', '')
                if 'border-left: 4px solid' in st and 'background-color:' in st and 'color:' in st:
                    bg_m = re.search(r'background-color:\s*(#[0-9a-fA-F]{6})', st)
                    fg_m = re.search(r'(?<!background-)color:\s*(#[0-9a-fA-F]{6})', st)
                    if bg_m and fg_m:
                        self.callout_pairs.append((fg_m.group(1), bg_m.group(1)))

        import re
        for tname, theme in themes.items():
            with self.subTest(audit_theme=tname):
                res = rwh.WeChatRenderer(theme).convert(md_sample)
                auditor = AttrAuditor()
                auditor.feed(res['html'])
                self.assertEqual(auditor.bad_attrs, [], f'{tname}: malformed/unexpected HTML attrs (possible broken quotes): {auditor.bad_attrs}')
                self.assertTrue(auditor.pre_styles and 'color:' in auditor.pre_styles[0], f'{tname}: <pre> lost color style')
                self.assertGreaterEqual(contrast_ratio(theme['colors']['codeText'], theme['colors']['codeBg']), 4.5)
                self.assertGreaterEqual(contrast_ratio(theme['colors']['text'], theme['colors']['bg']), 4.5)
                for fg, bg in auditor.callout_pairs:
                    self.assertGreaterEqual(contrast_ratio(fg, bg), 4.5, f'{tname}: low callout contrast {fg} on {bg}')
                preview_html = rwh.build_preview_page(res, theme)
                self.assertIn(f'color:{theme["colors"]["text"]};', preview_html)

        # Preview mode passes validate-only, while forbidden HTML fails validate-only
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            md_file = tdir / 'article.md'
            prev_file = tdir / 'preview.html'
            bad_file = tdir / 'bad.html'
            md_file.write_text(md_sample, encoding='utf-8')
            p1 = subprocess.run(
                [sys.executable, str(WECHAT_SCRIPTS / 'render_wechat_html.py'), str(md_file), '--theme', 'sspai', '--mode', 'preview', '-o', str(prev_file), '--json'],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p1.returncode, 0, p1.stderr)
            p2 = subprocess.run(
                [sys.executable, str(WECHAT_SCRIPTS / 'render_wechat_html.py'), '--validate-only', str(prev_file), '--json'],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p2.returncode, 0, p2.stdout + p2.stderr)

            bad_file.write_text('<style>p{color:red}</style><div class="x" style="position:fixed;display:grid;color:var(--a)">hi</div>', encoding='utf-8')
            p3 = subprocess.run(
                [sys.executable, str(WECHAT_SCRIPTS / 'render_wechat_html.py'), '--validate-only', str(bad_file), '--json'],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p3.returncode, 1)
            bad_out = json.loads(p3.stdout)
            rules = {item['rule'] for item in bad_out['issues']}
            self.assertTrue({'style_tag', 'div_tag', 'class_attr', 'position_unsupported', 'display_grid', 'css_var'}.issubset(rules))

    def test_wechat_client_stage_draft_add_image_post_and_get_draft_over_http(self):
        recorded = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_POST(self):
                length = int(self.headers.get('Content-Length', '0'))
                raw = self.rfile.read(length)
                recorded.append((self.path, raw))
                if self.path.startswith('/cgi-bin/media/uploadimg'):
                    body = {'url': 'https://mmbiz.qpic.cn/mmbiz_png/uploaded_inline_1/0'}
                elif self.path.startswith('/cgi-bin/material/add_material'):
                    body = {'media_id': f'MEDIA_{len(recorded)}'}
                elif self.path.startswith('/cgi-bin/draft/add'):
                    body = {'media_id': 'DRAFT_OK_123'}
                elif self.path.startswith('/cgi-bin/draft/get'):
                    body = {'news_item': [{'title': '人工改过的标题', 'digest': '摘要', 'content': '<section><p>第一段正文。</p><p>第二段修改版。</p></section>'}]}
                else:
                    body = {'errcode': 40001, 'errmsg': 'unexpected path'}
                payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            wx_client = load_module(WECHAT_SCRIPTS / 'client.py', 'wx_client_v12')
            base_url = f'http://127.0.0.1:{server.server_port}'
            with tempfile.TemporaryDirectory() as tmp, \
                 patch.object(wx_client, 'BASE', base_url), \
                 patch.dict(os.environ, {'WECHAT_OFFICIAL_ACCESS_TOKEN': 'tok_test'}):
                tdir = Path(tmp)
                assets = tdir / 'assets'
                assets.mkdir()
                img1 = assets / 'fig1.png'
                cover = assets / 'cover.png'
                img1.write_bytes(b'\x89PNG\r\n\x1a\nfakeimg1')
                cover.write_bytes(b'\x89PNG\r\n\x1a\nfakecover')
                md = tdir / 'article.md'
                md.write_text('# 测试公众号标题\n\n正文插图：\n\n![插图一](assets/fig1.png)\n', encoding='utf-8')

                # 1. stage-draft uploads inline image + cover + posts unescaped Chinese JSON
                from io import StringIO
                buf = StringIO()
                with patch('sys.stdout', buf):
                    rc = wx_client.main(['stage-draft', '--content-file', str(md), '--cover', str(cover), '--theme', 'sspai'])
                self.assertEqual(rc, 0)
                staged = json.loads(buf.getvalue())
                self.assertEqual(staged['draft']['media_id'], 'DRAFT_OK_123')
                self.assertEqual(len(staged['uploadedInlineImages']), 1)
                draft_reqs = [raw.decode('utf-8') for path, raw in recorded if path.startswith('/cgi-bin/draft/add')]
                self.assertEqual(len(draft_reqs), 1)
                self.assertIn('测试公众号标题', draft_reqs[0])  # ensure_ascii=False preserved UTF-8
                self.assertIn('https://mmbiz.qpic.cn/mmbiz_png/uploaded_inline_1/0', draft_reqs[0])
                self.assertNotIn('assets/fig1.png', draft_reqs[0])

                # 2. stage-draft blocks invalid raw HTML before making network calls
                bad_html = tdir / 'bad.html'
                bad_html.write_text('<div>forbidden</div>', encoding='utf-8')
                before_count = len(recorded)
                err_buf = StringIO()
                with patch('sys.stderr', err_buf):
                    rc_bad = wx_client.main(['stage-draft', '--content-file', str(bad_html), '--cover', str(cover), '--title', '坏HTML'])
                self.assertEqual(rc_bad, 1)
                self.assertEqual(len(recorded), before_count)

                # 3. add-image-post (newspic / 小绿书)
                buf2 = StringIO()
                with patch('sys.stdout', buf2):
                    rc2 = wx_client.main(['add-image-post', '--title', '小绿书三图测试', '--images', f'{img1},{cover}', '--content', '精简配文'])
                self.assertEqual(rc2, 0)
                pic_out = json.loads(buf2.getvalue())
                self.assertEqual(pic_out['articleType'], 'newspic')
                self.assertEqual(pic_out['imageCount'], 2)

                # Over-32-char newspic title rejected
                with patch('sys.stderr', StringIO()):
                    rc_long = wx_client.main(['add-image-post', '--title', '标题' * 20, '--image-media-ids', 'M1'])
                self.assertEqual(rc_long, 1)

                # 4. get-draft returns HTML + stripped plainText
                buf3 = StringIO()
                with patch('sys.stdout', buf3):
                    rc3 = wx_client.main(['get-draft', '--media-id', 'DRAFT_OK_123'])
                self.assertEqual(rc3, 0)
                got = json.loads(buf3.getvalue())
                self.assertEqual(got['title'], '人工改过的标题')
                self.assertIn('第二段修改版', got['plainText'])
                self.assertNotIn('<section>', got['plainText'])
        finally:
            server.shutdown()
            server.server_close()

    def test_writing_quality_score_similarity_and_learn_edits_flywheel(self):
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            cliche_doc = tdir / 'cliche.md'
            cliche_doc.write_text(
                '首先，值得注意的是，众所周知这件事非常重要。其次，不可否认，不是工具不够好，而是认知没到位。'
                '再者，毋庸置疑，不是速度不够快，而是方向没选对。最后，总而言之，综上所述，不是团队不够努力，而是方法论至关重要。'
                + '这是一个极其深刻地、显著地、全面地、有效地、真正地改变行业格局的话题。' * 12,
                encoding='utf-8',
            )
            clean_doc = tdir / 'clean.md'
            clean_doc.write_text(
                '# 实测复盘\n\n2026年11月我们统计了30篇公众号文章，根据内部数据报告，完读率从28%提升到41%。'
                '参考 https://example.com/benchmark 的对照实验，去掉空泛开场白后前30秒跳出率下降了14%。\n',
                encoding='utf-8',
            )
            clone_doc = tdir / 'clone.md'
            clone_doc.write_text(clean_doc.read_text(encoding='utf-8') + '\n加一句尾巴。', encoding='utf-8')
            native_rewrite = tdir / 'xhs.md'
            native_rewrite.write_text(
                '姐妹们别再写废话开头了！直接给结果：把第一段砍掉一半，读完的人多了快一半，具体怎么做看这三张卡片清单。',
                encoding='utf-8',
            )

            r_bad = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'check_writing_quality.py'), 'score', str(cliche_doc), '--json'],
                capture_output=True, text=True, check=True,
            )
            bad_data = json.loads(r_bad.stdout)
            self.assertLess(bad_data['score'], 70)
            bad_rules = {f['rule'] for f in bad_data['findings']}
            self.assertIn('cliche_density', bad_rules)
            self.assertIn('contrast_template_overuse', bad_rules)

            r_ok = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'check_writing_quality.py'), 'score', str(clean_doc), '--json'],
                capture_output=True, text=True, check=True,
            )
            self.assertGreaterEqual(json.loads(r_ok.stdout)['score'], 90)

            # Similarity gate blocks near-clone and passes native rewrite
            r_sim_fail = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'check_writing_quality.py'), 'similarity', str(clean_doc), str(clone_doc), '--threshold', '0.45', '--fail-on-exceed', '--json'],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_sim_fail.returncode, 1)
            self.assertTrue(json.loads(r_sim_fail.stdout)['exceedsThreshold'])

            r_sim_ok = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'check_writing_quality.py'), 'similarity', str(clean_doc), str(native_rewrite), '--threshold', '0.45', '--fail-on-exceed', '--json'],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(r_sim_ok.returncode, 0)
            self.assertFalse(json.loads(r_sim_ok.stdout)['exceedsThreshold'])

            # Edit-learning flywheel: single edit stays advisory, 2nd occurrence promotes to standing rule
            ws = tdir / 'content-ops'
            ws.mkdir()
            ai_draft = tdir / 'ai_draft.md'
            human_final = tdir / 'human_final.md'
            ai_draft.write_text('# 旧标题：浅谈工具\n\n众所周知这是一个好工具。\n\n具体步骤如下。', encoding='utf-8')
            human_final.write_text('# 新标题：3步用好工具\n\n直接看实测结果。\n\n具体步骤如下。', encoding='utf-8')

            rec1 = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'learn_edits.py'), 'record', str(ws), '--draft', str(ai_draft), '--final', str(human_final), '--platform', 'wechat-official', '--json'],
                capture_output=True, text=True, check=True,
            )
            self.assertGreaterEqual(json.loads(rec1.stdout)['recordedCount'], 2)

            sum1 = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'learn_edits.py'), 'summarize', str(ws), '--write-playbook', '--json'],
                capture_output=True, text=True, check=True,
            )
            s1 = json.loads(sum1.stdout)
            self.assertEqual(s1['standingCount'], 0)
            self.assertGreater(s1['candidateCount'], 0)

            # Record same pattern a second time -> promoted automatically
            subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'learn_edits.py'), 'record', str(ws), '--draft', str(ai_draft), '--final', str(human_final), '--platform', 'wechat-official', '--json'],
                capture_output=True, text=True, check=True,
            )
            sum2 = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'learn_edits.py'), 'summarize', str(ws), '--write-playbook', '--json'],
                capture_output=True, text=True, check=True,
            )
            s2 = json.loads(sum2.stdout)
            self.assertGreaterEqual(s2['standingCount'], 2)
            playbook = (ws / 'style' / 'style-playbook.md').read_text(encoding='utf-8')
            self.assertIn('## Standing Rules', playbook)
            self.assertIn('wechat-official | global, x2', playbook)

    def test_topic_radar_hotspots_seo_and_sogou_over_local_http(self):
        class RadarHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                if self.path.startswith('/weibo'):
                    body = json.dumps({'data': {'realtime': [{'note': '重复热点', 'num': 900000}, {'note': '微博独有热点', 'num': 500000}]}}, ensure_ascii=False)
                    ctype = 'application/json; charset=utf-8'
                elif self.path.startswith('/toutiao'):
                    body = json.dumps({'data': [{'Title': '重复热点', 'HotValue': 8000000, 'Url': 'https://toutiao.example/1'}, {'Title': '头条独有热点', 'HotValue': 4000000, 'Url': 'https://toutiao.example/2'}]}, ensure_ascii=False)
                    ctype = 'application/json; charset=utf-8'
                elif self.path.startswith('/baidu-su'):
                    body = json.dumps(['AI', ['AI工具', 'AI写作', 'AI工作流']], ensure_ascii=False)
                    ctype = 'application/json; charset=utf-8'
                elif self.path.startswith('/baidu'):
                    body = json.dumps({'data': {'cards': [{'content': [{'content': [{'word': '百度热点A', 'hotScore': 700000, 'url': 'https://baidu.example/a'}]}]}]}}, ensure_ascii=False)
                    ctype = 'application/json; charset=utf-8'
                elif self.path.startswith('/hn-top'):
                    body = json.dumps([101])
                    ctype = 'application/json; charset=utf-8'
                elif self.path.startswith('/hn-item/101'):
                    body = json.dumps({'id': 101, 'title': 'Show HN: Code Video Engine', 'score': 320, 'url': 'https://hn.example/101'})
                    ctype = 'application/json; charset=utf-8'
                elif self.path.startswith('/lobsters'):
                    body = json.dumps([{'title': 'Zero-Dependency Markdown Compiler', 'score': 88, 'url': 'https://lob.example/1', 'tags': ['python', 'compilers']}])
                    ctype = 'application/json; charset=utf-8'
                elif self.path.startswith('/so360-su'):
                    body = json.dumps({'result': [{'word': 'AI工作流'}, {'word': 'AI自动化'}]}, ensure_ascii=False)
                    ctype = 'application/json; charset=utf-8'
                elif self.path.startswith('/sogou-boot'):
                    body = 'ok'
                    ctype = 'text/plain'
                elif self.path.startswith('/sogou-search') and 'captcha' in self.path:
                    body = '<html><body>antispider 请输入验证码</body></html>'
                    ctype = 'text/html; charset=utf-8'
                elif self.path.startswith('/sogou-search'):
                    from datetime import datetime, timezone
                    now_ts = int(datetime.now(timezone.utc).timestamp())
                    body = (
                        '<ul class="news-list"><li>'
                        '<h3><a href="/link?url=demo">AI编程提效实战</a></h3>'
                        '<p class="txt-info">一篇真实测试摘要</p>'
                        f'<div class="s-p"><span class="all-time-y2">测试公众号</span><span class="s2"><script>timeConvert("{now_ts}")</script></span></div>'
                        '</li></ul>'
                    )
                    ctype = 'text/html; charset=utf-8'
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                raw = body.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = ThreadingHTTPServer(('127.0.0.1', 0), RadarHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            from io import StringIO

            # 1a. fetch_hotspots_cn (CN radar only)
            fh_cn = load_module(CN_RADAR_SCRIPTS / 'fetch_hotspots_cn.py', 'fetch_hotspots_cn_mod')
            buf = StringIO()
            with patch.dict(fh_cn.ENDPOINTS, {
                'weibo': f'{base}/weibo',
                'toutiao': f'{base}/toutiao',
                'baidu': f'{base}/baidu',
            }), patch('sys.stdout', buf):
                rc = fh_cn.main(['--limit', '10', '--json'])
            self.assertEqual(rc, 0)
            hot_cn = json.loads(buf.getvalue())
            self.assertEqual(hot_cn['sourcesOk'], ['baidu', 'toutiao', 'weibo'])
            cn_titles = [it['title'] for it in hot_cn['items']]
            self.assertEqual(cn_titles.count('重复热点'), 1)

            # 1b. fetch_hotspots_global (Global radar only: Hacker News + Lobsters)
            fh_gl = load_module(GLOBAL_RADAR_SCRIPTS / 'fetch_hotspots_global.py', 'fetch_hotspots_global_mod')
            buf_gl = StringIO()
            with patch.dict(fh_gl.ENDPOINTS, {
                'hackernews': f'{base}/hn-top',
                'lobsters': f'{base}/lobsters',
            }), patch.object(fh_gl, 'HN_ITEM_TMPL', f'{base}/hn-item/{{id}}'), patch('sys.stdout', buf_gl):
                rc_gl = fh_gl.main(['--limit', '10', '--json'])
            self.assertEqual(rc_gl, 0)
            hot_gl = json.loads(buf_gl.getvalue())
            self.assertEqual(hot_gl['sourcesOk'], ['hackernews', 'lobsters'])
            gl_titles = [it['title'] for it in hot_gl['items']]
            self.assertIn('Show HN: Code Video Engine', gl_titles)
            self.assertIn('Zero-Dependency Markdown Compiler', gl_titles)

            # 2. seo_keywords_cn
            sk = load_module(CN_RADAR_SCRIPTS / 'seo_keywords_cn.py', 'seo_keywords_cn_mod')
            buf2 = StringIO()
            with patch.object(sk, 'BAIDU_SU', f'{base}/baidu-su'), patch.object(sk, 'SO360_SU', f'{base}/so360-su'), patch('sys.stdout', buf2):
                rc2 = sk.main(['AI', '--json'])
            self.assertEqual(rc2, 0)
            seo = json.loads(buf2.getvalue())[0]
            self.assertEqual(seo['baiduScore'], 3)
            self.assertEqual(seo['so360Score'], 2)
            self.assertEqual(seo['relatedKeywords'], ['AI工具', 'AI写作', 'AI工作流', 'AI自动化'])

            # 3. search_wechat_articles (owned by platform-wechat-official) normal + CAPTCHA clean stop
            sw = load_module(WECHAT_SCRIPTS / 'search_wechat_articles.py', 'search_wechat_mod')
            buf3 = StringIO()
            with patch.object(sw, 'BOOTSTRAP_URL', f'{base}/sogou-boot'), patch.object(sw, 'SEARCH_URL', f'{base}/sogou-search'), patch('sys.stdout', buf3):
                rc3 = sw.main(['AI编程', '--days', '7', '--pages', '1', '--json'])
            self.assertEqual(rc3, 0)
            s_ok = json.loads(buf3.getvalue())
            self.assertFalse(s_ok['captchaDetected'])
            self.assertEqual(s_ok['count'], 1)
            self.assertEqual(s_ok['items'][0]['account'], '测试公众号')

            buf4 = StringIO()
            with patch.object(sw, 'BOOTSTRAP_URL', f'{base}/sogou-boot'), patch.object(sw, 'SEARCH_URL', f'{base}/sogou-search'), patch('sys.stdout', buf4):
                rc4 = sw.main(['captcha', '--pages', '1', '--json'])
            self.assertEqual(rc4, 0)
            self.assertTrue(json.loads(buf4.getvalue())['captchaDetected'])
        finally:
            server.shutdown()
            server.server_close()

    def test_fetch_wechat_article_learn_theme_workspace_render_and_exemplar(self):
        sample_wx_html = """<!doctype html><html><head><title>翡翠绿排版范文</title></head><body>
        <h1 id="activity-name">翡翠绿排版范文</h1>
        <a id="js_name">极客运营笔记</a>
        <div id="js_content" style="background-color: #ffffff;">
          <h2 style="color: #047857; border-bottom: 2px solid #047857;">01 · 为什么先看数据</h2>
          <p style="color: #2d3748;">2026年我们复盘了40篇长文，完读率提升35%。但是很多人忽略了节奏控制。</p>
          <blockquote style="border-left: 4px solid #047857; background-color: #ecfdf5;">好结构比辞藻更值钱。</blockquote>
          <h2 style="color: #047857; border-bottom: 2px solid #047857;">02 · 实操清单</h2>
          <p style="color: #2d3748;">记住这三件事：<strong>先给结论</strong>，再拆步骤，最后给边界。</p>
          <img data-src="https://mmbiz.qpic.cn/demo/img1.png" alt="示意图" />
        </div></body></html>"""

        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            ws = tdir / 'content-ops'
            ws.mkdir()
            saved = tdir / 'saved.html'
            saved.write_text(sample_wx_html, encoding='utf-8')
            md_out = tdir / 'extracted.md'

            # 1. fetch_wechat_article from local saved HTML -> clean Markdown
            p_fetch = subprocess.run(
                [sys.executable, str(WECHAT_SCRIPTS / 'fetch_wechat_article.py'), '--file', str(saved), '-o', str(md_out), '--json'],
                capture_output=True, text=True, check=True,
            )
            f_data = json.loads(p_fetch.stdout)
            self.assertEqual(f_data['title'], '翡翠绿排版范文')
            self.assertEqual(f_data['account'], '极客运营笔记')
            self.assertEqual(f_data['imageCount'], 1)
            self.assertIn('![示意图](https://mmbiz.qpic.cn/demo/img1.png)', md_out.read_text(encoding='utf-8'))

            # 2. learn_theme from saved HTML -> saves into <workspace>/style/themes/emerald-geek.json
            p_learn = subprocess.run(
                [sys.executable, str(WECHAT_SCRIPTS / 'learn_theme.py'), '--file', str(saved), '--name', 'emerald-geek', '--workspace', str(ws), '--json'],
                capture_output=True, text=True, check=True,
            )
            l_data = json.loads(p_learn.stdout)
            self.assertEqual(l_data['theme']['colors']['primary'], '#047857')
            self.assertTrue(l_data['theme']['sectionNumbering'])
            self.assertTrue((ws / 'style' / 'themes' / 'emerald-geek.json').is_file())

            # 3. render_wechat_html loads custom learned theme via --workspace and passes all 16 rules
            rendered_preview = tdir / 'learned-preview.html'
            p_ren = subprocess.run(
                [sys.executable, str(WECHAT_SCRIPTS / 'render_wechat_html.py'), str(md_out), '--workspace', str(ws), '--theme', 'emerald-geek', '--mode', 'preview', '-o', str(rendered_preview), '--json'],
                capture_output=True, text=True, check=True,
            )
            r_data = json.loads(p_ren.stdout)
            self.assertEqual(r_data['errors'], 0)
            self.assertEqual(r_data['theme'], 'emerald-geek')
            self.assertIn('#047857', rendered_preview.read_text(encoding='utf-8'))

            # 4. extract_exemplar records structural fingerprint into <workspace>/style/exemplars.json
            p_ex = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'extract_exemplar.py'), 'add', str(ws), str(md_out), '--source', '极客运营笔记', '--json'],
                capture_output=True, text=True, check=True,
            )
            ex_data = json.loads(p_ex.stdout)
            self.assertEqual(ex_data['addedCount'], 1)
            self.assertEqual(ex_data['exemplars'][0]['fingerprint']['h2Count'], 2)

            p_ls = subprocess.run(
                [sys.executable, str(MEDIA_SCRIPTS / 'extract_exemplar.py'), 'list', str(ws), '--json'],
                capture_output=True, text=True, check=True,
            )
            self.assertEqual(json.loads(p_ls.stdout)['count'], 1)


if __name__ == '__main__':
    unittest.main()
