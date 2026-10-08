# -*- coding: utf-8 -*-
"""Assemble the game's language files from translation/ and the installed game.

Writes (default local/build/):
  lang/texts_ru.xml            Ukrainian UI strings
  lang/export_ru.xml           Ukrainian data.cdb fields
  lang/old/export_ru_old.xml   the English each shipped line was translated
                               from, i.e. the game's current English — cdb.Lang
                               skips a line whose reference differs from data.cdb
  res.compressed1.pak          the three files above plus the UI fonts with
                               Ї ї Є є Ґ ґ (tools/fonts.py). The game mounts
                               res.compressed1.pak over res.compressed.pak, so
                               installing is copying this one file next to it.

A line ships only when it is non-empty, passes every check.py error rule and
its English has not changed since it was translated (src hash). Everything
else falls back to the game's English, never to the Russian.

Everything is generated from the user's own game files plus translation/, so
the output never has to be distributed.

Usage:
    python tools/build.py [--game <D4X folder>] [--out <dir>]
    python tools/build.py --ru         rebuild the shipped Russian through the
                                       same pipeline and compare (self-test)
    python tools/build.py --install    build, then copy res.compressed1.pak into
                                       the game (pick "Русский" in the options)
    python tools/build.py --proofread  ship only the rows marked in
                                       translation/proofreading.csv (tools/proof.py)
    python tools/build.py --release 0.1
                                       --proofread, then pack the pak and the
                                       install note into local/release/*.zip
    python tools/build.py --uninstall  remove it from the game again
"""
import collections, datetime, os, shutil, sys, zipfile
import d4x, check, fonts, proof

PATCH = 'res.compressed1.pak'
MARKER = 'ua-localization.txt'                   # tells our patch from anyone else's

README_TXT = '''Dune: Spice Wars — українська локалізація, версія {version}
Для гри версії {game}. Перекладено {n} рядків ({pct:.0f}%), решта поки англійською.

ВСТАНОВЛЕННЯ
1. Скопіюйте res.compressed1.pak у папку гри, туди, де лежить res.compressed.pak.
   Steam: ПКМ на грі → Керувати → Переглянути локальні файли.
2. У налаштуваннях гри оберіть мову «Русский»: переклад займає цей слот.

ВИДАЛЕННЯ
Видаліть res.compressed1.pak з папки гри. Перевірка цілісності файлів у Steam
його не прибирає.

Після оновлення гри змінені рядки показуються англійською, доки не вийде
нова версія перекладу.

https://github.com/Iskamele/Ukrainify-Dune-Spice-Wars
'''


def arg(name, default=None):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def build(game, entries, out_dir):
    src = d4x.game_strings(game)
    charset = d4x.font_charset(game)
    issues = check.check(entries, src, charset)
    blocked = {key for kind, key, _ in issues if kind in check.ERRORS}
    stale = {key for kind, key, _ in issues if kind == 'stale'}

    texts, export, ref = {}, {}, {}
    skipped = collections.Counter()
    for key, e in entries.items():
        uk = e.get('uk', '')
        if not uk:
            continue
        if key not in src:
            skipped['unknown'] += 1
        elif key in blocked:
            skipped['error'] += 1
        elif key in stale:
            skipped['stale'] += 1
        elif key.startswith('texts:'):
            texts[key] = uk
        else:
            export[key] = uk
            ref[key] = src[key]['en']

    # keep the game's own order so the files diff cleanly against the originals
    order = {k: i for i, k in enumerate(src)}
    texts = dict(sorted(texts.items(), key=lambda kv: order[kv[0]]))
    export = dict(sorted(export.items(), key=lambda kv: order[kv[0]]))
    ref = {k: ref[k] for k in export}

    ru_texts = game.lang_file('texts')
    ru_export = game.lang_file('export')
    files = {
        'lang/texts_%s.xml' % d4x.LANG: d4x.emit_texts(texts, d4x.xml_attrs(ru_texts)),
        'lang/export_%s.xml' % d4x.LANG: d4x.emit_export(export, d4x.xml_attrs(ru_export)),
        'lang/old/export_%s_old.xml' % d4x.LANG: d4x.emit_export(ref, d4x.xml_attrs(game.lang_file('ref'))),
    }
    for name, body in files.items():
        path = os.path.join(out_dir, *name.split('/'))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(body)
    return texts, export, skipped, len(src), {k: v.encode('utf-8') for k, v in files.items()}


def self_test(game, out_dir):
    """Push the shipped Russian through build() and read it back: every
    string must survive unchanged, so the emitters are trustworthy."""
    want_t = {k: v for k, v in d4x.parse_texts(game.lang_file('texts')).items() if v}
    want_e = {k: v for k, v in d4x.parse_export(game.lang_file('export')).items() if v}
    src = d4x.game_strings(game)
    entries = {k: {'uk': v, 'src': d4x.src_hash(src[k]['en'])}
               for k, v in list(want_t.items()) + list(want_e.items()) if k in src}
    texts, export, skipped, _, _ = build(game, entries, out_dir)
    got_t = d4x.parse_texts(open(os.path.join(out_dir, 'lang', 'texts_ru.xml'), encoding='utf-8').read())
    got_e = d4x.parse_export(open(os.path.join(out_dir, 'lang', 'export_ru.xml'), encoding='utf-8').read())
    bad = [k for k in texts if got_t.get(k) != want_t[k]] + [k for k in export if got_e.get(k) != want_e[k]]
    print('self-test: %d texts + %d export lines rebuilt, %d differ after the round trip'
          % (len(texts), len(export), len(bad)))
    print('           not rebuilt: %s' % dict(skipped))
    for k in bad[:10]:
        print('  ', k)
    return not bad


def ours(path):
    try:
        return MARKER in d4x.Pak(path).files
    except Exception:
        return False


def remove_loose(game):
    """early test builds copied texts/export to res/lang, where they would
    shadow the pak's — clear them"""
    for name in ('texts_%s.xml' % d4x.LANG, 'export_%s.xml' % d4x.LANG):
        p = os.path.join(game.dir, 'res', 'lang', name)
        if os.path.isfile(p):
            os.remove(p)
            print('removed  %s' % p)


def main():
    d4x.configure_stdout()
    game = d4x.Game(arg('--game'))
    out_dir = arg('--out', os.path.join(d4x.LOCAL, 'build'))
    print('game     %s  (%s)' % (game.dir, game.version))
    target = os.path.join(game.dir, PATCH)

    if '--uninstall' in sys.argv:
        if os.path.isfile(target):
            if not ours(target):
                sys.exit('%s is not ours — left alone' % target)
            os.remove(target)
            print('removed  %s' % target)
        remove_loose(game)
        return

    if '--ru' in sys.argv:
        sys.exit(0 if self_test(game, os.path.join(d4x.LOCAL, 'selftest')) else 1)

    entries = d4x.load_translation()
    release = arg('--release')
    if release or '--proofread' in sys.argv:
        source = d4x.load_source()
        keys = proof.proofread_keys(source, entries)
        entries = {k: e for k, e in entries.items() if k in keys}
        print('proofread only: %d lines marked in %s' % (len(entries), os.path.basename(proof.PATH)))
        for t, n in proof.dangling(keys, source).most_common(10):
            print('warning  [%s] is not proofread: %d shipped lines show it in English' % (t, n))
    texts, export, skipped, total, files = build(game, entries, out_dir)
    print('shipped  %d texts + %d export lines  (%d of %d strings, %.1f%%)'
          % (len(texts), len(export), len(texts) + len(export), total,
             100.0 * (len(texts) + len(export)) / total))
    if skipped:
        print('held back %s — see tools/check.py' % dict(skipped))

    font_files = fonts.build_all(game)
    print('fonts    %d UI fonts with %s' % (len(font_files) // 2, ' '.join(d4x.ADDED_GLYPHS)))
    files.update(font_files)
    files[MARKER] = ('Dune: Spice Wars — українська локалізація\n'
                     'built %s for game %s\n' % (datetime.date.today().isoformat(), game.version)).encode('utf-8')
    pak = d4x.write_pak(files)
    with open(os.path.join(out_dir, PATCH), 'wb') as f:
        f.write(pak)
    print('written  %s  (%.1f MB)' % (os.path.relpath(os.path.join(out_dir, PATCH), d4x.ROOT), len(pak) / 1e6))

    if release:
        shipped = len(texts) + len(export)
        note = README_TXT.format(version=release, game=game.version, n=shipped, pct=100.0 * shipped / total)
        path = os.path.join(d4x.LOCAL, 'release', 'Dune-Spice-Wars-UA-%s.zip' % release)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr(PATCH, pak)
            z.writestr('Встановлення.txt', '﻿' + note.replace('\n', '\r\n'))
        print('release  %s  (%.1f MB)' % (os.path.relpath(path, d4x.ROOT), os.path.getsize(path) / 1e6))

    if '--install' in sys.argv:
        if os.path.isfile(target) and not ours(target):
            sys.exit('%s exists and is not ours — not overwriting it' % target)
        shutil.copyfile(os.path.join(out_dir, PATCH), target)
        remove_loose(game)
        print('copied   %s  (in the game pick "Русский")' % target)


if __name__ == '__main__':
    main()
