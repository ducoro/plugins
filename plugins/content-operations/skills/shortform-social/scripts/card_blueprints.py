#!/usr/bin/env python3
"""Semantic HTML frame blueprints for Social Visual Card Studio (zero external dependencies)."""
from __future__ import annotations

from html import escape
from typing import List

LAYOUT_NAMES = (
    'cover-split',
    'cover-bleed',
    'thesis',
    'metric-hero',
    'compare-two',
    'checklist',
    'step-flow',
    'shot-stage',
    'quote-note',
    'closing-cta',
    'map-route',
)


def _frame_open(fid: str, classes: str, w: int, h: int, label: str, card_title: str) -> str:
    return (
        f'    <section id="{fid}" class="card-frame {classes}" '
        f'data-export-frame="{fid}" data-export-width="{w}" data-export-height="{h}" '
        f'data-export-label="{escape(label, quote=True)}" '
        f'data-card="{fid}" data-card-title="{escape(card_title, quote=True)}">'
    )


def render_carousel_frame(
    frame_id: str,
    layout: str,
    idx: int,
    total: int,
    brand: str = '@BrandName',
    deck_title: str = '核心观点卡片组',
    *,
    width: int = 1080,
    height: int = 1440,
    frame_class: str = 'frame-3x4',
    ratio_label: str = '3:4',
) -> str:
    """Render one exportable vertical carousel slide (3:4 1080x1440 or 4:5 1080x1350) for the requested semantic layout."""
    html = render_3x4_frame(frame_id, layout, idx, total, brand=brand, deck_title=deck_title)
    if width == 1080 and height == 1440 and frame_class == 'frame-3x4' and ratio_label == '3:4':
        return html
    return (
        html.replace('class="card-frame frame-3x4 ', f'class="card-frame {frame_class} ', 1)
        .replace('data-export-width="1080" data-export-height="1440"', f'data-export-width="{width}" data-export-height="{height}"', 1)
        .replace('data-export-label="3:4 ', f'data-export-label="{ratio_label} ', 1)
    )


def render_3x4_frame(
    frame_id: str,
    layout: str,
    idx: int,
    total: int,
    brand: str = '@BrandName',
    deck_title: str = '核心观点卡片组',
) -> str:
    """Render one 1080x1440 (3:4) exportable card section for the requested semantic layout."""
    if layout not in LAYOUT_NAMES:
        raise ValueError(f'Unknown layout {layout!r}; expected one of: {", ".join(LAYOUT_NAMES)}')

    fid = escape(frame_id, quote=True)
    b = escape(brand)
    t = escape(deck_title)
    page = f'{idx:02d} / {total:02d}'

    if layout == 'cover-bleed':
        head = _frame_open(fid, 'frame-3x4 layout-cover-bleed soft-scrim-bottom', 1080, 1440, '3:4 Full-Bleed Cover', f'{fid} — Full-Bleed Cover')
        return f'''{head}
      <!-- subject map: inspect hero image before final placement; set explicit object-position and keep title inside quiet zone -->
      <div class="bleed-layer zone-bottom">
        <span class="eyebrow-solid" data-mark-item="{fid}-eyebrow" data-mark-label="Cover tag">FEATURE</span>
        <h1 class="title-hero" data-mark-item="{fid}-title" data-mark-label="Cover headline">{t}</h1>
        <p class="lead-copy" data-mark-item="{fid}-lead" data-mark-label="Cover subtitle">替换为满铺实拍图（&lt;img class="bleed-photo" src="assets/cover.jpg" style="object-position: center 35%" alt="..." /&gt;），确保文字落在安静区。</p>
        <footer class="card-foot"><span class="brand-mark">{b}</span><span>{page}</span></footer>
      </div>
    </section>'''

    if layout == 'cover-split':
        head = _frame_open(fid, 'frame-3x4 layout-cover-split', 1080, 1440, '3:4 Split Cover', f'{fid} — Split Cover')
        return f'''{head}
      <div class="card-head">
        <span class="eyebrow-pill" data-mark-item="{fid}-eyebrow" data-mark-label="Cover tag">FIELD GUIDE</span>
        <span class="page-index">{page}</span>
      </div>
      <div class="card-body">
        <div class="accent-rule"></div>
        <h1 class="title-hero" data-mark-item="{fid}-title" data-mark-label="Cover headline">{t}</h1>
        <p class="lead-copy" data-mark-item="{fid}-lead" data-mark-label="Cover subtitle">8–14 字主标题 + 真实证据图，在手机信息流缩略宽度下保持一眼可读。</p>
        <figure class="media-well" data-mark-item="{fid}-visual" data-mark-label="Cover visual slot">
          <div class="media-placeholder">
            <strong>真实照片 / 产品截图 / image_generate 视觉位</strong>
            <span class="meta-caption">替换为 &lt;img src="assets/hero.png" style="object-position: center 45%" alt="..." /&gt;</span>
          </div>
        </figure>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>向右滑动查看拆解 →</span></footer>
    </section>'''

    if layout == 'thesis':
        head = _frame_open(fid, 'frame-3x4 layout-thesis', 1080, 1440, '3:4 Thesis Statement', f'{fid} — Core Thesis')
        return f'''{head}
      <div class="card-head"><span class="eyebrow">CORE THESIS</span><span class="page-index">{page}</span></div>
      <div class="card-body">
        <div class="thesis-stage">
          <div class="accent-rule"></div>
          <h2 class="title-hero" data-mark-item="{fid}-title" data-mark-label="Thesis headline">把最反直觉的一句话<br />放到整页正中</h2>
          <p class="lead-copy" data-mark-item="{fid}-lead" data-mark-label="Thesis context">当某页只有一个核心判断时，放大排印层级并用下方补充注脚承接事实语境，避免塞进无意义列表。</p>
          <div class="thesis-note" data-mark-item="{fid}-note" data-mark-label="Evidence note">实证来源或关键约束：写清这句话成立的前提条件与适用边界。</div>
        </div>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>核心判断</span></footer>
    </section>'''

    if layout == 'metric-hero':
        head = _frame_open(fid, 'frame-3x4 layout-metric-hero', 1080, 1440, '3:4 Metric Breakdown', f'{fid} — Metric Breakdown')
        return f'''{head}
      <div class="card-head"><span class="eyebrow">DATA EVIDENCE</span><span class="page-index">{page}</span></div>
      <div class="card-body">
        <h2 class="title-slide" data-mark-item="{fid}-title" data-mark-label="Metric slide title">用一组可核验数字说话</h2>
        <div class="metric-hero-box" data-mark-item="{fid}-hero" data-mark-label="Primary metric">
          <div><div class="metric-figure">3.4×</div><p class="meta-caption">替换为真实统计口径与样本周期</p></div>
          <p class="lead-copy">核心变化幅度与对比基准</p>
        </div>
        <div class="metric-bars" data-mark-item="{fid}-bars" data-mark-label="Comparison bars">
          <div class="bar-row"><div class="bar-label"><span>方案 A（实测样本）</span><span>82%</span></div><div class="bar-track"><div class="bar-fill" style="width: 82%"></div></div></div>
          <div class="bar-row"><div class="bar-label"><span>方案 B（传统基线）</span><span>46%</span></div><div class="bar-track"><div class="bar-fill" style="width: 46%"></div></div></div>
          <div class="bar-row"><div class="bar-label"><span>方案 C（未优化对照）</span><span>24%</span></div><div class="bar-track"><div class="bar-fill" style="width: 24%"></div></div></div>
        </div>
        <div class="thesis-note" data-mark-item="{fid}-note" data-mark-label="Metric takeaway">样本结论：写清指标差异背后的核心原因，避免只扔数字不给解释。</div>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>数据来源注明于正文</span></footer>
    </section>'''

    if layout == 'compare-two':
        head = _frame_open(fid, 'frame-3x4 layout-compare-two', 1080, 1440, '3:4 Two-Column Comparison', f'{fid} — Side-by-Side Comparison')
        return f'''{head}
      <div class="card-head"><span class="eyebrow">BEFORE / AFTER</span><span class="page-index">{page}</span></div>
      <div class="card-body">
        <h2 class="title-slide" data-mark-item="{fid}-title" data-mark-label="Comparison headline">两种做法的真实分水岭</h2>
        <div class="compare-grid" data-mark-item="{fid}-grid" data-mark-label="Comparison columns">
          <div class="compare-col">
            <span class="eyebrow">常见误区</span>
            <h3>堆砌装饰与空话</h3>
            <ul class="compare-list">
              <li><strong>版式千篇一律</strong>全篇套同一个卡片壳，读者划到第三页就疲劳</li>
              <li><strong>正文直接硬塞</strong>把长段落原封不动贴进图里，小屏根本看不清</li>
              <li><strong>缺少真实证据</strong>没有截图与数据口径支撑，看完留不下记忆点</li>
            </ul>
          </div>
          <div class="compare-col is-highlight">
            <span class="eyebrow-solid">高收藏写法</span>
            <h3>克制结构 + 硬证据</h3>
            <ul class="compare-list">
              <li><strong>按内容轮换页型</strong>封面、对比、数据与截图交替出现，每页讲透一点</li>
              <li><strong>图文各司其职</strong>卡片负责钩子与结论，完整推导与来源留给正文</li>
              <li><strong>真实依据唱主角</strong>界面截图与实测数据占满视觉重心，降低理解成本</li>
            </ul>
          </div>
        </div>
        <div class="thesis-note" data-mark-item="{fid}-summary" data-mark-label="Comparison verdict">判断准则：先问“这一页拿掉装饰后还剩多少硬信息”，再决定是否保留。</div>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>对比参考</span></footer>
    </section>'''

    if layout == 'checklist':
        head = _frame_open(fid, 'frame-3x4 layout-checklist', 1080, 1440, '3:4 Action Checklist', f'{fid} — Action Checklist')
        return f'''{head}
      <div class="card-head"><span class="eyebrow">CHECKLIST</span><span class="page-index">{page}</span></div>
      <div class="card-body">
        <h2 class="title-slide" data-mark-item="{fid}-title" data-mark-label="Checklist title">发布前必查的三条硬指标</h2>
        <ul class="item-stack" data-mark-item="{fid}-items" data-mark-label="Checklist rows">
          <li class="item-row"><span class="item-num">01</span><div><strong>缩略图宽度下主标一眼可读</strong><p>把封面缩到 360px 宽复核，标题与背景反差够大且不压主体。</p></div></li>
          <li class="item-row"><span class="item-num">02</span><div><strong>每个结论都对应具体依据</strong><p>用真实操作截图、数据口径或条件约束替代模糊形容词。</p></div></li>
          <li class="item-row"><span class="item-num">03</span><div><strong>版面充盈且页脚不撞正文</strong><p>拒绝下半屏大块死白，用有效论据、图表或引文撑住竖向节奏。</p></div></li>
        </ul>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>建议收藏照做</span></footer>
    </section>'''

    if layout == 'step-flow':
        head = _frame_open(fid, 'frame-3x4 layout-step-flow', 1080, 1440, '3:4 Step Flow', f'{fid} — Step Flow')
        return f'''{head}
      <div class="card-head"><span class="eyebrow">WORKFLOW</span><span class="page-index">{page}</span></div>
      <div class="card-body">
        <h2 class="title-slide" data-mark-item="{fid}-title" data-mark-label="Workflow title">四步跑通整套流程</h2>
        <ol class="step-track" data-mark-item="{fid}-steps" data-mark-label="Workflow steps">
          <li class="step-node"><span class="step-badge">STEP 01</span><div><strong class="body-copy">明确目标平台与受众场景</strong><p class="meta-caption">先定比例与信息密度，再拆分每页任务。</p></div></li>
          <li class="step-node"><span class="step-badge">STEP 02</span><div><strong class="body-copy">选定唯一视觉语言与预设色板</strong><p class="meta-caption">整组保持统一调性，不混用多套风格。</p></div></li>
          <li class="step-node"><span class="step-badge">STEP 03</span><div><strong class="body-copy">放入真实截图、实拍或生成配图</strong><p class="meta-caption">先定安静区与主体裁切位置，再排文字。</p></div></li>
          <li class="step-node"><span class="step-badge">STEP 04</span><div><strong class="body-copy">离线体检 + 精确像素出图复核</strong><p class="meta-caption">通过审计与浏览器检视后进入审批发布。</p></div></li>
        </ol>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>标准作业流</span></footer>
    </section>'''

    if layout == 'shot-stage':
        head = _frame_open(fid, 'frame-3x4 layout-shot-stage', 1080, 1440, '3:4 Screenshot Stage', f'{fid} — Screenshot Evidence')
        return f'''{head}
      <div class="card-head"><span class="eyebrow">PRODUCT PROOF</span><span class="page-index">{page}</span></div>
      <div class="card-body">
        <h2 class="title-slide" data-mark-item="{fid}-title" data-mark-label="Screenshot headline">把关键界面放进主舞台</h2>
        <p class="lead-copy" data-mark-item="{fid}-lead" data-mark-label="Screenshot caption">一句话指出读者该看哪里，把 55% 以上画布留给清晰可读的真实截图。</p>
        <figure class="shot-stage" data-mark-item="{fid}-stage" data-mark-label="Framed screenshot">
          <div class="device-browser">
            <div class="browser-bar">
              <span class="browser-dot"></span><span class="browser-dot"></span><span class="browser-dot"></span>
              <span class="browser-url">app.example.com / dashboard</span>
            </div>
            <div class="device-screen">
              <div class="media-placeholder">
                <strong>产品 / 网页 / 终端真实截图位</strong>
                <span class="meta-caption">替换为 &lt;img src="assets/screenshot.png" alt="界面实拍" /&gt;（移动界面可改用 .device-phone）</span>
              </div>
            </div>
          </div>
        </figure>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>实测截图证据</span></footer>
    </section>'''

    if layout == 'quote-note':
        head = _frame_open(fid, 'frame-3x4 layout-quote-note', 1080, 1440, '3:4 Pull Quote', f'{fid} — Key Quote')
        return f'''{head}
      <div class="card-head"><span class="eyebrow">FIELD NOTE</span><span class="page-index">{page}</span></div>
      <div class="card-body">
        <blockquote class="quote-block" data-mark-item="{fid}-quote" data-mark-label="Pull quote">
          <div class="quote-mark">“</div>
          <p class="quote-text">好的社交图文不是把长文章硬塞进海报，而是帮读者在三秒内看清一个值得收藏的判断。</p>
          <p class="meta-caption">—— 替换为真实出处、访谈原话或核心复盘结论</p>
        </blockquote>
        <div class="thesis-note" data-mark-item="{fid}-takeaway" data-mark-label="Quote interpretation">延伸观察：用两行短句把引文拉回读者的日常工作或消费场景。</div>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>观点摘录</span></footer>
    </section>'''

    if layout == 'map-route':
        head = _frame_open(fid, 'frame-3x4 layout-map-route', 1080, 1440, '3:4 Spatial Route Map', f'{fid} — Route Map')
        return f'''{head}
      <div class="card-head"><span class="eyebrow">ROUTE MAP</span><span class="page-index">{page}</span></div>
      <div class="card-body">
        <h2 class="title-slide" data-mark-item="{fid}-title" data-mark-label="Map route title">四个停靠点，顺路不折返</h2>
        <p class="lead-copy" data-mark-item="{fid}-lead" data-mark-label="Map route summary">全程约 5.2 公里、步行加停留 4 小时，可替换为本地静态地图瓦片底图。</p>
        <figure class="map-canvas" data-mark-item="{fid}-map" data-mark-label="Route map stage">
          <svg viewBox="0 0 936 580" aria-hidden="true">
            <path d="M 160 440 C 260 390, 290 260, 420 270 C 550 280, 560 150, 740 140" fill="none" stroke="var(--accent)" stroke-width="6" stroke-dasharray="12 10" stroke-linecap="round" />
            <circle cx="160" cy="440" r="10" fill="var(--accent)" />
            <circle cx="380" cy="272" r="10" fill="var(--accent)" />
            <circle cx="575" cy="212" r="10" fill="var(--accent)" />
            <circle cx="740" cy="140" r="10" fill="var(--accent)" />
          </svg>
          <div class="map-pin" style="left: 20%; top: 76%;"><span class="map-pin-num">1</span>起点集合</div>
          <div class="map-pin" style="left: 42%; top: 47%;"><span class="map-pin-num">2</span>核心停靠</div>
          <div class="map-pin" style="left: 63%; top: 37%;"><span class="map-pin-num">3</span>补给观景</div>
          <div class="map-pin" style="left: 78%; top: 24%;"><span class="map-pin-num">4</span>终点收官</div>
        </figure>
        <div class="route-stops" data-mark-item="{fid}-stops" data-mark-label="Route stops legend">
          <div class="route-stop"><strong>01 起点集合</strong><span>07:30 · 0 km</span></div>
          <div class="route-stop"><strong>02 核心停靠</strong><span>08:40 · 1.8 km</span></div>
          <div class="route-stop"><strong>03 补给观景</strong><span>10:00 · 3.5 km</span></div>
          <div class="route-stop"><strong>04 终点收官</strong><span>11:30 · 5.2 km</span></div>
        </div>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>路线实测参考</span></footer>
    </section>'''

    head = _frame_open(fid, 'frame-3x4 layout-closing-cta', 1080, 1440, '3:4 Closing Summary', f'{fid} — Closing Takeaway')
    return f'''{head}
      <div class="card-head"><span class="eyebrow-solid">TAKEAWAY</span><span class="page-index">{page}</span></div>
      <div class="card-body">
        <div class="closing-box" data-mark-item="{fid}-box" data-mark-label="Closing summary box">
          <div class="closing-main">
            <div class="accent-rule"></div>
            <h2 class="title-hero" data-mark-item="{fid}-title" data-mark-label="Closing headline">一张图带走<br />全部关键动作</h2>
            <p class="lead-copy" data-mark-item="{fid}-lead" data-mark-label="Closing prompt">在评论区告诉我你目前最卡壳的一步，下一期针对真实问题做实操拆解。</p>
          </div>
          <div class="summary-strip" data-mark-item="{fid}-chips" data-mark-label="Summary tags">
            <div class="summary-chip">01 先定结构</div>
            <div class="summary-chip">02 实图优先</div>
            <div class="summary-chip">03 审核再发</div>
          </div>
        </div>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>完 · 欢迎收藏与讨论</span></footer>
    </section>'''


def render_wechat_pair(
    wide_title: str = '深度拆解：把长内容变成高转发封面的完整方法',
    short_title: str = '高转发封面<br />独立短标',
    brand: str = '公众号名称',
) -> str:
    """Render paired 2.35:1 (900x383) primary cover and 1:1 (1080x1080) square share cover."""
    wt = escape(wide_title)
    b = escape(brand)
    st = '<br />'.join(escape(part) for part in short_title.replace('<br>', '<br />').split('<br />'))
    wide_open = _frame_open('wechat-cover', 'frame-wechat-wide', 900, 383, 'WeChat 2.35:1 Primary Cover', 'WeChat 2.35:1 Primary Cover')
    sq_open = _frame_open('wechat-square', 'frame-wechat-sq', 1080, 1080, 'WeChat 1:1 Square Share Cover', 'WeChat 1:1 Square Share Cover')
    return f'''    <div class="pair-group">
  {wide_open}
        <div class="card-head">
          <span class="eyebrow-pill" data-mark-item="wechat-cover-tag" data-mark-label="WeChat wide tag">深度观察</span>
          <span class="page-index">900 × 383</span>
        </div>
        <div class="card-body">
          <h2 class="title-wide" data-mark-item="wechat-cover-title" data-mark-label="WeChat wide headline">{wt}</h2>
          <p class="lead-copy" data-mark-item="wechat-cover-sub" data-mark-label="WeChat wide subtitle">与 1:1 分享卡同风格不同构图，保证订阅号列表与聊天卡片都清晰耐看。</p>
        </div>
        <footer class="card-foot"><span class="brand-mark">{b}</span><span>主推送头图</span></footer>
      </section>

  {sq_open}
        <div class="card-head">
          <span class="eyebrow" data-mark-item="wechat-square-tag" data-mark-label="WeChat square tag">SHARE CARD</span>
          <span class="page-index">1080 × 1080</span>
        </div>
        <div class="card-body">
          <div class="square-stage">
            <div class="accent-rule"></div>
            <h2 class="title-square" data-mark-item="wechat-square-title" data-mark-label="WeChat short headline">{st}</h2>
            <p class="lead-copy" data-mark-item="wechat-square-note" data-mark-label="WeChat square note">4–10 字独立精炼短标题，专供转发卡片与次条方图。</p>
          </div>
        </div>
        <footer class="card-foot"><span class="brand-mark">{b}</span><span>1:1 分享封面对</span></footer>
      </section>
    </div>'''


def render_video_thumb(title: str = '3–5 个词定住第一眼', brand: str = '@ChannelName') -> str:
    """Render one 1280x720 (16:9) video thumbnail frame."""
    t, b = escape(title), escape(brand)
    head = _frame_open('thumb-16x9', 'frame-16x9 layout-thesis', 1280, 720, '16:9 Video Thumbnail', '16:9 Video Thumbnail')
    return f'''{head}
      <div class="card-head">
        <span class="eyebrow-solid" data-mark-item="thumb-16x9-tag" data-mark-label="Thumbnail tag">VIDEO COVER</span>
        <span class="page-index">1280 × 720</span>
      </div>
      <div class="card-body">
        <div class="thesis-stage">
          <h2 class="title-thumb" data-mark-item="thumb-16x9-title" data-mark-label="Thumbnail headline">{t}</h2>
          <p class="lead-copy" data-mark-item="thumb-16x9-sub" data-mark-label="Thumbnail subtitle">与视频标题形成互补，在手机推荐流小图下保持强反差可读。</p>
        </div>
      </div>
      <footer class="card-foot"><span class="brand-mark">{b}</span><span>1280 × 720</span></footer>
    </section>'''


def pick_carousel_layouts(pages: int, custom: List[str] | None = None) -> List[str]:
    """Return a balanced list of 3:4 slide layouts matching the requested page count."""
    if custom:
        for name in custom:
            if name not in LAYOUT_NAMES:
                raise ValueError(f'Unknown layout {name!r}; expected one of: {", ".join(LAYOUT_NAMES)}')
        return list(custom)
    if pages < 1 or pages > 20:
        raise ValueError(f'pages must be between 1 and 20, got {pages}')
    if pages == 1:
        return ['cover-split']
    if pages == 2:
        return ['cover-split', 'checklist']
    middle_pool = ['metric-hero', 'compare-two', 'shot-stage', 'checklist', 'step-flow', 'quote-note', 'thesis']
    return ['cover-split', *[middle_pool[i % len(middle_pool)] for i in range(pages - 2)], 'closing-cta']
