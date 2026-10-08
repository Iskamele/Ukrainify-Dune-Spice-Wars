# -*- coding: utf-8 -*-
"""Merge a batch of new or revised lines into translation/.

A batch is a UTF-8 text file, one line per entry, key and text split by a tab:

    texts:menu.quit_game_title<TAB>Вийти з гри
    export:unit/A_Trooper/texts.desc<TAB>Піхотинці — ...

Text uses the same escapes as the translation files (\\n for a line break).

A name and all its declension forms come in one line, the key ending in
"=forms" after the name field:

    export:unit/A_Trooper/texts.name=forms<TAB>піхотинець; піхотинця; піхотинцеві; піхотинця; піхотинцем; піхотинці | піхотинці; піхотинців; піхотинцям; піхотинців; піхотинцями; піхотинцях

  six singular cases | six plural cases, each in the order
  називний; родовий; давальний; знахідний; орудний; місцевий

which fills texts.name (називний, first letter capitalised), the twelve
texts.<case>[Plural].name forms (as written), nominativeLc[Plural] and, where
the game has one, texts.plural.name. A separate texts.name / texts.plural.name
line in the same batch wins over the derived one (for names whose capital
letters the simple rule would get wrong).

Lines starting with # are comments. Every key must exist in
local/source/strings.tsv; each entry is stamped with the fingerprint of the
English it was written against.

Usage:
    python tools/merge.py <batch file> [...]
"""
import sys
import d4x

CASE_ORDER = ['', 'genitive', 'dative', 'accusative', 'instrumental', 'prepositional']


def cap(s):
    i = s.find('|') + 1                       # "Дім|Атрідів": capitalise after the glue
    return s[:i] + s[i:i + 1].upper() + s[i + 1:] if s else s


def expand(base_key, spec, source):
    """'forms' line -> {key: text}"""
    halves = [h.strip() for h in spec.split(' | ')]
    if len(halves) != 2:
        raise ValueError('%s: expected "singular cases | plural cases"' % base_key)
    sing, plur = ([w.strip() for w in h.split(';')] for h in halves)
    if len(sing) != 6 or len(plur) != 6:
        raise ValueError('%s: need 6 + 6 forms, got %d + %d' % (base_key, len(sing), len(plur)))
    head, field = base_key.rsplit('/texts.', 1)            # field: name / shortName / longName
    out = {base_key: cap(sing[0])}
    for case, s, p in zip(CASE_ORDER, sing, plur):
        if case:
            out['%s/texts.%s.%s' % (head, case, field)] = s
            out['%s/texts.%sPlural.%s' % (head, case, field)] = p
    out['%s/texts.nominativeLc.%s' % (head, field)] = sing[0]
    out['%s/texts.nominativeLcPlural.%s' % (head, field)] = plur[0]
    plural_key = '%s/texts.plural.%s' % (head, field)
    if plural_key in source:
        out[plural_key] = cap(plur[0])
    # only keep forms the game actually reads for this name
    return {k: v for k, v in out.items() if k in source}


def edges(en, text):
    """carry the English's leading/trailing whitespace over: it is layout
    (" / Day", "You will lose : "), and editors tend to eat trailing spaces"""
    lead = en[:len(en) - len(en.lstrip())]
    trail = en[len(en.rstrip()):]
    return lead + text.strip() + trail if text.strip() else text


def read_batch(path, source):
    derived, explicit = {}, {}
    with open(path, encoding='utf-8-sig') as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip('\r\n')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            if '\t' not in line:
                raise ValueError('%s:%d: no tab between key and text' % (path, n))
            key, text = line.split('\t', 1)
            key, text = key.strip(), d4x.unesc(text)
            if key.endswith('=forms'):
                base = key[:-len('=forms')]
                if base not in source:
                    raise ValueError('%s:%d: unknown key %s' % (path, n, base))
                derived.update(expand(base, text, source))
            else:
                if key not in source:
                    raise ValueError('%s:%d: unknown key %s' % (path, n, key))
                explicit[key] = edges(source[key]['en'], text)
    derived.update(explicit)
    return derived


def main():
    d4x.configure_stdout()
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    source = d4x.load_source()
    entries = d4x.load_translation()
    changed = 0
    for path in sys.argv[1:]:
        for key, text in read_batch(path, source).items():
            new = {'uk': text, 'src': d4x.src_hash(source[key]['en'])}
            old = entries.get(key) or {}
            if (old.get('uk'), old.get('src')) != (new['uk'], new['src']):
                changed += 1
            entries[key] = new
    files = d4x.save_translation(entries, source)
    print('merged   %d changed lines into %d files' % (changed, len(files)))


if __name__ == '__main__':
    main()
