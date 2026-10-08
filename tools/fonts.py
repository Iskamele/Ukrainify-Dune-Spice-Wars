# -*- coding: utf-8 -*-
"""Add Ї ї Є є Ґ ґ to the game's UI fonts, built from the user's own copies.

Two kinds of font ship with the game:
  MSDF  (RGB atlas)  philosopher-*, monda-regular, noto_sans_cjk_*: a multi-
        channel signed distance field, value 0.5 on the outline, rising
        inside at 1/range per pixel. The union of two shapes is the per-
        channel max, exact for the median the shader reads.
  bitmap (RGBA)      noto_sans_bold_shadow_*: a white glyph over a soft black
        shadow. The shadow is the glyph blurred (sigma 1.4) and dropped one
        pixel (fitted on the existing letters, <1% error), so new letters get
        theirs from the same model.

New letters reuse what each font already draws:
  ї  = ï                       (identical shape, the tile is shared)
  Ї  = І + the diaeresis of Ï  (Ï carries serifs in some fonts, І does not)
  Є  = Э mirrored              (italic: mirrored, then re-slanted)
  є  = э mirrored
  Ґ  = Г + an upturn as thick as the stems, rising from the end of the bar
  ґ  = г + the same, proportioned to the x-height

The new tiles go into a strip appended to the bottom of each atlas, so no
existing glyph moves.

Usage:
    python tools/fonts.py [--game <D4X folder>] [--preview]
        writes local/fonts/out/<font>.fnt/.png (and preview.png)
"""
import io, os, sys
import numpy as np
from PIL import Image
import d4x, bfnt

PAD = 3                                          # px between tiles: > field range, no bleed when filtering
SHADOW = dict(sigma=1.4, oy=1.0, k=1.04)
TICK = {'Ґ': 0.25, 'ґ': 0.30}                     # upturn height, share of the letter's height


# --------------------------------------------------------------- layers ---
class Layer:
    """A glyph image placed in pen space: (dx, dy) is the top-left corner
    relative to the pen, as in a BFNT glyph."""

    def __init__(self, a, dx, dy):
        self.a, self.dx, self.dy = a, dx, dy

    @property
    def h(self):
        return self.a.shape[0]

    @property
    def w(self):
        return self.a.shape[1]


def union(layers):
    x0 = min(l.dx for l in layers)
    y0 = min(l.dy for l in layers)
    x1 = max(l.dx + l.w for l in layers)
    y1 = max(l.dy + l.h for l in layers)
    out = np.zeros((y1 - y0, x1 - x0) + layers[0].a.shape[2:], dtype=np.float64)
    for l in layers:
        sl = out[l.dy - y0:l.dy - y0 + l.h, l.dx - x0:l.dx - x0 + l.w]
        np.maximum(sl, l.a, out=sl)
    return Layer(out, x0, y0)


def blur(a, sigma):
    r = max(1, int(np.ceil(3 * sigma)))
    x = np.arange(-r, r + 1)
    k = np.exp(-x ** 2 / (2 * sigma ** 2))
    k /= k.sum()
    a = np.pad(a, r)
    a = np.apply_along_axis(lambda v: np.convolve(v, k, 'same'), 0, a)
    a = np.apply_along_axis(lambda v: np.convolve(v, k, 'same'), 1, a)
    return a[r:-r, r:-r]


def sample(a, xs, ys):
    """bilinear lookup of a (H,W[,C]) at float coords, 0 outside"""
    h, w = a.shape[:2]
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    fx, fy = xs - x0, ys - y0
    if a.ndim == 3:
        fx, fy = fx[..., None], fy[..., None]

    def at(y, x):
        ok = (x >= 0) & (x < w) & (y >= 0) & (y < h)
        v = a[np.clip(y, 0, h - 1), np.clip(x, 0, w - 1)]
        return np.where(ok[..., None] if a.ndim == 3 else ok, v, 0)
    return (at(y0, x0) * (1 - fx) * (1 - fy) + at(y0, x0 + 1) * fx * (1 - fy) +
            at(y0 + 1, x0) * (1 - fx) * fy + at(y0 + 1, x0 + 1) * fx * fy)


# ----------------------------------------------------------------- font ---
class UIFont:
    def __init__(self, name, fnt_bytes, png_bytes):
        self.name = name
        self.font = bfnt.Font(fnt_bytes)
        self.atlas = Image.open(io.BytesIO(png_bytes))
        self.atlas.load()
        self.msdf = self.atlas.mode == 'RGB'
        self.px = np.asarray(self.atlas, dtype=np.float64) / 255
        self.range = self._field_range() if self.msdf else 1.0
        self.slant = self._slant()

    # a glyph as a layer: MSDF channels, or the white core of a bitmap glyph
    def layer(self, ch):
        g = self.font.glyphs[ord(ch)]
        t = self.px[g.y:g.y + g.h, g.x:g.x + g.w]
        if self.msdf:
            return Layer(t[:, :, :3].copy(), g.dx, g.dy)
        return Layer(t[:, :, :3].mean(axis=2) * t[:, :, 3], g.dx, g.dy)

    def inside(self, layer):
        return (np.median(layer.a, axis=2) if self.msdf else layer.a) > 0.5

    def _field_range(self):
        med = np.median(self.layer('І').a, axis=2)
        return 1.0 / np.abs(np.diff(med, axis=1)).max()

    def _slant(self):
        """horizontal shift per pixel of height, from the І stem (0 when upright)"""
        m = self.inside(self.layer('І'))
        rows = [r for r in range(m.shape[0]) if m[r].any()]
        top, bot = rows[len(rows) // 5], rows[-len(rows) // 5]
        c = lambda r: np.nonzero(m[r])[0].mean()
        s = (c(top) - c(bot)) / (bot - top)
        return s if abs(s) > 0.05 else 0.0

    def box(self, x0, x1, y0, y1, base):
        """field (or coverage) of a box spanning pen-space pixels x0..x1,
        y0..y1, sheared with the font's slant around the baseline"""
        m = int(np.ceil(self.range)) + 1 + int(abs(self.slant) * (y1 - y0 + 2))
        lx, ly = x0 - m, y0 - m
        h, w = y1 - y0 + 1 + 2 * m, x1 - x0 + 1 + 2 * m
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
        px, py = xs + lx + 0.5, ys + ly + 0.5
        px = px - self.slant * (base - py)                     # undo the slant, then measure
        dx = np.maximum(x0 - px, px - (x1 + 1))
        dy = np.maximum(y0 - py, py - (y1 + 1))
        out = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))
        inside = np.minimum(np.maximum(dx, dy), 0)
        sd = -(out + inside)                                   # positive inside
        if self.msdf:
            v = np.clip(0.5 + sd / self.range, 0, 1)
            return Layer(np.repeat(v[..., None], 3, axis=2), lx, ly)
        return Layer(np.clip(sd + 0.5, 0, 1), lx, ly)

    # ----------------------------------------------------- new letters ---
    def make_yi(self):
        """Ї: І with the diaeresis lifted off Ï"""
        i_ = self.layer('І')
        ii = self.layer('Ï')
        m = self.inside(ii)
        rows = [r for r in range(m.shape[0]) if m[r].any()]
        gap = next(r for r in range(rows[0], rows[-1]) if not m[r].any())   # first empty row under the dots
        stem_top = next(r for r in range(gap, m.shape[0]) if m[r].any())
        cut = (gap + stem_top) // 2 + 1
        dots = Layer(ii.a[:cut].copy(), ii.dx, ii.dy)
        dm = self.inside(dots)
        im = self.inside(i_)
        mid = im.shape[0] // 2
        dots_c = dots.dx + np.nonzero(dm.any(axis=0))[0].mean()
        stem_c = i_.dx + np.nonzero(im[mid])[0].mean()
        top_i = i_.dy + np.nonzero(im.any(axis=1))[0][0]
        top_ii_stem = ii.dy + stem_top                           # keep the dots' height over the stem
        dots.dx += int(round(stem_c - dots_c))
        dots.dy += top_i - top_ii_stem
        return union([i_, dots]), max(self.font.glyphs[ord('І')].adv,
                                      int(np.ptp(np.nonzero(dm.any(axis=0))[0])) + 3)

    def ink_left(self, layer, y):
        """leftmost inside pixel of a layer on pen row y"""
        m = self.inside(layer)
        r = min(max(y - layer.dy, 0), m.shape[0] - 1)
        cols = np.nonzero(m[r])[0]
        return layer.dx + (cols[0] if len(cols) else 0), layer.dx + (cols[-1] if len(cols) else 0)

    def make_ye(self, src):
        """Є/є: Э/э mirrored, italic re-slanted, then spaced like С/с — the
        letter it really resembles: same left edge, same right bearing"""
        l = self.layer(src)
        g = self.font.glyphs[ord(src)]
        m = Layer(l.a[:, ::-1].copy(), g.adv - (g.dx + g.w), g.dy)
        if self.slant:
            m = self.shear(m, 2 * self.slant)
        es = 'С' if src.isupper() else 'с'
        c = self.layer(es)
        cm = self.inside(c)
        rows = np.nonzero(cm.any(axis=1))[0]
        mid = c.dy + rows[len(rows) // 2]
        c_left, c_right = self.ink_left(c, mid)
        m_left, m_right = self.ink_left(m, mid)
        m.dx += c_left - m_left
        mm = self.inside(m)
        ink_right = m.dx + np.nonzero(mm.any(axis=0))[0][-1]
        c_ink_right = c.dx + np.nonzero(cm.any(axis=0))[0][-1]
        adv = self.font.glyphs[ord(es)].adv + (ink_right - c_ink_right)
        return m, adv

    def shear(self, l, s):
        """x' = x + s * (base - y) in pen space"""
        base = self.font.base_line
        y_top, y_bot = l.dy, l.dy + l.h
        add = [s * (base - y) for y in (y_top, y_bot)]
        x0 = int(np.floor(l.dx + min(add))) - 1
        x1 = int(np.ceil(l.dx + l.w + max(add))) + 1
        ys, xs = np.mgrid[0:l.h, 0:x1 - x0].astype(np.float64)
        py = ys + l.dy + 0.5
        src_x = xs + x0 - s * (base - py) - l.dx
        return Layer(sample(l.a, src_x, ys), x0, l.dy)

    def stem_width(self, ch):
        m = self.inside(self.layer(ch))
        rows = np.nonzero(m.any(axis=1))[0]
        return max(1, int(m[rows[len(rows) * 2 // 3]].sum()))

    def make_ghe(self, src, share):
        """Ґ/ґ: Г/г with an upturn rising from the top-right end of the letter:
        the end of the bar in an upright г, the shoulder of a cursive one"""
        l = self.layer(src)
        m = self.inside(l)
        rows = np.nonzero(m.any(axis=1))[0]
        top, height = rows[0], rows[-1] - rows[0] + 1
        stem_w = self.stem_width('І' if src.isupper() else 'і')
        upper = range(top, top + max(2, int(round(height * 0.3))))
        right = max(np.nonzero(m[r])[0][-1] for r in upper if m[r].any())
        col = max(0, right - stem_w // 2)
        attach = int(np.nonzero(m[:, col])[0][0])               # where the stroke starts in that column
        depth = 0
        while attach + depth < m.shape[0] and m[attach + depth, col] and depth < 2 * stem_w:
            depth += 1
        tick_h = max(2, int(round(height * share)))
        base = self.font.base_line
        y_attach = l.dy + attach
        x1 = l.dx + right - int(round(self.slant * (base - y_attach)))   # unslanted right edge
        tick = self.box(x1 - stem_w + 1, x1, y_attach - tick_h, y_attach + max(1, depth) - 1, base)
        return union([l, tick]), self.font.glyphs[ord(src)].adv

    # ------------------------------------------------------------ build ---
    def build(self):
        """-> (new .fnt bytes, new atlas Image)"""
        made = {}
        made['Ї'] = self.make_yi()
        made['Є'] = self.make_ye('Э')
        made['є'] = self.make_ye('э')
        made['Ґ'] = self.make_ghe('Г', TICK['Ґ'])
        made['ґ'] = self.make_ghe('г', TICK['ґ'])
        kern_from = {'Ї': 'І', 'Є': 'С', 'є': 'с', 'Ґ': 'Г', 'ґ': 'г'}

        # pack into a strip under the existing atlas
        W, H = self.atlas.size
        x, y = PAD, H + PAD
        tiles = []
        strip_h = 0
        for ch, (lay, adv) in made.items():
            if x + lay.w + PAD > W:
                x, y = PAD, y + strip_h + PAD
                strip_h = 0
            tiles.append((ch, lay, adv, x, y))
            x += lay.w + PAD
            strip_h = max(strip_h, lay.h)
        new_h = y + strip_h + PAD
        if self.msdf:
            atlas = Image.new('RGB', (W, new_h), (0, 0, 0))
        else:
            atlas = Image.new('RGBA', (W, new_h), (0, 0, 0, 0))
        atlas.paste(self.atlas, (0, 0))

        font = bfnt.Font(self.font.to_bytes())
        for ch, lay, adv, tx, ty in tiles:
            atlas.paste(self.to_image(lay.a), (tx, ty))
            src = font.glyphs[ord(kern_from[ch])] if ord(kern_from[ch]) in font.glyphs else None
            font.glyphs[ord(ch)] = bfnt.Glyph(tx, ty, lay.w, lay.h, lay.dx, lay.dy, adv,
                                              list(src.kern) if src else [])
        ii = font.glyphs[ord('ï')].copy()                       # ї shares ï's tile
        font.glyphs[ord('ї')] = ii
        return font.to_bytes(), atlas

    def to_image(self, a):
        if self.msdf:
            return Image.fromarray(np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8), 'RGB')
        core = np.clip(a, 0, 1)
        pad = 4
        c = np.pad(core, pad)
        sh = np.clip(SHADOW['k'] * np.roll(blur(c, SHADOW['sigma']), int(SHADOW['oy']), axis=0), 0, 1)
        alpha = c + sh * (1 - c)
        lum = np.where(alpha > 0, c / np.maximum(alpha, 1e-6), 0)
        rgba = np.dstack([lum, lum, lum, alpha])[pad:-pad, pad:-pad]
        return Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), 'RGBA')


def build_all(game):
    """-> {pak path: bytes} for every patched font file"""
    files = {}
    for name in d4x.UI_FONTS:
        fnt = game.pak.read('Font/%s.fnt' % name)
        tile = bfnt.Font(fnt).tile
        uf = UIFont(name, fnt, game.pak.read('Font/%s' % tile))
        new_fnt, atlas = uf.build()
        buf = io.BytesIO()
        atlas.save(buf, 'PNG', optimize=False, compress_level=6)
        files['Font/%s.fnt' % name] = new_fnt
        files['Font/%s' % tile] = buf.getvalue()
    return files


def main():
    d4x.configure_stdout()
    a = sys.argv
    game = d4x.Game(a[a.index('--game') + 1] if '--game' in a else None)
    out = os.path.join(d4x.LOCAL, 'fonts', 'out')
    os.makedirs(out, exist_ok=True)
    files = build_all(game)
    for path, data in files.items():
        with open(os.path.join(out, os.path.basename(path)), 'wb') as f:
            f.write(data)
    print('written  %d font files to %s' % (len(files), os.path.relpath(out, d4x.ROOT)))
    if '--preview' in a:
        import preview
        preview.sheet(out, os.path.join(out, 'preview.png'))
        print('preview  %s' % os.path.relpath(os.path.join(out, 'preview.png'), d4x.ROOT))


if __name__ == '__main__':
    main()
