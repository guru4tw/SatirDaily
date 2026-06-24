#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_og.py
===========
為每場「有效活動」與站台預設,在每日 build 時用 Pillow 自動生成 1200×630 的
og:image(社群分享縮圖),輸出到 assets/og/{id}.png 與 assets/og/default.png。

為何要:社群(LINE/FB)分享無縮圖會直接壓低點擊率,圖片搜尋也零曝光。純靜態下
無法即時算圖,故改在 build 時預生成。各頁的 og:image meta 由 build_site_json.py
依檔案存在與否寫入(圖不在就不寫死 404),所以本腳本須在 build_site_json.py 之前跑。

字型:需 CJK 字型才畫得出中文。優先找環境內的 Noto Sans TC / 微軟正黑體 等;
都找不到就 graceful 退出(印警告、不生圖),build_site_json.py 會自動略過 og meta。

用法:
    python Py/build_og.py            # 讀 Docs/events.json,生成 assets/og/*.png
    python Py/build_og.py --force    # 即使圖已存在也重畫(預設只補缺漏)
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_JSON = ROOT / "Docs" / "events.json"
OG_DIR = ROOT / "assets" / "og"

TODAY = datetime.date.today().isoformat()

W, H = 1200, 630
BG_TOP = (15, 46, 42)      # 深湖綠
BG_BOT = (31, 111, 104)    # 湖水青
WATER = (124, 192, 184)
INK = (234, 245, 241)
SUB = (191, 229, 221)
CLAY = (211, 131, 92)

# 候選 CJK 字型(Linux CI 的 Noto / Windows 的微軟正黑 / mac)
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJKtc-Bold.otf",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
    "C:/Windows/Fonts/msjh.ttc",
    "C:/Windows/Fonts/msjhbd.ttc",
    "/System/Library/Fonts/PingFang.ttc",
]


def find_font():
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def _font(path, size):
    from PIL import ImageFont
    return ImageFont.truetype(path, size)


def _wrap(draw, text, font, max_w, max_lines):
    """逐字斷行(中文無空白),回傳行清單(超出 max_lines 以 … 收尾)。"""
    lines, cur = [], ""
    for ch in text:
        trial = cur + ch
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = ch
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if len(lines) == max_lines and (cur or True):
        # 若仍有殘餘字未放入,末行加省略號
        joined = "".join(lines)
        if len(joined) < len(text):
            last = lines[-1]
            while last and draw.textlength(last + "…", font=font) > max_w:
                last = last[:-1]
            lines[-1] = last + "…"
    return lines


def _gradient_bg():
    from PIL import Image
    img = Image.new("RGB", (W, H), BG_TOP)
    px = img.load()
    for y in range(H):
        t = y / H
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return img


def draw_card(font_path, *, title, when, meta, brand="SatirDaily｜薩提爾活動每日匯整"):
    from PIL import ImageDraw
    img = _gradient_bg()
    d = ImageDraw.Draw(img)

    PAD = 90
    # 品牌列 + 水面意象線
    f_brand = _font(font_path, 34)
    d.text((PAD, 70), brand, font=f_brand, fill=SUB)
    d.line([(PAD, 130), (W - PAD, 130)], fill=WATER, width=3)

    # 主標題(最多三行)。長標題易塞到三行,三行時縮字級 + 收窄行高,
    # 避免後面的日期膠囊與次要資訊溢出 630 畫布底部被切掉。
    f_title = _font(font_path, 74)
    lines = _wrap(d, title or "薩提爾活動", f_title, W - 2 * PAD, 3)
    if len(lines) >= 3:
        f_title = _font(font_path, 58)
        lines = _wrap(d, title or "薩提爾活動", f_title, W - 2 * PAD, 3)
    line_h = f_title.size + 18

    y = 188
    for ln in lines:
        d.text((PAD, y), ln, font=f_title, fill=INK)
        y += line_h
    y += 6

    # 日期膠囊
    if when:
        f_when = _font(font_path, 36)
        tw = d.textlength(when, font=f_when)
        cap_top = y + 12
        d.rounded_rectangle([PAD, cap_top, PAD + tw + 56, cap_top + 64],
                            radius=32, fill=(255, 255, 255))
        d.text((PAD + 28, cap_top + 12), when, font=f_when, fill=BG_BOT)
        y = cap_top + 64 + 18

    # 次要資訊(地區/講師/主辦)
    if meta:
        f_meta = _font(font_path, 34)
        meta_line = _wrap(d, meta, f_meta, W - 2 * PAD, 1)[0]
        d.text((PAD, y), meta_line, font=f_meta, fill=SUB)

    return img


def event_meta(e):
    bits = [e.get("region"), e.get("venue")]
    if e.get("facilitator"):
        bits.append("帶領:" + e["facilitator"])
    if e.get("organizer"):
        bits.append("主辦:" + e["organizer"])
    return " · ".join([b for b in bits if b])


def event_when(e):
    ds = e.get("date_start")
    if not ds:
        return "依報名場次・隨到隨學"
    de = e.get("date_end")
    return f"{ds} ～ {de}" if de and de != ds else ds


def is_active(e):
    ds = e.get("date_start")
    if not ds:
        return True  # 無日期=隨到隨學,視為有效
    return (e.get("date_end") or ds) >= TODAY


def main():
    ap = argparse.ArgumentParser(description="生成 og:image 到 assets/og/")
    ap.add_argument("--force", action="store_true", help="圖已存在也重畫")
    args = ap.parse_args()

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("⚠ 未安裝 Pillow,略過 og:image 生成(pip install Pillow)。", file=sys.stderr)
        return 0

    font_path = find_font()
    if not font_path:
        print("⚠ 找不到 CJK 字型,略過 og:image 生成。CI 請先 apt-get install fonts-noto-cjk。",
              file=sys.stderr)
        return 0

    if not DOCS_JSON.exists():
        print(f"⚠ 找不到 {DOCS_JSON},略過。", file=sys.stderr)
        return 0

    OG_DIR.mkdir(parents=True, exist_ok=True)
    events = json.loads(DOCS_JSON.read_text(encoding="utf-8"))

    # 站台預設圖
    default_png = OG_DIR / "default.png"
    if args.force or not default_png.exists():
        img = draw_card(font_path,
                        title="全台薩提爾工作坊・課程・活動每日匯整",
                        when="每日自動更新",
                        meta="依日期、地區、帶領者排序與搜尋,一站找到報名連結")
        img.save(default_png)

    made = 0
    for e in events:
        if not is_active(e):
            continue
        eid = e.get("id")
        if not eid:
            continue
        out = OG_DIR / f"{eid}.png"
        if out.exists() and not args.force:
            continue
        img = draw_card(font_path,
                        title=e.get("title") or "薩提爾活動",
                        when=event_when(e),
                        meta=event_meta(e))
        img.save(out)
        made += 1

    print(f"og:image 完成:字型 {Path(font_path).name} | 預設圖 1 | 新增活動圖 {made}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
