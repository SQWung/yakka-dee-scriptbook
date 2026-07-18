#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把现有 html/*.html 台词本改造成「图书展开页」风格。
- 解析旧 HTML 提取章节与已翻译的台词行
- 重新渲染为双页展开布局：章节彩条、圆角图卡网格、页码
- 保留图片/翻译开关
"""
import json
import re
import html as html_mod
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).parent.parent
HTML_DIR = ROOT / "html"
PER_PAGE = 8

SECTION_STYLE = {
    "🎵 片头主题曲": {"color": "#9b59b6", "icon": "🎵"},
    "🎲 今天学哪个词": {"color": "#f39c12", "icon": "🎲"},
    "📺 单词探险": {"color": "#3498db", "icon": "📺"},
    "🎵 片尾曲": {"color": "#e91e63", "icon": "🎵"},
}

EPISODES = [
    ("banana", "Banana", "香蕉", "line_020.jpg"),
    ("dog", "Dog", "狗", "line_022.jpg"),
    ("book", "Book", "书", "line_019.jpg"),
    ("boots", "Boots", "靴子", "line_023.jpg"),
    ("bike", "Bike", "自行车", "line_032.jpg"),
    ("duck", "Duck", "鸭子", "line_023.jpg"),
    ("cup", "Cup", "杯子", "line_023.jpg"),
    ("bus", "Bus", "公交车", "line_024.jpg"),
    ("peas", "Peas", "豌豆", "line_019.jpg"),
    ("hat", "Hat", "帽子", "line_019.jpg"),
    ("worm", "Worm", "虫子", "line_030.jpg"),
    ("boat", "Boat", "船", "line_030.jpg"),
    ("house", "House", "房子", "line_030.jpg"),
    ("lion", "Lion", "狮子", "line_030.jpg"),
    ("apple", "Apple", "苹果", "line_030.jpg"),
    ("ball", "Ball", "球", "line_030.jpg"),
    ("mouse", "Mouse", "老鼠", "line_030.jpg"),
    ("beans", "Beans", "豆子", "line_030.jpg"),
    ("car", "Car", "汽车", "line_030.jpg"),
    ("bed", "Bed", "床", "line_030.jpg"),
]


def parse_episode(html_path: Path):
    """从旧 HTML 中解析章节结构和已翻译的台词行。"""
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    title = soup.title.string if soup.title else html_path.stem
    main = soup.find("main")
    if not main:
        return title, []

    sections = []
    current_title = None
    current_lines = []

    for child in main.children:
        if isinstance(child, NavigableString):
            continue
        if child.name == "div" and "section" in child.get("class", []):
            if current_title is not None:
                sections.append({"title": current_title, "lines": current_lines})
            current_title = child.get_text(strip=True)
            current_lines = []
        elif child.name == "div" and "line-card" in child.get("class", []):
            img_tag = child.find("img")
            meta_tag = child.find("div", class_="line-meta")
            time_tag = child.find("span", class_="time")
            en_tag = child.find("div", class_="line-en")
            cn_tag = child.find("div", class_="line-cn")
            if not (img_tag and en_tag and cn_tag):
                continue
            num_match = re.search(r"#(\d+)", meta_tag.get_text() if meta_tag else "")
            line = {
                "img": img_tag.get("src", ""),
                "alt": img_tag.get("alt", ""),
                "num": int(num_match.group(1)) if num_match else 0,
                "time": time_tag.get_text(strip=True) if time_tag else "",
                "en": en_tag.get_text(strip=True),
                "cn": cn_tag.get_text(strip=True),
            }
            current_lines.append(line)

    if current_title is not None:
        sections.append({"title": current_title, "lines": current_lines})
    return title, sections


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def build_spreads(sections, page_start=1):
    """把章节拆成双页展开页。返回 (spread_html, 下一页起始编号)。"""
    page_no = page_start
    spreads = []
    for sec in sections:
        style = SECTION_STYLE.get(sec["title"], {"color": "#1abc9c", "icon": "📖"})
        pages = list(chunks(sec["lines"], PER_PAGE))
        if not pages:
            pages = [[]]
        for i in range(0, len(pages), 2):
            is_first_spread = i == 0
            left_lines = pages[i]
            right_lines = pages[i + 1] if i + 1 < len(pages) else None
            spread_html = render_spread(
                sec["title"], style, left_lines, right_lines, page_no, page_no + 1, is_first_spread
            )
            spreads.append(spread_html)
            page_no += 2
    return "\n".join(spreads), page_no


def render_spread(title, style, left_lines, right_lines, left_page, right_page, is_first):
    """渲染一个双页展开。"""
    return f"""
<div class="spread">
  {render_page(title, style, left_lines, left_page, is_first, True, 'page-left')}
  {render_page(title, style, right_lines, right_page, is_first, False, 'page-right') if right_lines else f'<div class="page page-right blank-page"><div class="page-footer">Page {right_page}</div></div>'}
</div>
"""


def render_page(title, style, lines, page_no, is_first_spread, is_left, extra_cls):
    cards = "\n".join(render_card(line) for line in lines)
    short_title = title.split()[-1] if title else ""
    header_title = title if (is_first_spread and is_left) else short_title
    return f"""
<div class="page {extra_cls}" style="--section-color:{style['color']}">
  <div class="page-header">
    <span class="page-mascot">{style['icon']}</span>
    <span class="page-title">{html_mod.escape(header_title)}</span>
  </div>
  <div class="card-grid">{cards}</div>
  <div class="page-footer">{f'Page {page_no}' if page_no else ''}</div>
</div>
"""


def render_card(line):
    return f"""
<div class="card">
  <div class="card-thumb">
    <img src="{line['img']}" alt="{html_mod.escape(line['alt'])}" loading="lazy">
  </div>
  <div class="card-body">
    <div class="card-en">{html_mod.escape(line['en'])}</div>
    <div class="card-cn">{html_mod.escape(line['cn'])}</div>
    <div class="card-meta">#{line['num']} · {html_mod.escape(line['time'])}</div>
  </div>
</div>
"""


def build_episode_html(episode, title, sections):
    """生成单集图书风格 HTML。"""
    spreads_html, _ = build_spreads(sections, page_start=1)
    total_lines = sum(len(s["lines"]) for s in sections)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Yakka Dee 台词本 · {title}</title>
{COMMON_CSS}
</head>
<body>
{build_header(title, f"共 {total_lines} 句")}
<main class="book">
{spreads_html}
</main>
{COMMON_JS}
</body>
</html>
"""


def build_index_html():
    """生成总目录（图书封面风格）。"""
    colors = ['#f39c12','#e74c3c','#3498db','#2ecc71','#9b59b6','#1abc9c','#e91e63','#34495e','#f1c40f','#8e44ad','#16a085','#d35400','#c0392b','#2980b9','#27ae60','#2c3e50','#e67e22','#a569bd','#48c9b0','#f1948a']
    cards = "\n".join(
        f"""
<a class="ep-cover" href="{ep}.html" style="--ep-color:{colors[i]}">
  <div class="ep-thumb"><img src="images/{ep}/{thumb}" alt="{en}"></div>
  <div class="ep-info">
    <div class="ep-en">{en}</div>
    <div class="ep-zh">{zh}</div>
    <div class="ep-ep">第 {i+1} 集</div>
  </div>
</a>
"""
        for i, (ep, en, zh, thumb) in enumerate(EPISODES)
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Yakka Dee 台词本 · 总目录</title>
{COMMON_CSS}
<style>
.book-cover {{ text-align:center; padding: 40px 20px 20px; }}
.book-cover h1 {{ font-size: 42px; margin: 0 0 8px; color: var(--ink); letter-spacing: 2px; }}
.book-cover .subtitle {{ color: var(--muted); font-size: 18px; margin-bottom: 8px; }}
.book-cover .badge {{ display:inline-block; background: var(--accent); color: #fff; padding: 6px 16px; border-radius: 20px; font-size: 14px; margin-top: 10px; }}
.ep-shelf {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 18px; padding: 24px; }}
.ep-cover {{ text-decoration: none; background: #fff; border-radius: 14px; overflow: hidden; box-shadow: 0 3px 10px rgba(0,0,0,.12); border-top: 6px solid var(--ep-color); transition: transform .15s, box-shadow .15s; display: flex; flex-direction: column; }}
.ep-cover:hover {{ transform: translateY(-4px); box-shadow: 0 6px 16px rgba(0,0,0,.18); }}
.ep-thumb img {{ width: 100%; height: 110px; object-fit: cover; display: block; }}
.ep-info {{ padding: 12px; text-align: center; }}
.ep-en {{ font-size: 18px; font-weight: 700; color: var(--ink); }}
.ep-zh {{ font-size: 14px; color: var(--muted); margin-top: 2px; }}
.ep-ep {{ font-size: 12px; color: var(--accent); margin-top: 6px; font-weight: 600; }}
@media (max-width: 480px) {{ .book-cover h1 {{ font-size: 28px; }} .ep-shelf {{ grid-template-columns: repeat(2, 1fr); }} }}
</style>
</head>
<body>
{build_header("Yakka Dee 台词本", "第一季前20集 · 点击封面进入各集", include_toggles=False)}
<main class="book">
  <div class="book-cover">
    <h1>📚 Yakka Dee 台词本</h1>
    <div class="subtitle">第一季前 20 集 · 逐句翻译 + 截图</div>
    <div class="badge">🖼️ 图片 · 🔤 翻译 均可一键关闭</div>
  </div>
  <div class="ep-shelf">
    {cards}
  </div>
</main>
{COMMON_JS}
</body>
</html>
"""


def build_header(main_title, subtitle, include_toggles=True):
    toggles = f"""
    <div class="toggles">
      <a href="index.html" style="text-decoration:none"><button>🏠 总目录</button></a>
      <button id="btnImg" class="active" onclick="toggle('images')">🖼️ 图片</button>
      <button id="btnCn" class="active" onclick="toggle('cn')">🔤 翻译</button>
    </div>""" if include_toggles else ""
    return f"""
<header>
  <div class="header-inner">
    <div class="header-title">
      <span class="header-mascot">🎤</span>
      <div>
        <div class="header-h1">{html_mod.escape(main_title)}</div>
        <div class="header-sub">{html_mod.escape(subtitle)}</div>
      </div>
    </div>
    {toggles}
  </div>
</header>
"""


COMMON_CSS = """
<style>
:root { --paper: #fffdf5; --ink: #2c3e50; --muted: #7f8c8d; --accent: #f9a825; --border: #e5e5e5; }
* { box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif; background: #e8e0d5; color: var(--ink); margin: 0; padding-bottom: 40px; }
header { position: sticky; top: 0; z-index: 20; background: #fff; border-bottom: 3px solid var(--accent); box-shadow: 0 2px 10px rgba(0,0,0,.08); }
.header-inner { max-width: 1200px; margin: 0 auto; padding: 12px 20px; display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.header-title { display: flex; align-items: center; gap: 12px; }
.header-mascot { width: 44px; height: 44px; border-radius: 50%; background: var(--accent); display: grid; place-items: center; font-size: 24px; box-shadow: 0 2px 6px rgba(0,0,0,.15); }
.header-h1 { font-size: 20px; font-weight: 700; margin: 0; }
.header-sub { font-size: 13px; color: var(--muted); margin-top: 2px; }
.toggles { display: flex; gap: 8px; flex-wrap: wrap; }
button { border: 2px solid #d1d1d1; background: #fff; border-radius: 8px; padding: 8px 14px; font-size: 14px; cursor: pointer; font-weight: 600; transition: all .15s; }
button:hover { border-color: var(--accent); color: var(--accent); }
button.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.book { max-width: 1200px; margin: 24px auto; background: var(--paper); border-radius: 12px; box-shadow: 0 0 24px rgba(0,0,0,.15); min-height: 80vh; overflow: hidden; }
.spread { display: flex; gap: 16px; padding: 20px; border-bottom: 2px dashed #ddd; page-break-inside: avoid; }
.page { flex: 1; background: #fff; border-radius: 14px; box-shadow: 0 4px 12px rgba(0,0,0,.1); display: flex; flex-direction: column; min-height: 520px; overflow: hidden; border: 1px solid #ececec; }
.page-header { background: var(--section-color); color: #fff; padding: 10px 14px; display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 16px; border-bottom: 3px solid rgba(0,0,0,.08); }
.page-mascot { width: 32px; height: 32px; border-radius: 50%; background: rgba(255,255,255,.25); display: grid; place-items: center; font-size: 18px; }
.page-title { flex: 1; }
.card-grid { flex: 1; display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; padding: 14px; align-content: start; }
.card { border: 2px solid #f4f4f4; border-radius: 14px; background: #fff; padding: 10px; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,.05); transition: transform .15s; display: flex; flex-direction: column; }
.card:hover { transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,.1); border-color: var(--section-color); }
.card-thumb { width: 90px; height: 90px; margin: 0 auto 8px; border-radius: 50%; overflow: hidden; border: 3px solid var(--section-color); background: #f9f9f9; }
.card-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.card-body { flex: 1; display: flex; flex-direction: column; justify-content: center; gap: 4px; }
.card-en { font-size: 15px; font-weight: 700; line-height: 1.35; color: var(--ink); }
.card-cn { font-size: 13px; color: var(--muted); line-height: 1.35; }
.card-meta { font-size: 11px; color: #aaa; margin-top: 4px; }
.page-footer { text-align: center; padding: 8px; font-size: 12px; color: #bbb; border-top: 1px solid #f4f4f4; }
.blank-page { background: repeating-linear-gradient(45deg, #fff, #fff 10px, #fafafa 10px, #fafafa 20px); }
body.hide-images .card-thumb { display: none; }
body.hide-cn .card-cn { display: none; }
@media (max-width: 900px) { .spread { flex-direction: column; } .page { min-height: auto; } .card-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px) { .header-inner { flex-direction: column; align-items: flex-start; } .card-grid { grid-template-columns: repeat(2, 1fr); } .card-thumb { width: 70px; height: 70px; } }
@media (max-width: 400px) { .card-grid { grid-template-columns: 1fr; } }
@media print { header { position: static; } .toggles { display: none; } .spread { break-inside: avoid; page-break-inside: avoid; } .card { break-inside: avoid; } }
</style>
"""

COMMON_JS = """
<script>
function toggle(k){
  document.body.classList.toggle('hide-'+k);
  document.getElementById(k==='images'?'btnImg':'btnCn').classList.toggle('active');
}
</script>
"""


def main():
    for ep, en, zh, _ in EPISODES:
        html_path = HTML_DIR / f"{ep}.html"
        title, sections = parse_episode(html_path)
        # 保留旧 title 中的中文名，例如 "Banana（香蕉）"
        display_title = re.sub(r"Yakka Dee 台词本 · ", "", title)
        new_html = build_episode_html(ep, display_title, sections)
        html_path.write_text(new_html, encoding="utf-8")
        print(f"已生成 {html_path}，共 {sum(len(s['lines']) for s in sections)} 句")

    index_path = HTML_DIR / "index.html"
    index_path.write_text(build_index_html(), encoding="utf-8")
    print(f"已生成 {index_path}")


if __name__ == "__main__":
    main()
