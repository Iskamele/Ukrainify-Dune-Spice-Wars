# -*- coding: utf-8 -*-
"""Heaps binary bitmap fonts (hxd.fmt.bfnt, version 1): read and write.

Layout, little endian:
  "BFNT" 0 version:u8
  name: u16 length + utf8      size: i16
  tile: u16 length + utf8      lineHeight: i16   baseLine: i16   defaultChar: i32
  glyphs until a 0 id:
    id:i32 x:u16 y:u16 w:u16 h:u16 dx:i16 dy:i16 advance:i16
    kerning pairs until a 0 id: prev:i32 amount:i16
  0:i32
"""
import struct


class Glyph:
    __slots__ = ('x', 'y', 'w', 'h', 'dx', 'dy', 'adv', 'kern')

    def __init__(self, x, y, w, h, dx, dy, adv, kern=None):
        self.x, self.y, self.w, self.h, self.dx, self.dy, self.adv = x, y, w, h, dx, dy, adv
        self.kern = kern or []                       # [(prev char, amount)]

    def copy(self):
        return Glyph(self.x, self.y, self.w, self.h, self.dx, self.dy, self.adv, list(self.kern))


class Font:
    def __init__(self, data):
        if data[:5] != b'BFNT\0' or data[5] != 1:
            raise ValueError('not a BFNT v1 font')
        p = 6

        def take(fmt):
            nonlocal p
            v = struct.unpack_from('<' + fmt, data, p)
            p += struct.calcsize(fmt)
            return v

        def text():
            nonlocal p
            n, = take('H')
            s = data[p:p + n].decode('utf-8')
            p += n
            return s
        self.name = text()
        self.size, = take('h')
        self.tile = text()
        self.line_height, self.base_line = take('hh')
        self.default_char, = take('i')
        self.glyphs = {}                              # insertion order is file order
        while True:
            cid, = take('i')
            if cid == 0:
                break
            g = Glyph(*take('HHHHhhh'))
            while True:
                prev, = take('i')
                if prev == 0:
                    break
                g.kern.append((prev, take('h')[0]))
            self.glyphs[cid] = g

    def to_bytes(self):
        out = [b'BFNT\0\x01']
        for s in (self.name,):
            b = s.encode('utf-8')
            out.append(struct.pack('<H', len(b)) + b)
        out.append(struct.pack('<h', self.size))
        b = self.tile.encode('utf-8')
        out.append(struct.pack('<H', len(b)) + b)
        out.append(struct.pack('<hhi', self.line_height, self.base_line, self.default_char))
        for cid, g in self.glyphs.items():
            out.append(struct.pack('<iHHHHhhh', cid, g.x, g.y, g.w, g.h, g.dx, g.dy, g.adv))
            for prev, amount in g.kern:
                out.append(struct.pack('<ih', prev, amount))
            out.append(struct.pack('<i', 0))
        out.append(struct.pack('<i', 0))
        return b''.join(out)
