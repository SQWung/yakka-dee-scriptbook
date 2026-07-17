#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch 2 (S1E06-10: duck/cup/bus/peas/hat) 台词本流水线：
- 下载 subsaga SRT 字幕
- 翻译（dict + Google gtx）
- ffmpeg 逐句截图
- 生成旧版 HTML（含章节）
- 输出 JSON 数据
"""
import re
import json
import time
import html as html_mod
import subprocess
from pathlib import Path
from typing import List, Dict
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
HTML_DIR = ROOT / "html"
IMG_DIR = HTML_DIR / "images"
SRT_BASE = "https://subsaga.com/bbc/childrens/yakka-dee/series-1/{slug}.srt"

EPISODES = [
    ("duck", "Duck", "鸭子", 6, "d3535t7rol7"),
    ("cup", "Cup", "杯子", 7, "f3362rgrazv"),
    ("bus", "Bus", "公交车", 8, "a3362q9ywlm"),
    ("peas", "Peas", "豌豆", 9, "s35699fr7kc"),
    ("hat", "Hat", "帽子", 10, "n35358cyetc"),
]

# 把常见译名固定，避免 Google 翻译不一致
NAME_FIX = {
    "亚卡迪伊": "雅卡迪", "亚卡迪": "雅卡迪", "亚卡": "雅卡",
    "嘀伊": "迪伊", "迪伊": "迪伊",
    "Yakka": "雅卡", "Dee": "迪伊",
}

SFX_MAP = {
    "SLURP": "啜饮声", "HIC": "打嗝声", "PARDON": "抱歉",
    "DRUM ROLL": "鼓声", "CYMBAL CRASH": "镲声",
    "DUCK QUACKS": "鸭子嘎嘎叫", "QUACK": "嘎嘎",
    "DUCKS QUACKING": "鸭子嘎嘎叫",
    "BUS BEEPS": "巴士哔哔声", "BUS HONKS": "巴士喇叭声",
    "TYRES SQUEAL": "轮胎尖叫声", "BIKE BELL RINGS": "自行车铃响",
    "DOG BARKS": "狗叫", "DOG WHINES": "狗呜呜叫", "DOG PANTS": "狗喘气",
    "SHE LAUGHS": "她笑了", "HE LAUGHS": "他笑了", "THEY LAUGH": "他们笑了",
    "DEE LAUGHS": "迪伊笑了", "DEE CHUCKLES": "迪伊咯咯笑",
    "BOTH": "两人", "ALL": "大家", "KIDS": "孩子们",
}

# 尝试导入现有字典
DICT = {}
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location("dict_zh", ROOT / "dict_zh.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    DICT = dict(mod.D)
except Exception as e:
    print("注意：未能加载 dict_zh.py:", e)


def parse_srt(text: str) -> List[Dict]:
    """解析 SubRip 文本。"""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        # 序号行
        if re.fullmatch(r"\d+", lines[i].strip()):
            i += 1
            if i >= len(lines):
                break
            # 时间轴行
            time_line = lines[i].strip()
            m = re.match(r"(\d{1,2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2},\d{3})", time_line)
            if not m:
                i += 1
                continue
            fr_srt = m.group(1)
            to_srt = m.group(2)
            i += 1
            # 收集文本行
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            if text_lines:
                out.append({
                    "text": "\n".join(text_lines),
                    "from": srt_to_display(fr_srt),
                    "to": srt_to_display(to_srt),
                    "from_sec": srt_to_seconds(fr_srt),
                    "to_sec": srt_to_seconds(to_srt),
                })
        else:
            i += 1
    return out


def srt_to_display(s: str) -> str:
    # 00:00:02,600 -> 0:00:02
    s = s.replace(",", ".")
    parts = s.split(":")
    h, m, sec = parts[0], parts[1], parts[2]
    h = int(h)
    if h == 0:
        return f"{int(m)}:{sec.split('.')[0].zfill(2)}"
    return f"{h}:{m}:{sec.split('.')[0].zfill(2)}"


def srt_to_seconds(s: str) -> float:
    s = s.replace(",", ".")
    parts = s.split(":")
    h, m, sec = int(parts[0]), int(parts[1]), float(parts[2])
    return h * 3600 + m * 60 + sec


# ---------- 翻译 ----------

def translate_lines(texts: List[str]) -> Dict[str, str]:
    """批量翻译文本，返回 {原文: 中文}。"""
    # 先准备 dict / 规则命中
    cache = {}
    todo = []
    for t in texts:
        if t in DICT:
            cache[t] = DICT[t]
            continue
        # 全大写 SFX（含空格的字母）
        if re.fullmatch(r"[A-Z][A-Z\s]*", t) and len(t) > 1:
            cache[t] = "【" + (SFX_MAP.get(t, t)) + "】"
            continue
        # 歌曲：以 # 开头
        if t.strip().startswith("#"):
            lyric = t.strip().lstrip("#").strip()
            if lyric in DICT:
                cache[t] = DICT[lyric]
            else:
                todo.append(t)
            continue
        todo.append(t)

    # Google gtx 逐个翻译
    for t in todo:
        cache[t] = google_translate(t)
        time.sleep(0.05)
    return cache


def google_translate(text: str) -> str:
    """调用 Google Translate gtx。"""
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": text}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        parts = [item[0] for item in data[0]]
        return post_process("".join(parts))
    except Exception as e:
        print("翻译失败:", text, e)
        return "（待翻译）"


def post_process(s: str) -> str:
    # 歌曲标记
    if s.lstrip().startswith("#"):
        s = "【歌曲】" + s.lstrip().lstrip("#").strip()
    # 人名/品牌统一
    for old, new in NAME_FIX.items():
        s = s.replace(old, new)
    return s


# ---------- 分节 ----------

def segment_sections(lines: List[Dict], target_word: str) -> List[Dict]:
    """把台词行分成 4 个章节。"""
    # 找 "What will our yakka be today?"
    idx_today = next((i for i, l in enumerate(lines)
                      if re.search(r"what will our yakka be today", l["text"], re.I)), None)
    if idx_today is None:
        idx_today = 0

    # 找目标词揭示（今天学哪个词的结束）
    # 通常在今天之后，第一个出现 "<Word>!" 或 "<Word>." 或纯目标词大写的行
    idx_reveal = None
    for i in range(idx_today, min(idx_today + 12, len(lines))):
        txt = re.sub(r"[^\w\s'!]", "", lines[i]["text"]).strip()
        if re.fullmatch(rf"{re.escape(target_word)}[!\.\?]?", txt, re.I):
            idx_reveal = i
            break
    if idx_reveal is None:
        #  fallback：今天之后第 4 行
        idx_reveal = min(idx_today + 3, len(lines) - 1)

    # 找片尾曲：最后一段以 # 开头的歌词
    idx_outro = None
    for i in range(len(lines) - 1, idx_reveal, -1):
        if lines[i]["text"].strip().startswith("#"):
            idx_outro = i
            break
    # 往前找到片尾曲连续段的开头
    if idx_outro is not None:
        while idx_outro > 0 and lines[idx_outro - 1]["text"].strip().startswith("#"):
            idx_outro -= 1
    else:
        idx_outro = len(lines)

    sections = [
        {"title": "🎵 片头主题曲", "lines": lines[:idx_today]},
        {"title": "🎲 今天学哪个词", "lines": lines[idx_today:idx_reveal + 1]},
        {"title": "📺 单词探险", "lines": lines[idx_reveal + 1:idx_outro]},
        {"title": "🎵 片尾曲", "lines": lines[idx_outro:]},
    ]
    return [s for s in sections if s["lines"]]


# ---------- 截图与 HTML ----------

def take_screenshot(video_path: Path, timestamp: float, out_path: Path):
    """ffmpeg 截图。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video_path),
        "-frames:v", "1", "-q:v", "3", str(out_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def build_old_html(ep: str, title: str, zh: str, sections: List[Dict], ep_no: int) -> str:
    """生成旧版 line-card HTML。"""
    cards_html = []
    global_idx = 1
    for sec in sections:
        cards_html.append(f'<div class="section"><h2>{html_mod.escape(sec["title"])}</h2></div>')
        for line in sec["lines"]:
            img = f"images/{ep}/line_{global_idx:03d}.jpg"
            alt = f"截图：{line['text'][:30]}"
            cards_html.append(f"""        <div class="line-card" data-idx="{global_idx}">
          <div class="line-thumb">
            <img src="{img}" alt="{html_mod.escape(alt)}" loading="lazy">
          </div>
          <div class="line-body">
            <div class="line-meta">#{global_idx} <span class="time">{line['from']} → {line['to']}</span></div>
            <div class="line-en">{html_mod.escape(line['text'])}</div>
            <div class="line-cn">{html_mod.escape(line['cn'])}</div>
          </div>
        </div>""")
            global_idx += 1

    total = global_idx - 1
    cards_body = "\n".join(cards_html)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Yakka Dee 台词本 · {title}（{zh}）</title>
<style>
:root{{--bg:#f7f7f8;--card:#fff;--text:#222;--muted:#666;--accent:#f9a825;--border:#e5e5e5}}
*{{box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);margin:0;padding:0}}
header{{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid var(--border);padding:14px 16px}}
.container{{max-width:920px;margin:0 auto;padding:0 16px}}
header .container{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}}
h1{{font-size:20px;margin:0}}
.sub{{color:var(--muted);font-size:13px}}
.toggles{{display:flex;gap:8px;flex-wrap:wrap}}
button{{border:1px solid #d1d1d1;background:#fff;border-radius:6px;padding:8px 14px;font-size:14px;cursor:pointer;transition:all .2s}}
button:hover{{border-color:var(--accent)}}
button.active{{background:var(--accent);border-color:var(--accent);color:#fff}}
.section{{margin:32px 0 16px}}
.section h2{{font-size:18px;border-left:4px solid var(--accent);padding-left:10px;margin:0}}
.line-card{{display:flex;gap:14px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:12px;margin:10px 0;transition:box-shadow .2s}}
.line-card:hover{{box-shadow:0 2px 8px rgba(0,0,0,.08)}}
.line-thumb{{flex:0 0 220px;max-width:220px}}
.line-thumb img{{width:100%;height:auto;border-radius:6px;display:block}}
.line-body{{flex:1;display:flex;flex-direction:column;justify-content:center;gap:6px}}
.line-meta{{font-size:12px;color:var(--muted)}}
.time{{margin-left:6px;}}
.line-en{{font-size:18px;font-weight:600;line-height:1.5}}
.line-cn{{font-size:15px;color:var(--muted);line-height:1.5}}
body.hide-images .line-thumb{{display:none}}
body.hide-images .line-card{{display:block;padding:14px}}
body.hide-cn .line-cn{{display:none}}
@media(max-width:640px){{.line-card{{flex-direction:column}} .line-thumb{{flex:1;max-width:100%}} header .container{{flex-direction:column;align-items:flex-start}}}}
@media print{{.toggles{{display:none}} .line-thumb{{page-break-inside:avoid}}}}
</style>
</head>
<body>
<header>
  <div class="container">
    <div>
      <h1>Yakka Dee 台词本</h1>
      <div class="sub">第一季第 {ep_no} 集：{title}（{zh}） · 共 {total} 句</div>
    </div>
    <div class="toggles">
      <button id="btnImg" class="active" onclick="toggle('images')">📷 图片</button>
      <button id="btnCn" class="active" onclick="toggle('cn')">🇨🇳 翻译</button>
    </div>
  </div>
</header>
<main class="container">
{cards_body}
</main>
<script>
function toggle(k){{document.body.classList.toggle('hide-'+k);document.getElementById(k==='images'?'btnImg':'btnCn').classList.toggle('active');}}
</script>
</body>
</html>"""


def main():
    print("=" * 50)
    print("Batch 2 流水线开始")
    print("=" * 50)
    for ep, title, zh, ep_no, vid in EPISODES:
        slug = f"{ep_no}-{ep}"
        print(f"\n--- 处理 {ep_no}. {title} ({zh}) ---")

        # 1. 下载 SRT
        srt_url = SRT_BASE.format(slug=slug)
        r = requests.post(srt_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        lines = parse_srt(r.text)
        print(f"  字幕行数: {len(lines)}")

        # 2. 翻译
        unique_texts = list({l["text"] for l in lines})
        trans = translate_lines(unique_texts)
        for l in lines:
            l["cn"] = trans.get(l["text"], "（待翻译）")

        # 3. 分节
        sections = segment_sections(lines, title)
        print(f"  章节: " + " / ".join(f"{s['title']}({len(s['lines'])}句)" for s in sections))

        # 4. 截图
        video_path = ROOT / f"{ep}.mp4"
        ep_img_dir = IMG_DIR / ep
        ep_img_dir.mkdir(parents=True, exist_ok=True)
        for i, l in enumerate(lines, 1):
            out = ep_img_dir / f"line_{i:03d}.jpg"
            take_screenshot(video_path, l["from_sec"], out)
        print(f"  截图: {len(lines)} 张")

        # 5. 保存 JSON 数据
        data = [{"text": l["text"], "from": l["from"], "to": l["to"], "cn": l["cn"]} for l in lines]
        with open(DATA_DIR / f"{ep}_subs.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 6. 生成旧版 HTML
        html = build_old_html(ep, title, zh, sections, ep_no)
        with open(HTML_DIR / f"{ep}.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  已生成 html/{ep}.html")

    print("\nBatch 2 流水线完成。")


if __name__ == "__main__":
    main()
