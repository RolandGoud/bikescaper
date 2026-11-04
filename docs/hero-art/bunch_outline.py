"""Draws webapp/static/hero/hero-bunch.svg: the home hero's bunch of bikes, made from the
selling wizard's drive-side photo guide (webapp/static/photo-guide/drive-side.svg).

It strips the guide-only parts (the 1-4 markers, corner brackets, dashed ground line and
the embedded metadata), then places five copies in the same staggered layout as bikes.svg:
two faint at the back, two in the middle, one full-strength in front.

Run from the repo root: python docs/hero-art/bunch_outline.py
"""
import re
from pathlib import Path

SRC = Path("webapp/static/photo-guide/drive-side.svg")
OUT = Path("webapp/static/hero/hero-bunch.svg")

BIKE_LEFT, BIKE_BOTTOM, BIKE_WIDTH = 30, 264.2, 340   # bike's bounds inside the guide's 400x300 box
UNIT_WIDTH = 267                                       # width of a scale-1 bike in bikes.svg
# (left edge, bottom, scale, opacity), back to front, matching bikes.svg
BUNCH = [(110, 250, 1, .4), (370, 256, 1, .4), (20, 300, 1.2, .7), (300, 306, 1.2, .7), (160, 346, 1.4, 1)]


def bike_paths(svg):
    svg = re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.S)
    svg = re.sub(r"<g><circle[^>]*/><text[^>]*>\d</text></g>", "", svg)            # numbered markers
    svg = re.sub(r'<g stroke="#9A9CA6" stroke-width="2.5" fill="none">.*?</g>', "", svg, count=1, flags=re.S)  # corners
    svg = re.sub(r'<path d="M56.4 197.8L343.6 197.8"[^>]*/>', "", svg)                # dashed ground line
    return svg[svg.index(">", svg.index("<svg")) + 1:svg.rindex("</svg>")]


def main():
    inner = bike_paths(SRC.read_text())
    uses = []
    for left, bottom, scale, opacity in BUNCH:
        k = scale * UNIT_WIDTH / BIKE_WIDTH
        uses.append(f'<use href="#bike" transform="translate({left - BIKE_LEFT * k:.1f} {bottom - BIKE_BOTTOM * k:.1f}) '
                    f'scale({k:.4f})" opacity="{opacity}"/>')
    OUT.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 40 720 315" fill="none" '
                   'stroke-linecap="round" stroke-linejoin="round">'
                   f'<defs><g id="bike">{inner}</g></defs>{"".join(uses)}</svg>')


if __name__ == "__main__":
    main()
