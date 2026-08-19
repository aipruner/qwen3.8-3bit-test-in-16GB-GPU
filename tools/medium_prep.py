#!/usr/bin/env python3
"""Turn the write-ups in output/ into something Medium can actually publish.

Medium has never supported tables: its importer drops pipe tables silently and
pasting them yields a wall of `|` characters. Each table is therefore rewritten
one of three ways, chosen per table in TABLE_PLAN:

  list  small key/value tables become bold-label bullets, which Medium renders
        natively and keeps selectable, searchable and link-clickable
  png   data comparison tables are screenshotted by headless Chromium, since
        their value is visual alignment that a bullet list destroys
  gist  the 29-row per-program table goes to a GitHub Gist, because as an image
        it would be unreadable on a phone

Relative image paths are rewritten to absolute raw.githubusercontent URLs so
Medium's importer can fetch and re-host them. Outputs cleaned Markdown plus
Medium-import-ready HTML.

Usage:
    python3 tools/medium_prep.py zh
    python3 tools/medium_prep.py zh en --skip-images   # text only, faster
"""

from __future__ import annotations

import argparse
import html
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_DIR = REPO / "output"
OUT_DIR = REPO / "output" / "medium"
TABLE_IMG_DIR = REPO / "output" / "images" / "tables"

RAW_BASE = "https://raw.githubusercontent.com/aipruner/qwen3.8-3bit-test-in-16GB-GPU/main"
IMG_URL_BASE = f"{RAW_BASE}/output/images"

SOURCES = {
    "zh": "qwen38-medium-zh.md",
    "en": "qwen38-medium-en.md",
}

# Chromium renders text through fontconfig, and WSL ships no CJK UI font worth
# using. Borrowing Microsoft JhengHei from the Windows host beats WenQuanYi.
WINDOWS_FONTS = Path("/mnt/c/Windows/Fonts")

SANS = (
    "'Microsoft JhengHei UI','Microsoft JhengHei','Noto Sans TC',"
    "'WenQuanYi Zen Hei','Segoe UI',Roboto,Helvetica,Arial,sans-serif"
)
MONO = "'Cascadia Mono',Consolas,'DejaVu Sans Mono','Liberation Mono',monospace"

# Medium's article column is about 700px wide. Rendering table images any wider
# means the browser downscales them, shrinking their text below the body copy
# and inverting the reading hierarchy. So render at the display width and let
# wide tables wrap instead.
CONTENT_WIDTH = 700
TABLE_MARGIN = 24  # white space each side, in CSS px
SCALE = 2  # device pixel ratio, for crisp text on retina displays


@dataclass
class TablePlan:
    """How to rewrite one table. `slug` and `alt` are only used by mode="png"."""

    mode: str
    slug: str = ""
    alt: dict[str, str] = field(default_factory=dict)


# Keyed by 1-based table order in the source, identical across both languages.
TABLE_PLAN: dict[int, TablePlan] = {
    1: TablePlan("list"),
    2: TablePlan("list"),
    3: TablePlan("list"),
    4: TablePlan("list"),
    5: TablePlan("list"),
    6: TablePlan("gist"),
    7: TablePlan(
        "png",
        "t07-2048",
        {
            "zh": "2048 核心邏輯：五次生成全部通過 19 條隱藏 assertion",
            "en": "2048 core logic: all five runs passed all 19 hidden assertions",
        },
    ),
    8: TablePlan(
        "png",
        "t08-tetris",
        {
            "zh": "Tetris 三次生成：語法、14 條功能檢查、實際載入全部通過",
            "en": "Tetris, three runs: syntax, 14 feature checks and real execution all passed",
        },
    ),
    9: TablePlan("list"),
    10: TablePlan(
        "png",
        "t10-math",
        {
            "zh": "八題數學：純推理 4/8，給 Python 工具後 8/8",
            "en": "Eight math problems: 4/8 on pure reasoning, 8/8 with a Python tool",
        },
    ),
    11: TablePlan("list"),
    12: TablePlan(
        "png",
        "t12-context",
        {
            "zh": "context 從 1K 拉到 29K，生成速度基本持平",
            "en": "Generation speed stays flat from 1K to 29K of context",
        },
    ),
    13: TablePlan("list"),
    14: TablePlan(
        "png",
        "t14-quant",
        {
            "zh": "3-bit 與 4-bit 在這張 16GB 卡上的實測結果",
            "en": "3-bit versus 4-bit measured on this 16GB card",
        },
    ),
    15: TablePlan(
        "png",
        "t15-throughput",
        {
            "zh": "與第三方公開數據的吞吐量對照",
            "en": "Throughput compared against third-party public numbers",
        },
    ),
    16: TablePlan(
        "png",
        "t16-vendor",
        {
            "zh": "Qwen 官方 model card 的 benchmark 自評表",
            "en": "Benchmark numbers self-reported on Qwen's official model card",
        },
    ),
    17: TablePlan(
        "png",
        "t17-intelligence",
        {
            "zh": "Artificial Analysis Intelligence Index",
            "en": "Artificial Analysis Intelligence Index",
        },
    ),
    18: TablePlan(
        "png",
        "t18-agentic",
        {
            "zh": "Artificial Analysis Agentic Index",
            "en": "Artificial Analysis Agentic Index",
        },
    ),
    19: TablePlan(
        "png",
        "t19-claude-vs-local",
        {
            "zh": "Claude Opus 4.7 對 Qwen 3.6-27B Q3_K_XL 的同題實測",
            "en": "Claude Opus 4.7 versus Qwen 3.6-27B Q3_K_XL on an identical task",
        },
    ),
    20: TablePlan("list"),
    21: TablePlan(
        "png",
        "t21-reasoning-effort",
        {
            "zh": "三種 reasoning_effort 的成功率與平均耗時",
            "en": "Success rate and mean wall-clock across three reasoning_effort settings",
        },
    ),
    22: TablePlan("list"),
}

GIST_LABELS = {
    "zh": {
        "note": "完整逐題數據（29 支程式的步數、工具呼叫、token、耗時、生成速度）"
        "放在這裡，Medium 上以 Gist 形式嵌入：",
        "placeholder": "把下面這行換成 Gist 網址，Medium 會自動嵌入",
    },
    "en": {
        "note": "The full per-program table (steps, tool calls, tokens, wall-clock and "
        "generation speed for all 29 programs) lives here, embedded on Medium as a Gist:",
        "placeholder": "Replace the line below with the Gist URL; Medium embeds it automatically",
    },
}

LINK_NOTE = {
    "zh": "表中連結：",
    "en": "Links from the table above: ",
}

INLINE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
INLINE_CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


# --------------------------------------------------------------------------- #
# Markdown table parsing
# --------------------------------------------------------------------------- #


@dataclass
class Table:
    index: int
    headers: list[str]
    aligns: list[str]
    rows: list[list[str]]

    @property
    def has_headers(self) -> bool:
        return any(h.strip() for h in self.headers)


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_aligns(sep: str) -> list[str]:
    aligns = []
    for cell in split_row(sep):
        if cell.startswith(":") and cell.endswith(":"):
            aligns.append("center")
        elif cell.endswith(":"):
            aligns.append("right")
        else:
            aligns.append("left")
    return aligns


# --------------------------------------------------------------------------- #
# mode="list"
# --------------------------------------------------------------------------- #


def strip_bold(text: str) -> str:
    return BOLD.sub(r"\1", text)


def table_to_list(table: Table, lang: str) -> list[str]:
    """Bold-label bullets. Medium renders these natively and keeps links live."""
    sep = "：" if lang == "zh" else ": "
    joiner = " · "
    lines = []
    for row in table.rows:
        label = strip_bold(row[0]).strip()
        rest = row[1:]
        parts = []
        for i, cell in enumerate(rest, start=1):
            cell = cell.strip()
            if not cell:
                continue
            header = table.headers[i].strip() if i < len(table.headers) else ""
            # A two-column table's second header is always noise ("Value", "內容").
            if header and len(table.headers) > 2:
                parts.append(f"{strip_bold(header)}{sep}{cell}")
            else:
                parts.append(cell)
        body = joiner.join(parts)
        if label and body:
            lines.append(f"- **{label}** — {body}")
        elif label:
            lines.append(f"- **{label}**")
        elif body:
            lines.append(f"- {body}")
    return lines


# --------------------------------------------------------------------------- #
# mode="png"
# --------------------------------------------------------------------------- #


def cell_to_html(text: str) -> str:
    """Inline Markdown to HTML for table images. Links become plain text, since
    a link inside a PNG is not clickable; the URLs are re-emitted below it."""
    codes: list[str] = []

    def stash_code(m: re.Match) -> str:
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = INLINE_CODE.sub(stash_code, text)
    text = INLINE_LINK.sub(r"\1", text)
    text = html.escape(text)
    text = BOLD.sub(r"<b>\1</b>", text)
    text = ITALIC.sub(r"<i>\1</i>", text)

    def restore_code(m: re.Match) -> str:
        return f'<code>{html.escape(codes[int(m.group(1))])}</code>'

    text = re.sub(r"\x00(\d+)\x00", restore_code, text)
    text = text.replace("✅", '<span class="ok">✓</span>')
    text = text.replace("❌", '<span class="no">✗</span>')
    return text


TABLE_FONT = 14.5  # px, matched to the body copy of the article
TABLE_FONT_FLOOR = 11.5  # below this a table image stops being readable


def table_css(font: float) -> str:
    return f"""
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #fff; }}
/* One fixed width for every table image: uniform in the article, and once the
   margin is added it lands on exactly CONTENT_WIDTH, so the browser displays
   it 1:1 and Medium never has to upscale a narrow one. */
#cap {{ display: inline-block; width: {CONTENT_WIDTH - TABLE_MARGIN * 2}px; }}
/* Only data cells are held to one line. A header wrapping onto a second line is
   ordinary table typography; a wrapped data row is what looks broken. */
#cap.nowrap td {{ white-space: nowrap; }}
table {{
  border-collapse: collapse; width: 100%; table-layout: auto;
  font: 400 {font}px/1.5 {SANS}; color: #1a1a1a;
}}
thead th {{
  text-align: left; font-weight: 700; font-size: {font * 0.79:.2f}px;
  letter-spacing: .04em; text-transform: uppercase; color: #6b6b6b;
  padding: 0 11px 7px; border-bottom: 2px solid #2f2f2f;
}}
/* Upper-casing a header that mixes CJK with Latin looks like a shouting typo. */
thead th.cjk {{
  text-transform: none; letter-spacing: 0; font-size: {font * 0.86:.2f}px;
}}
tbody td {{ padding: 7px 11px; border-bottom: 1px solid #e8e8e8; vertical-align: top; }}
tbody tr:last-child td {{ border-bottom: 2px solid #2f2f2f; }}
td.right, th.right {{ text-align: right; }}
td.center, th.center {{ text-align: center; }}
code {{
  font: 400 {font * 0.9:.2f}px {MONO}; background: #f2f2f2;
  padding: 1px 4px; border-radius: 3px;
}}
b {{ font-weight: 700; color: #000; }}
.ok {{ color: #1a7f45; font-weight: 700; }}
.no {{ color: #bf2f24; font-weight: 700; }}
"""

# scrollWidth reveals whether holding data cells to one line pushed the table
# wider than its container, which a fixed-width container's own rect cannot show.
MEASURE_JS = """
const cap = document.getElementById('cap');
const r = cap.getBoundingClientRect();
document.documentElement.setAttribute('data-wh', [
  Math.ceil(r.width), Math.ceil(r.height),
  Math.ceil(cap.querySelector('table').scrollWidth)].join('x'));
"""


CJK = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]")


def table_to_html_page(table: Table, variant: str = "", font: float = TABLE_FONT) -> str:
    thead = ""
    if table.has_headers:
        cells = "".join(
            f'<th class="{table.aligns[i]}{" cjk" if CJK.search(h) else ""}">'
            f"{cell_to_html(h)}</th>"
            for i, h in enumerate(table.headers)
        )
        thead = f"<thead><tr>{cells}</tr></thead>"
    body_rows = []
    for row in table.rows:
        cells = "".join(
            f'<td class="{table.aligns[i] if i < len(table.aligns) else "left"}">'
            f"{cell_to_html(c)}</td>"
            for i, c in enumerate(row)
        )
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<style>{table_css(font)}</style></head><body>"
        f"<div id='cap' class='{variant}'>"
        f"<table>{thead}<tbody>{''.join(body_rows)}</tbody></table></div>"
        f"<script>{MEASURE_JS}</script></body></html>"
    )


def find_chromium() -> str:
    env = os.environ.get("CHROME")
    if env and Path(env).exists():
        return env
    cache = Path.home() / ".cache" / "ms-playwright"
    candidates = sorted(cache.glob("chromium-*/chrome-linux64/chrome"), reverse=True)
    if candidates:
        return str(candidates[0])
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit(
        "No Chromium found. Set CHROME=/path/to/chrome or install Playwright's browser."
    )


def fontconfig_env() -> dict[str, str]:
    """Scoped fontconfig that adds the Windows font directory, so we get a real
    Traditional Chinese UI face without touching the user's global config."""
    env = dict(os.environ)
    if not WINDOWS_FONTS.is_dir():
        return env
    conf_dir = Path(tempfile.gettempdir()) / "medium-prep-fontconfig"
    conf_dir.mkdir(parents=True, exist_ok=True)
    conf = conf_dir / "fonts.conf"
    conf.write_text(
        '<?xml version="1.0"?>'
        '<!DOCTYPE fontconfig SYSTEM "fonts.dtd">'
        "<fontconfig>"
        '<include ignore_missing="yes">/etc/fonts/fonts.conf</include>'
        f"<dir>{WINDOWS_FONTS}</dir>"
        f"<cachedir>{conf_dir / 'cache'}</cachedir>"
        "</fontconfig>",
        encoding="utf-8",
    )
    env["FONTCONFIG_FILE"] = str(conf)
    return env


def chrome_flags(chrome: str) -> list[str]:
    return [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--default-background-color=FFFFFFFF",
    ]


def measure_page(page: str, chrome: str, env: dict) -> tuple[int, int, int]:
    """Chromium screenshots the whole window rather than the content, so ask the
    page how big it is first; that avoids clipped rows and trailing whitespace.

    Returns the container width and height plus the table's own width.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(page)
        path = f.name
    try:
        dom = subprocess.run(
            chrome_flags(chrome) + ["--dump-dom", f"file://{path}"],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        ).stdout
    finally:
        os.unlink(path)
    match = re.search(r'data-wh="(\d+)x(\d+)x(\d+)"', dom)
    if not match:
        raise SystemExit("Could not measure table")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def fit_font(table: Table, chrome: str, env: dict) -> tuple[float, bool]:
    """Pick the largest font that keeps every data row on a single line.

    English cells run longer than their Chinese equivalents, and a table that
    wraps into ragged two-line rows reads worse than the same table half a point
    smaller. Table width is close to linear in font size, so each measurement
    gives a good estimate of the size that would fit.
    """
    inner_width = CONTENT_WIDTH - TABLE_MARGIN * 2
    font = TABLE_FONT
    for _ in range(3):
        *_, table_width = measure_page(table_to_html_page(table, "nowrap", font), chrome, env)
        if table_width <= inner_width:
            return font, True
        # 0.99 absorbs the cell padding, which does not shrink with the font.
        estimate = font * inner_width / table_width * 0.99
        if estimate < TABLE_FONT_FLOOR:
            return TABLE_FONT_FLOOR, False
        # Tidy half-pixel steps, and always at least one step down.
        font = min(math.floor(estimate * 2) / 2, font - 0.5)
    return font, False


def render_table_png(
    table: Table, out_path: Path, chrome: str, env: dict
) -> tuple[float, bool]:
    """Screenshot one table at exactly the article's column width."""
    font, nowrap = fit_font(table, chrome, env)
    page = table_to_html_page(table, "nowrap" if nowrap else "", font)
    container, height, table_width = measure_page(page, chrome, env)
    width = max(container, table_width)

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(page)
        page_path = f.name
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            chrome_flags(chrome)
            + [
                f"--force-device-scale-factor={SCALE}",
                f"--window-size={width + 8},{height + 8}",
                f"--screenshot={out_path}",
                f"file://{page_path}",
            ],
            capture_output=True,
            env=env,
            timeout=120,
            check=True,
        )
    finally:
        os.unlink(page_path)

    # Trimming to the real ink and re-padding makes the result independent of
    # how the CSS happened to lay out the surrounding whitespace.
    trim_and_pad(out_path, pad=TABLE_MARGIN * SCALE)
    return font, nowrap


def trim_and_pad(path: Path, pad: int) -> None:
    from PIL import Image, ImageChops

    image = Image.open(path).convert("RGB")
    background = Image.new("RGB", image.size, (255, 255, 255))
    bbox = ImageChops.difference(image, background).getbbox()
    if not bbox:
        return
    cropped = image.crop(bbox)
    canvas = Image.new("RGB", (cropped.width + pad * 2, cropped.height + pad * 2), (255, 255, 255))
    canvas.paste(cropped, (pad, pad))
    canvas.save(path, optimize=True)


# --------------------------------------------------------------------------- #
# Rewriting the document
# --------------------------------------------------------------------------- #


def rewrite(lang: str, skip_images: bool) -> tuple[str, list[str]]:
    src = (SRC_DIR / SOURCES[lang]).read_text(encoding="utf-8").split("\n")
    chrome = None if skip_images else find_chromium()
    env = fontconfig_env()

    out: list[str] = []
    gist_blocks: list[str] = []
    table_index = 0
    i = 0

    while i < len(src):
        line = src[i]
        if not line.startswith("|"):
            out.append(rewrite_image_paths(line))
            i += 1
            continue

        block = []
        while i < len(src) and src[i].startswith("|"):
            block.append(src[i])
            i += 1

        table_index += 1
        headers = split_row(block[0])
        aligns = parse_aligns(block[1])
        rows = [split_row(r) for r in block[2:]]
        table = Table(table_index, headers, aligns, rows)
        plan = TABLE_PLAN.get(table_index, TablePlan("list"))

        if plan.mode == "list":
            out.extend(table_to_list(table, lang))
        elif plan.mode == "gist":
            labels = GIST_LABELS[lang]
            out.append(labels["note"])
            out.append("")
            out.append(f"<!-- {labels['placeholder']} -->")
            out.append("GIST_URL_HERE")
            gist_blocks.append("\n".join(block))
        elif plan.mode == "png":
            filename = f"{plan.slug}-{lang}.png"
            alt = plan.alt.get(lang, "")
            if not skip_images:
                print(f"  rendering {filename}", file=sys.stderr)
                font, nowrap = render_table_png(table, TABLE_IMG_DIR / filename, chrome, env)
                if not nowrap:
                    print(f"    wraps even at {font}px", file=sys.stderr)
                elif font != TABLE_FONT:
                    print(f"    narrowed to {font}px to avoid wrapping", file=sys.stderr)
            out.append(f"![{alt}]({IMG_URL_BASE}/tables/{filename})")
            links = collect_links(table)
            if links:
                rendered = "、".join(links) if lang == "zh" else ", ".join(links)
                out.append("")
                out.append(f"*{LINK_NOTE[lang]}{rendered}*")

    return "\n".join(out), gist_blocks


def collect_links(table: Table) -> list[str]:
    """Links inside a table die when the table becomes an image; re-emit them."""
    seen: list[str] = []
    for row in table.rows:
        for cell in row:
            for text, url in INLINE_LINK.findall(cell):
                markdown = f"[{strip_bold(text)}]({url})"
                if markdown not in seen:
                    seen.append(markdown)
    return seen


def rewrite_image_paths(line: str) -> str:
    """Medium's importer fetches images over HTTPS; relative paths silently break."""
    return re.sub(
        r"(!\[[^\]]*\]\()\./images/([^)]+)(\))",
        lambda m: f"{m.group(1)}{IMG_URL_BASE}/{m.group(2)}{m.group(3)}",
        line,
    )


# --------------------------------------------------------------------------- #
# Markdown to Medium-friendly HTML
# --------------------------------------------------------------------------- #


def inline_to_html(text: str) -> str:
    codes: list[str] = []

    def stash_code(m: re.Match) -> str:
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = INLINE_CODE.sub(stash_code, text)
    links: list[tuple[str, str]] = []

    def stash_link(m: re.Match) -> str:
        links.append((m.group(1), m.group(2)))
        return f"\x01{len(links) - 1}\x01"

    text = INLINE_LINK.sub(stash_link, text)
    text = html.escape(text)
    text = BOLD.sub(r"<strong>\1</strong>", text)
    text = ITALIC.sub(r"<em>\1</em>", text)

    def restore_link(m: re.Match) -> str:
        label, url = links[int(m.group(1))]
        label = html.escape(label)
        label = BOLD.sub(r"<strong>\1</strong>", label)
        label = re.sub(r"\x00(\d+)\x00", lambda c: f"<code>{html.escape(codes[int(c.group(1))])}</code>", label)
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'

    text = re.sub(r"\x01(\d+)\x01", restore_link, text)
    text = re.sub(
        r"\x00(\d+)\x00",
        lambda m: f"<code>{html.escape(codes[int(m.group(1))])}</code>",
        text,
    )
    return text


# A whole line wrapped in parentheses or italics is an aside about the block
# above it — a unit note, a source credit — not part of the argument.
NOTE_LINE = re.compile(r"^(?:\*([^*].*?)\*|（(.*)）|\((.*)\))$")
CAP_MARK = "<!--CAP-->"
GLOSSARY_HEADINGS = {"專有名詞", "Glossary"}


def markdown_to_html(markdown: str, lang: str) -> str:
    """Deliberately minimal: only the constructs Medium accepts on import.
    Tables are already gone by this point."""
    lines = markdown.split("\n")
    body: list[str] = []
    i = 0
    list_open: str | None = None
    last_figure: int | None = None  # index in `body`, still open for a caption
    after_h1 = False
    in_glossary = False

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            body.append(f"</{list_open}>")
            list_open = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            close_list()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            body.append(f"<pre><code>{html.escape(chr(10).join(code))}</code></pre>")
            last_figure, after_h1 = None, False
            continue

        if not stripped:
            close_list()
            i += 1
            continue

        if stripped.startswith("<!--"):
            body.append(line)
            i += 1
            continue

        if re.fullmatch(r"-{3,}|\*{3,}", stripped):
            close_list()
            body.append("<hr>")
            last_figure, after_h1 = None, False
            i += 1
            continue

        heading = re.match(r"(#{1,3})\s+(.*)", stripped)
        if heading:
            close_list()
            level = len(heading.group(1))
            text = heading.group(2)
            body.append(f"<h{level}>{inline_to_html(text)}</h{level}>")
            last_figure = None
            after_h1 = level == 1
            if level <= 2:
                in_glossary = text.strip() in GLOSSARY_HEADINGS
            i += 1
            continue

        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", stripped)
        if image:
            close_list()
            alt = html.escape(image.group(1), quote=True)
            body.append(
                f'<figure><img src="{html.escape(image.group(2), quote=True)}" alt="{alt}">'
                f"<figcaption>{inline_to_html(image.group(1))}{CAP_MARK}</figcaption></figure>"
            )
            last_figure = len(body) - 1
            after_h1 = False
            i += 1
            continue

        # Unit notes and source credits belong to the figure above them: as a
        # caption Medium renders them small and grey instead of as body copy.
        note = NOTE_LINE.fullmatch(stripped)
        if note and not after_h1:
            inner = next(g for g in note.groups() if g is not None)
            rendered = inline_to_html(inner)
            if last_figure is not None:
                figure = body[last_figure]
                separator = " · " if not figure.endswith(f"<figcaption>{CAP_MARK}</figcaption></figure>") else ""
                body[last_figure] = figure.replace(CAP_MARK, f"{separator}{rendered}{CAP_MARK}")
            else:
                close_list()
                body.append(f'<p class="aux">{rendered}</p>')
            i += 1
            continue

        # Anything below is real content, so the figure above stops accepting
        # captions and the subtitle slot after the title is spent.
        last_figure, after_h1 = None, False

        if stripped.startswith("> "):
            close_list()
            quote = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote.append(lines[i].strip()[2:])
                i += 1
            body.append(f"<blockquote><p>{inline_to_html(' '.join(quote))}</p></blockquote>")
            continue

        bullet = re.match(r"[-*]\s+(.*)", stripped)
        if bullet:
            if list_open != "ul":
                close_list()
                body.append('<ul class="glossary">' if in_glossary else "<ul>")
                list_open = "ul"
            body.append(f"<li>{inline_to_html(bullet.group(1))}</li>")
            i += 1
            continue

        numbered = re.match(r"\d+\.\s+(.*)", stripped)
        if numbered:
            if list_open != "ol":
                close_list()
                body.append("<ol>")
                list_open = "ol"
            body.append(f"<li>{inline_to_html(numbered.group(1))}</li>")
            i += 1
            continue

        close_list()
        body.append(f"<p>{inline_to_html(stripped)}</p>")
        i += 1

    close_list()
    body = [block.replace(CAP_MARK, "") for block in body]
    title = re.search(r"^#\s+(.*)", markdown, re.M)
    return (
        "<!doctype html>\n"
        f'<html lang="{"zh-Hant" if lang == "zh" else "en"}">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title.group(1)) if title else 'Article'}</title>\n"
        "<style>\n"
        f"body {{ max-width: {CONTENT_WIDTH}px; margin: 3rem auto; padding: 0 1.25rem;\n"
        f"  font: 400 17px/1.75 {SANS}; color: #242424; }}\n"
        "h1 { font-size: 1.85rem; line-height: 1.3; margin: 2.5rem 0 .75rem; }\n"
        "h2 { font-size: 1.32rem; margin: 2.75rem 0 .5rem; }\n"
        "h3 { font-size: 1.06rem; margin: 2rem 0 .4rem; }\n"
        "p, li { margin: .85rem 0; }\n"
        f"pre {{ background: #f6f6f6; padding: .9rem 1rem; overflow-x: auto;\n"
        f"  font: 400 13.5px/1.55 {MONO}; }}\n"
        f"code {{ background: #f2f2f2; padding: 1px 5px; font: 400 .85em {MONO}; }}\n"
        "pre code { background: none; padding: 0; }\n"
        "img { max-width: 100%; height: auto; display: block; margin: 0 auto; }\n"
        "figure { margin: 1.85rem 0; }\n"
        "figcaption { font-size: .78rem; line-height: 1.5; color: #757575;\n"
        "  text-align: center; margin-top: .55rem; }\n"
        "/* Unit notes, source credits and the glossary are reference material:\n"
        "   at body size they compete with the argument for attention. */\n"
        ".aux { font-size: .82rem; line-height: 1.6; color: #757575; }\n"
        "ul.glossary { font-size: .87rem; line-height: 1.65; color: #3d3d3d; }\n"
        "ul.glossary li { margin: .5rem 0; }\n"
        "blockquote { border-left: 3px solid #242424; margin: 1.5rem 0;\n"
        "  padding: 0 0 0 1.25rem; color: #4a4a4a; }\n"
        "hr { border: none; border-top: 1px solid #e6e6e6; margin: 2.5rem 0; }\n"
        "a { color: inherit; text-decoration: underline; }\n"
        "</style>\n</head>\n<body>\n" + "\n".join(body) + "\n</body>\n</html>\n"
    )


# --------------------------------------------------------------------------- #


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("langs", nargs="*", default=["zh"], choices=["zh", "en"])
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="reuse existing table PNGs instead of re-rendering them",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for lang in args.langs:
        print(f"{lang}:", file=sys.stderr)
        markdown, gists = rewrite(lang, args.skip_images)

        md_path = OUT_DIR / f"medium-{lang}.md"
        md_path.write_text(markdown, encoding="utf-8")

        html_path = OUT_DIR / f"medium-{lang}.html"
        html_path.write_text(markdown_to_html(markdown, lang), encoding="utf-8")

        for n, block in enumerate(gists, start=1):
            gist_path = OUT_DIR / f"gist-{lang}-{n}.md"
            gist_path.write_text(block + "\n", encoding="utf-8")
            print(f"  {gist_path.relative_to(REPO)}", file=sys.stderr)

        print(f"  {md_path.relative_to(REPO)}", file=sys.stderr)
        print(f"  {html_path.relative_to(REPO)}", file=sys.stderr)


if __name__ == "__main__":
    main()
