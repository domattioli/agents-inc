#!/usr/bin/env python3
"""Cut round avatar portraits for the demo clip from docs/assets/logo-wide.png.

usage (any Python with Pillow, e.g. the one manim runs on):
    python make_avatars.py
Writes demo/clip/assets/<role>.png (400x400, round mask, transparent corners).
Boxes are (left, top, right, bottom) pixels in the 1730x909 source image; none
includes the sign text.
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "docs", "assets", "logo-wide.png")
OUT = os.path.join(HERE, "assets")

BOXES = {
    "executive": (850, 180, 1130, 460),     # teal horned boss
    "orchestrator": (370, 175, 590, 395),   # purple, round glasses
    "workhorse": (535, 505, 785, 755),      # green turtle at keyboards
    "grunt": (110, 445, 310, 645),          # chameleon with headset
    "reviewer": (1225, 400, 1485, 660),     # lime three-eyed, clipboard
}


def main():
    os.makedirs(OUT, exist_ok=True)
    img = Image.open(SRC).convert("RGBA")
    for name, box in BOXES.items():
        c = img.crop(box).resize((400, 400), Image.LANCZOS)
        mask = Image.new("L", (400, 400), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 399, 399), fill=255)
        c.putalpha(mask)
        c.save(os.path.join(OUT, name + ".png"))
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
