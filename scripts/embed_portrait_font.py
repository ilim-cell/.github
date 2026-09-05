#!/usr/bin/env python3
"""Inline the JetBrains Mono subset into ascii.svg.

Run once after scripts/make_portrait.py:
    python3 scripts/embed_portrait_font.py
"""
import base64
import re

FONT_FILE = "scripts/fonts/jbmono-ramp.woff2"

with open(FONT_FILE, "rb") as f:
    b64 = base64.b64encode(f.read()).decode("ascii")

face = (f"@font-face{{font-family:JBMono;src:url(data:font/woff2;base64,{b64}) format('woff2')}}")

with open("ascii.svg", encoding="utf-8") as f:
    svg = f.read()

if "<style>" in svg:
    svg = svg.replace("<style>", f"<style>{face}", 1)
else:
    svg = svg.replace("<svg", f"<svg><style>{face}</style>", 1)

svg = re.sub(
    r'font-family="[^"]*"',
    'font-family="JBMono"',
    svg)

with open("ascii.svg", "w", encoding="utf-8") as f:
    f.write(svg)

print("ascii.svg updated with inlined JetBrains Mono subset")