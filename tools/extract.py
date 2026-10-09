# -*- coding: utf-8 -*-
"""Pull the translatable text out of the installed game.

Writes local/source/ (never committed — it is the game's own text):
  strings.tsv   key, base, en — every string the Ukrainian has to cover
  game.json     game version, XML header attributes, the font charset

  key   texts:<group>.<id> or export:<sheet>/<row>/<field>...
  base  for a declension form (texts.genitive.name...), the key of the name
        it declines; the form itself has no English of its own
  en    current English (texts.xml / data.cdb)

Only the English is read: no other language of the game is used.

Usage:
    python tools/extract.py [<D4X folder>]
"""
import json, os, sys
import d4x


def main():
    d4x.configure_stdout()
    game = d4x.Game(sys.argv[1] if len(sys.argv) > 1 else None)
    print('game     %s  (%s)' % (game.dir, game.version))

    strings = d4x.game_strings(game)
    out = os.path.join(d4x.LOCAL, 'source')
    d4x.write_tsv(os.path.join(out, 'strings.tsv'), ['key', 'base', 'en'],
                  [dict(v, key=k) for k, v in strings.items()])
    with open(os.path.join(out, 'game.json'), 'w', encoding='utf-8') as f:
        json.dump({'version': game.version,
                   'charset': ''.join(sorted(d4x.font_charset(game)))}, f, ensure_ascii=False, indent=1)

    keys = list(strings)
    n_texts = sum(1 for k in keys if k.startswith('texts:'))
    n_decl = sum(1 for v in strings.values() if v.get('base'))
    n_plural = sum(1 for k in keys if '/texts.plural.' in k)
    print('texts    %5d strings' % n_texts)
    print('export   %5d fields (%d of them plural names) + %d declension forms'
          % (len(keys) - n_texts - n_decl, n_plural, n_decl))
    print('total    %5d' % len(keys))
    print('written  %s' % os.path.relpath(out, d4x.ROOT))


if __name__ == '__main__':
    main()
