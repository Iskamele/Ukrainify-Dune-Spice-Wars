# -*- coding: utf-8 -*-
"""Render sample text with BFNT fonts, the way the game lays glyphs out
(pen + dx/dy, advance), to eyeball new letters next to the old ones.

Usage:
    python tools/preview.py <dir with .fnt/.png> [<out.png>]
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw
import d4x, bfnt

SAMPLE = ['Їжак їсть яєчню. Єва є. Ґанок і ґудзик.', 'ІЇЄҐ іїєґ  ЭэГгÏï  Українська мова']


def glyph_image(atlas, g, msdf):
    t = np.asarray(atlas.crop((g.x, g.y, g.x + g.w, g.y + g.h)).convert('RGBA'), dtype=np.float64) / 255
    if msdf:
        med = np.median(t[:, :, :3], axis=2)
        return np.clip((med - 0.5) * 3 + 0.5, 0, 1), None       # coverage
    return t[:, :, 3], t[:, :, :3]


def line(font, atlas, text, scale):
    msdf = atlas.mode == 'RGB'
    w = sum(font.glyphs.get(ord(c), font.glyphs.get(ord('?'))).adv for c in text) + 40
    h = font.line_height + 20
    canvas = np.full((h, w, 3), 0.55 if not msdf else 1.0)
    pen = 10
    for c in text:
        g = font.glyphs.get(ord(c))
        if g is None:
            pen += font.size // 3
            continue
        cov, col = glyph_image(atlas, g, msdf)
        x, y = pen + g.dx, 10 + g.dy
        y0, x0 = max(y, 0), max(x, 0)
        sub = canvas[y0:y + g.h, x0:x + g.w]
        cv = cov[y0 - y:y0 - y + sub.shape[0], x0 - x:x0 - x + sub.shape[1]][..., None]
        if col is None:
            sub[:] = sub * (1 - cv)
        else:
            cc = col[y0 - y:y0 - y + sub.shape[0], x0 - x:x0 - x + sub.shape[1]]
            sub[:] = sub * (1 - cv) + cc * cv
        pen += g.adv
    im = Image.fromarray((canvas * 255).astype(np.uint8), 'RGB')
    return im.resize((im.width * scale, im.height * scale), Image.LANCZOS if msdf else Image.NEAREST)


def sheet(folder, out, names=d4x.UI_FONTS, sample=SAMPLE):
    rows = []
    for n in names:
        font = bfnt.Font(open(os.path.join(folder, n + '.fnt'), 'rb').read())
        atlas = Image.open(os.path.join(folder, font.tile))
        scale = 1 if font.size >= 30 else 2
        for s in sample:
            im = line(font, atlas, s, scale)
            row = Image.new('RGB', (im.width + 230, im.height), 'white')
            ImageDraw.Draw(row).text((4, 4), n, fill='black')
            row.paste(im, (230, 0))
            rows.append(row)
    W = max(r.width for r in rows)
    img = Image.new('RGB', (W, sum(r.height for r in rows)), 'white')
    y = 0
    for r in rows:
        img.paste(r, (0, y))
        y += r.height
    img.save(out)


if __name__ == '__main__':
    d4x.configure_stdout()
    sheet(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.join(sys.argv[1], 'preview.png'))
