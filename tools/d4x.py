# -*- coding: utf-8 -*-
"""Shared plumbing for the Dune: Spice Wars Ukrainian localisation tools.

The game (Shiro Games, Heaps/HashLink) keeps its text in three places inside
res.compressed.pak:

  texts.xml                  English UI strings, <g id> groups of <t id> leaves
  data.cdb                   CastleDB JSON; English names/descriptions live in
                             columns marked "localizable"
  lang/texts_XX.xml          translation of texts.xml
  lang/export_XX.xml         translation of data.cdb, one element per field
  lang/old/export_XX_old.xml the English each export line was translated from

cdb.Lang applies an export line only while that reference English still equals
the current English in data.cdb ("Ignored since has changed" otherwise), so a
build has to ship a matching reference file next to the translation.

Keys used throughout the tools:
  texts:<group>.<group>.<id>         a texts.xml leaf
  export:<sheet>/<row>/<field>[/...] an export leaf; list items are lineN or
                                     the item's id, props are dotted (texts.name)
"""
import csv, hashlib, html, io, json, os, re, struct, sys, zlib
import xml.etree.ElementTree as ET

STEAM_DEFAULT = r'C:\Program Files (x86)\Steam'
APP_DIR = 'D4X'
PAK_NAME = 'res.compressed.pak'
# The language slot the Ukrainian occupies. The list of languages is compiled
# into the game code; English loads no translation files at all, so a slot of
# another shipped language is used. French: no code special-cases it, and its
# CSS widens a few buttons and panels for longer text.
LANG = 'fr'

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRANSLATION = os.path.join(ROOT, 'translation')
LOCAL = os.path.join(ROOT, 'local')

# declension forms the game reads for names (cdb sub-sheet <sheet>@texts)
CASES = ['genitive', 'genitivePlural', 'dative', 'dativePlural', 'accusative', 'accusativePlural',
         'nominativeLc', 'nominativeLcPlural', 'instrumental', 'instrumentalPlural',
         'prepositional', 'prepositionalPlural']
DECL_RE = re.compile(r'^texts\.(' + '|'.join(CASES) + r')\.(name|shortName|longName)$')


# ------------------------------------------------------------------ game ---
def find_game(path=None):
    """-> the D4X install folder (the one holding res.compressed.pak)."""
    cands = [path] if path else []
    steam = STEAM_DEFAULT
    cands.append(os.path.join(steam, 'steamapps', 'common', APP_DIR))
    vdf = os.path.join(steam, 'steamapps', 'libraryfolders.vdf')
    if os.path.isfile(vdf):
        for lib in re.findall(r'"path"\s+"([^"]+)"', open(vdf, encoding='utf-8', errors='replace').read()):
            cands.append(os.path.join(lib.replace('\\\\', '\\'), 'steamapps', 'common', APP_DIR))
    for c in cands:
        if c and os.path.isfile(os.path.join(c, PAK_NAME)):
            return c
    sys.exit('game not found: pass the D4X folder (the one with %s)' % PAK_NAME)


class Pak:
    """Reader for Heaps' PAK format (hxd.fmt.pak), version 0.

    Header: "PAK" version:u8 headerSize:i32 dataSize:i32, then a file tree:
    name (u8 length + utf8), flags:u8 (1 = directory, 2 = position is a double),
    directories hold a count:i32 of children, files hold position (i32 or f64),
    size:i32 and a checksum:i32. Positions are relative to headerSize."""

    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            head = f.read(12)
            if head[:3] != b'PAK':
                raise ValueError('%s: not a PAK file' % path)
            self.version = head[3]
            self.header_size, = struct.unpack_from('<i', head, 4)
            raw = head + f.read(self.header_size - 12)
        self.files = {}
        self._p = 12
        self._raw = raw
        self._entry('')
        del self._raw

    def _entry(self, parent):
        raw, p = self._raw, self._p
        n = raw[p]; name = raw[p + 1:p + 1 + n].decode('utf-8'); p += 1 + n
        flags = raw[p]; p += 1
        path = parent + '/' + name if parent else name
        if flags & 1:
            count, = struct.unpack_from('<i', raw, p); self._p = p + 4
            for _ in range(count):
                self._entry(path)
        else:
            if flags & 2:
                pos, = struct.unpack_from('<d', raw, p); p += 8
            else:
                pos, = struct.unpack_from('<i', raw, p); p += 4
            size, crc = struct.unpack_from('<iI', raw, p); self._p = p + 8
            self.files[path] = (self.header_size + int(pos), size, crc)

    def read(self, name):
        pos, size, _ = self.files[name]
        with open(self.path, 'rb') as f:
            f.seek(pos)
            return f.read(size)

    def text(self, name):
        return self.read(name).decode('utf-8')


def write_pak(files, align=16):
    """{path: bytes} -> PAK bytes the game's hxd.fmt.pak.Reader accepts.
    Entries of a later pak (res.compressed1.pak, ...) replace those of the
    main one path by path; directories merge."""
    tree = {}
    for path in sorted(files):
        node = tree
        parts = path.split('/')
        for d in parts[:-1]:
            node = node.setdefault(d, {})
        node[parts[-1]] = path
    data, pos = [], {}
    size = 0
    for path in sorted(files):
        size += (-size) % align
        data.append((size, files[path]))
        pos[path] = size
        size += len(files[path])

    def entry(name, node):
        b = name.encode('utf-8')
        out = struct.pack('<B', len(b)) + b
        if isinstance(node, dict):
            out += struct.pack('<Bi', 1, len(node))
            for k in sorted(node):
                out += entry(k, node[k])
        else:
            blob = files[node]
            out += struct.pack('<BiiI', 0, pos[node], len(blob), zlib.adler32(blob) & 0xffffffff)
        return out
    body = entry('', tree)
    header_size = 12 + len(body) + 4
    blob = bytearray(b'PAK\0' + struct.pack('<ii', header_size, size) + body + b'DATA')
    for p, d in data:
        blob += b'\0' * (header_size + p - len(blob))
        blob += d
    return bytes(blob)


class Game:
    def __init__(self, path=None):
        self.dir = find_game(path)
        self.pak = Pak(os.path.join(self.dir, PAK_NAME))
        self.version = self.pak.text('version').strip()
        self._cdb = None

    @property
    def cdb(self):
        if self._cdb is None:
            self._cdb = json.loads(self.pak.text('data.cdb'))
        return self._cdb

    def lang_file(self, kind):
        """kind: texts | export | ref"""
        return self.pak.text({'texts': 'lang/texts_%s.xml', 'export': 'lang/export_%s.xml',
                              'ref': 'lang/old/export_%s_old.xml'}[kind] % LANG)


# ------------------------------------------------------- texts.xml format ---
def _inner(e):
    """Inner XML exactly as stored, edge whitespace included: a trailing
    no-break space is how "Shadout" joins "Mapes", for instance."""
    s = html.escape(e.text or '', quote=False) + ''.join(ET.tostring(c, encoding='unicode') for c in e)
    return s.replace('<br />', '<br/>')


def parse_texts(xml):
    """texts.xml / texts_XX.xml -> {key: inner xml}. Inline markup
    (<warning>, <good>, <br/>, ...) is kept as written."""
    out = {}

    def walk(e, groups):
        for c in e:
            if c.tag == 'g':
                walk(c, groups + [c.get('id')])
            elif c.tag == 't':
                out['texts:' + '.'.join(groups + [c.get('id')])] = _inner(c)
    walk(ET.fromstring(xml), [])
    return out


def emit_texts(items, attrs):
    """{key: inner xml} -> texts_XX.xml. Groups are rebuilt from the keys."""
    tree = {}
    for key, val in items.items():
        parts = key[len('texts:'):].split('.')
        node = tree
        for g in parts[:-1]:
            node = node.setdefault(('g', g), {})
        node[('t', parts[-1])] = val
    out = ['<texts %s>' % ' '.join('%s="%s"' % (k, html.escape(v)) for k, v in attrs.items())]

    def write(node, depth):
        pad = '    ' * depth
        for (kind, name), v in node.items():
            if kind == 't':
                out.append('%s<t id="%s">%s</t>' % (pad, html.escape(name), v))
            else:
                out.append('%s<g id="%s">' % (pad, html.escape(name)))
                write(v, depth + 1)
                out.append('%s</g>' % pad)
    write(tree, 1)
    out.append('</texts>')
    return '\n'.join(out) + '\n'


# ------------------------------------------------------ export.xml format ---
# A field value is stored in the XML html-escaped, with newlines as <br/>.
def xml_to_plain(inner):
    return html.unescape(re.sub(r'<br\s*/>', '\n', inner))


def plain_to_xml(text):
    return (text.replace('\r', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('\n', '<br/>'))


def parse_export(xml):
    """export_XX.xml -> {key: plain text}"""
    out = {}

    def walk(e, path):
        kids = [c for c in e if c.tag != 'br']
        if not kids:
            out['export:' + '/'.join(path)] = xml_to_plain(_inner(e))
            return
        for c in kids:
            walk(c, path + [c.tag])
    for sheet in ET.fromstring(xml):
        walk(sheet, [sheet.get('name')])
    return out


def emit_export(items, attrs):
    """{key: plain text} -> export_XX.xml. Element nesting is rebuilt from the
    keys, so the output only holds what is being shipped."""
    tree = {}
    for key, val in items.items():
        parts = key[len('export:'):].split('/')
        node = tree
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = val
    out = ['<cdb %s>' % ' '.join('%s="%s"' % (k, html.escape(v)) for k, v in attrs.items())]

    def write(node, depth):
        pad = '    ' * depth
        for name, v in node.items():
            if isinstance(v, dict):
                out.append('%s<%s>' % (pad, name))
                write(v, depth + 1)
                out.append('%s</%s>' % (pad, name))
            else:
                out.append('%s<%s>%s</%s>' % (pad, name, plain_to_xml(v), name))
    for sheet, node in tree.items():
        out.append('    <sheet name="%s">' % html.escape(sheet))
        write(node, 2)
        out.append('    </sheet>')
    out.append('</cdb>')
    return '\n'.join(out) + '\n'


def xml_attrs(xml):
    m = re.search(r'<(?:texts|cdb)\b([^>]*)>', xml)
    return dict(re.findall(r'(\w+)="([^"]*)"', m.group(1))) if m else {}


# --------------------------------------------------------- data.cdb walk ---
def cdb_sources(cdb):
    """-> {key: current English} for every localizable field, the way
    cdb.Lang.buildXML lays them out, plus {decl_key: base_key} for the
    declension forms that only exist in translations."""
    sheets = {s['name']: s for s in cdb['sheets']}
    loc_cache = {}

    def has_loc(name):
        if name not in loc_cache:
            loc_cache[name] = False
            loc_cache[name] = any(c.get('kind') == 'localizable' or
                                  (c['typeStr'] in ('8', '17') and has_loc(name + '@' + c['name']))
                                  for c in sheets[name]['columns'])
        return loc_cache[name]

    def id_col(name):
        return next((c['name'] for c in sheets[name]['columns'] if c['typeStr'] == '0'), None)

    def walk(sname, obj, prefix, path, out):
        for c in sheets[sname]['columns']:
            field, v = prefix + c['name'], obj.get(c['name'])
            sub = sname + '@' + c['name']
            if c.get('kind') == 'localizable' and c['typeStr'] == '1':
                if isinstance(v, str) and v != '':
                    out['/'.join(path + [field])] = v
            elif c['typeStr'] == '17' and isinstance(v, dict) and has_loc(sub):
                walk(sub, v, field + '.', path, out)
            elif c['typeStr'] == '8' and isinstance(v, list) and has_loc(sub):
                ic = id_col(sub)
                for i, item in enumerate(v):
                    if item.get('__ignoreLoc__'):
                        continue
                    tag = item.get(ic) if ic and item.get(ic) else 'line%d' % i
                    walk(sub, item, '', path + [field, tag], out)

    raw = {}
    for s in cdb['sheets']:
        name = s['name']
        if '@' in name or s.get('props', {}).get('hide') or not has_loc(name):
            continue
        ic = id_col(name)
        for i, line in enumerate(s.get('lines', [])):
            if line.get('__ignoreLoc__'):
                continue
            tag = line.get(ic) if ic and line.get(ic) else 'line%d' % i
            walk(name, line, '', [name, tag], raw)
    src = {'export:' + k: v for k, v in raw.items()}

    decl = {}
    for key in src:
        m = re.match(r'^(export:([^/]+)/[^/]+)/texts\.(name|shortName|longName)$', key)
        if not m:
            continue
        tsub = sheets.get(m.group(2) + '@texts')
        if not tsub or 'genitive' not in {c['name'] for c in tsub['columns']}:
            continue
        for case in CASES:
            decl['%s/texts.%s.%s' % (m.group(1), case, m.group(3))] = key
    return src, decl


# --------------------------------------------------------------- markup ---
# Suffixes after a link, [Spice]g, pick a declension field (HText.getDeclination).
# p and s both mean plural; a second p/s pluralises a case: gp == gs.
LINK_SUFFIXES = {'', 'a', 'ap', 'as', 'd', 'dp', 'ds', 'g', 'gp', 'gs', 'i', 'ip', 'is',
                 'l', 'lc', 'lcp', 'lcs', 'lp', 'ls', 'p', 's', 'pr', 'prp', 'prs'}
PLACEHOLDER_RE = re.compile(r'::[\w\-.]+::')
LINK_RE = re.compile(r'\[([^\[\]]+)\]([a-z]*)')
TAG_RE = re.compile(r'</?[a-zA-Z][\w-]*[^<>]*?/?>')


def markup(text):
    """-> (placeholders, link targets, tags), each sorted, for comparing a
    translation against its English. A link target drops what a translation
    may legitimately change: the ! prefix and the -adjective / -shortname /
    -longname variant ([Ecaz-adjective] -> [Ecaz-shortname]g)."""
    return (sorted(PLACEHOLDER_RE.findall(text)),
            sorted(link_target(m.group(1)) for m in LINK_RE.finditer(text)),
            sorted(re.sub(r'\s+', ' ', t) for t in TAG_RE.findall(text)))


def link_target(body):
    return re.sub(r'-(adjective|shortname|longname)$', '', body.lstrip('!'), flags=re.I).lower()


def tags_balanced(text):
    stack = []
    for t in TAG_RE.findall(text):
        name = re.match(r'</?([a-zA-Z][\w-]*)', t).group(1)
        if t.endswith('/>'):
            continue
        if t.startswith('</'):
            if not stack or stack.pop() != name:
                return False
        else:
            stack.append(name)
    return not stack


# hxd.Charset.resolveChar draws these with a stand-in when the font lacks them
FALLBACK = {'\u00a0': ' ', '\u3000': ' ', '\u00ab': '"', '\u00bb': '"', '\u201c': '"', '\u201d': '"',
            '\u201e': '"', '\u2018': "'", '\u2019': "'", '\u00b4': "'", '\u2039': '<', '\u203a': '>',
            '\u2013': '-'}


# ----------------------------------------------------------------- fonts ---
# The fonts the UI draws with. debug_font and regions (Latin capitals for the
# map) never show translated text.
UI_FONTS = ['philosopher-regular', 'philosopher-bold', 'philosopher-italic', 'monda-regular',
            'noto_sans_cjk_large', 'noto_sans_cjk_regular',
            'noto_sans_bold_shadow_12', 'noto_sans_bold_shadow_13']
ADDED_GLYPHS = 'ЇїЄєҐґ'          # what the font stage adds


def bfnt_chars(data):
    """Heaps binary font (hxd.fmt.bfnt, version 1) -> set of code points."""
    if data[:5] != b'BFNT\0' or data[5] != 1:
        raise ValueError('not a BFNT v1 font')
    p = 6
    n, = struct.unpack_from('<H', data, p); p += 2 + n          # font name
    p += 2                                                       # size
    n, = struct.unpack_from('<H', data, p); p += 2 + n          # tile path
    p += 4 + 4                                                   # lineHeight, baseLine, defaultChar
    chars = set()
    while True:
        cid, = struct.unpack_from('<i', data, p); p += 4
        if cid == 0:
            return chars
        chars.add(cid)
        p += 14                                                  # x y w h dx dy advance
        while True:
            prev, = struct.unpack_from('<i', data, p); p += 4
            if prev == 0:
                break
            p += 2


def font_charset(game):
    """Characters every UI font can draw, once the added glyphs are in."""
    common = None
    for name in UI_FONTS:
        cs = bfnt_chars(game.pak.read('Font/%s.fnt' % name))
        common = cs if common is None else common & cs
    return {chr(c) for c in common} | set(ADDED_GLYPHS) | {'\n'}


def game_strings(game):
    """-> {key: {'en', 'base'?}} in the game's own order: everything the
    Ukrainian has to cover. The one definition extract, check and build share.
    Only the English is read.

    Every name whose sheet has case columns gets all twelve forms: a link can
    reach any of them, also through placeholders such as [::target::]g. A
    name nothing declines (a button label) just repeats its nominative."""
    out = {}
    for k, en in parse_texts(game.pak.text('texts.xml')).items():
        if en:
            out[k] = {'en': en}
    src, decl = cdb_sources(game.cdb)
    forms = {}
    for dk, base in decl.items():
        forms.setdefault(base, []).append(dk)
    for k, en in src.items():
        out[k] = {'en': en}
        for dk in forms.get(k, []):                 # forms right after their name
            out[dk] = {'en': en, 'base': k}
    return out


# ------------------------------------------------------------------ tsv ---
# One record per line: tabs, newlines and backslashes are escaped so diffs
# stay line-per-string and Excel never splits a record.
def esc(s):
    return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')


def unesc(s):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t', '\\': '\\'}.get(m.group(1), '\\' + m.group(1)), s)


def read_tsv(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding='utf-8', newline='') as f:
        # a checkout with core.autocrlf turns the record ends into \r\n; real
        # line breaks inside a field are always escaped as \n, so \r never belongs
        lines = f.read().replace('\r\n', '\n').split('\n')
    head = lines[0].split('\t')
    return [dict(zip(head, map(unesc, l.split('\t')))) for l in lines[1:] if l]


def write_tsv(path, head, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write('\t'.join(head) + '\n')
        for r in rows:
            f.write('\t'.join(esc(r.get(h, '') or '') for h in head) + '\n')


def src_hash(text):
    """Fingerprint of the English a line was translated from."""
    return hashlib.sha1(text.strip().encode('utf-8')).hexdigest()[:8]


# ---------------------------------------------------------- translation ---
def translation_files():
    """-> [(file, area)] where area is 'texts' or the export sheet name"""
    out = []
    p = os.path.join(TRANSLATION, 'texts.tsv')
    if os.path.isfile(p):
        out.append((p, 'texts'))
    d = os.path.join(TRANSLATION, 'export')
    if os.path.isdir(d):
        out += [(os.path.join(d, f), f[:-4]) for f in sorted(os.listdir(d)) if f.endswith('.tsv')]
    return out


def file_for(key):
    if key.startswith('texts:'):
        return os.path.join(TRANSLATION, 'texts.tsv')
    return os.path.join(TRANSLATION, 'export', key[len('export:'):].split('/')[0] + '.tsv')


def load_translation():
    """-> {key: {'uk': ..., 'src': ...}}"""
    out = {}
    for path, _ in translation_files():
        for r in read_tsv(path):
            if r.get('key'):
                out[r['key']] = r
    return out


def save_translation(entries, source):
    """Write {key: {'uk', 'src'}} back into translation/, one file per area,
    rows in the game's order. Files are rewritten whole."""
    order = {k: i for i, k in enumerate(source)}
    files = {}
    for key, e in entries.items():
        if e.get('uk'):
            files.setdefault(file_for(key), []).append(dict(e, key=key))
    for path, rows in files.items():
        rows.sort(key=lambda r: order.get(r['key'], len(order)))
        write_tsv(path, ['key', 'src', 'uk'], rows)
    return sorted(files)


def load_source():
    """-> {key: {'en', 'base'}} from local/source (written by extract.py)"""
    path = os.path.join(LOCAL, 'source', 'strings.tsv')
    if not os.path.isfile(path):
        sys.exit('no local/source/strings.tsv — run tools/extract.py first')
    return {r['key']: r for r in read_tsv(path)}


def configure_stdout():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8')
        except Exception:
            pass
