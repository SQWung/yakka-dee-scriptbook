#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对 batch2 新 5 集应用图书风格 UI，并重新生成总目录。
"""
import re
import sys
from pathlib import Path

# 把 tools 目录加入路径，方便 import build_book_ui
sys.path.insert(0, str(Path(__file__).parent))
import build_book_ui as bu

ROOT = Path(__file__).parent.parent
HTML_DIR = ROOT / "html"


def main():
    # 处理新 5 集：解析旧版 HTML，生成图书风格 HTML
    for ep, en, zh, thumb in bu.EPISODES[5:]:
        html_path = HTML_DIR / f"{ep}.html"
        title, sections = bu.parse_episode(html_path)
        display_title = re.sub(r"Yakka Dee 台词本 · ", "", title)
        new_html = bu.build_episode_html(ep, display_title, sections)
        html_path.write_text(new_html, encoding="utf-8")
        total = sum(len(s["lines"]) for s in sections)
        print(f"已生成图书风格 {html_path}，共 {total} 句")

    # 重新生成总目录（使用全部 10 集）
    index_path = HTML_DIR / "index.html"
    index_path.write_text(bu.build_index_html(), encoding="utf-8")
    print(f"已重新生成 {index_path}")


if __name__ == "__main__":
    main()
