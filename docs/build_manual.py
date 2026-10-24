#!/usr/bin/env python3
"""Render docs/user_manual.md into a styled, self-contained user_manual.html.

The HTML is what the app opens via Help -> User Manual, so it must be
self-contained (no external assets) and readable offline.

Requires the 'markdown' package (build-time only, not a runtime dependency):
    py -m pip install markdown
Then:
    py docs/build_manual.py
"""
import re
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("The 'markdown' package is required: py -m pip install markdown")

HERE = Path(__file__).resolve().parent
SRC = HERE / "user_manual.md"
OUT = HERE / "user_manual.html"

text = SRC.read_text(encoding="utf-8")

# Pull the title/subtitle lines off the top (before '# Contents').
lines = text.splitlines()
title = "StenoLab User Manual"
for ln in lines[:6]:
    m = re.match(r"\*\*(.+?)\*\*", ln.strip())
    if m:
        title = m.group(1).strip()
        break

# Drop the static, Word-anchored "# Contents" block; we generate a fresh,
# linked table of contents from the headings instead.
text = re.sub(r"(?s)^.*?\n# Contents\n.*?(?=^# 1\\?\. )", "", text, count=1, flags=re.M)

md = markdown.Markdown(
    extensions=["tables", "toc", "fenced_code", "sane_lists", "attr_list"],
    extension_configs={"toc": {"title": "Contents", "permalink": False}},
)
body = md.convert(text)
toc = md.toc  # generated, with working in-page links

CSS = """
:root{--fg:#1f252c;--muted:#5b6672;--accent:#178f88;--border:#dce3ec;
--bg:#ffffff;--bg-soft:#f5f8fb;--code:#eef3f8;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.65 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:860px;margin:0 auto;padding:40px 24px 80px;}
h1,h2,h3{line-height:1.25;color:#10211f;}
h1{font-size:2em;margin:1.4em 0 .5em;padding-bottom:.25em;border-bottom:2px solid var(--accent);}
h1:first-of-type{margin-top:0;}
h2{font-size:1.4em;margin:1.8em 0 .5em;padding-bottom:.2em;border-bottom:1px solid var(--border);}
h3{font-size:1.15em;margin:1.4em 0 .4em;}
a{color:var(--accent);text-decoration:none;}
a:hover{text-decoration:underline;}
code{background:var(--code);padding:.12em .35em;border-radius:4px;
font:.9em SFMono-Regular,Consolas,Menlo,monospace;}
pre{background:var(--code);padding:14px 16px;border-radius:8px;overflow:auto;}
pre code{background:none;padding:0;}
table{border-collapse:collapse;width:100%;margin:1em 0;font-size:.95em;}
th,td{border:1px solid var(--border);padding:8px 12px;text-align:left;vertical-align:top;}
th{background:var(--bg-soft);}
tr:nth-child(even) td{background:#fafcfe;}
blockquote{border-left:3px solid var(--accent);margin:1em 0;padding:.2em 1em;color:var(--muted);}
.docheader{margin-bottom:1.5em;}
.docheader .sub{color:var(--muted);font-size:1.05em;margin:.2em 0;}
.toc{background:var(--bg-soft);border:1px solid var(--border);border-radius:10px;
padding:8px 22px;margin:1.5em 0 2.5em;}
.toc .toctitle{font-weight:700;font-size:1.1em;color:#10211f;}
.toc ul{list-style:none;padding-left:1.1em;}
.toc>ul{padding-left:0;}
.toc li{margin:.15em 0;}
hr{border:none;border-top:1px solid var(--border);margin:2em 0;}
@media print{.toc{break-inside:avoid;} a{color:var(--fg);}}
"""

html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<div class="docheader">
<h1>{title}</h1>
<p class="sub">User Manual &mdash; reference for hobbyist users of Plover and on-keyboard steno engines</p>
</div>
<nav class="toc">{toc}</nav>
{body}
</div>
</body>
</html>
"""

OUT.write_text(html, encoding="utf-8")
print(f"wrote {OUT}  ({len(html):,} bytes)")
