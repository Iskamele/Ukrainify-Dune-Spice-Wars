# -*- coding: utf-8 -*-
"""Validate the translation against the game's current English.

Errors (the build refuses to ship these lines):
  unknown     key no longer exists in the game
  placeholder ::placeholders:: differ from the English (a value would vanish)
  xml         <tags> unbalanced
  suffix      a [link] is followed by letters the game does not know
  glyph       a character no UI font can draw and the engine cannot stand in
              for (ё ы э ъ № tab ...) — it would show as an empty box
  pipe        the number of | list separators differs from the English

Warnings:
  stale       the English changed since the line was translated
  links       [link] targets differ (fine when grammar demands a plain word,
              e.g. [Annex] is the verb "Annex" and cannot be declined)
  tags        <tags> differ from the English
  fallback    a character the engine draws with an ASCII stand-in (’ “ ” –)
  space       leading/trailing whitespace differs from the English
  newline     different number of line breaks
  same        identical to the English
  decl        a translated name has untranslated declension forms
  term        the English uses a glossary term outside a [link] and the
              Ukrainian lacks it (matched on word stems, so declined forms pass)

Usage:
    python tools/check.py                 check translation/
    python tools/check.py --shipped       run the same rules over the game's own
                                          translation in our slot (calibrates
                                          the checker)
    python tools/check.py -v              list every warning too
    python tools/check.py --only markup   list one kind
"""
import collections, csv, json, os, re, sys
import d4x

ERRORS = ('unknown', 'placeholder', 'xml', 'suffix', 'glyph', 'pipe')
WARNINGS = ('stale', 'links', 'tags', 'fallback', 'space', 'newline', 'same', 'decl', 'term')


def load_terms():
    """glossary.csv -> [(english regex, [ukrainian stem regex], 'en -> uk')].
    Only settled rows (book, approved) plus names: proposals still move."""
    path = os.path.join(d4x.TRANSLATION, 'glossary.csv')
    if not os.path.isfile(path):
        return []
    terms = []
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            if not r['uk'] or not (r['status'] in ('book', 'approved') or r['category'] in ('character', 'faction')):
                continue
            for en, uk in zip(r['en'].split(' / '), r['uk'].split(' / ')):
                en, uk = en.strip(), uk.strip()
                if len(en) < 3:
                    continue
                stems = [stem(w) for w in re.findall(r"[\w']+", uk) if len(w) >= 3]
                if stems:
                    # Capitalised terms are names: match them case-sensitively so
                    # "Monitor" (the ship) does not fire on "monitor your assets"
                    flags = 0 if en[:1].isupper() else re.I
                    terms.append((re.compile(r'(?<![\w])' + re.escape(en) + r'(?![\w])', flags), stems,
                                  '%s -> %s' % (en, uk)))
    return terms


def stem(word):
    """A forgiving Ukrainian stem: drop the ending, let і/о alternate
    (Дім/Дому), ignore case and apostrophes."""
    w = word.lower().replace("'", '')
    if w.endswith('ець') and len(w) > 5:          # продавець / продавці: the е drops out
        w = w[:-3]
    elif len(w) > 4:
        w = w[:-2]
    elif len(w) == 4:
        w = w[:-1]
    return re.compile(re.escape(w).replace('і', '[іо]'), re.I)


def check(entries, source, charset, terms=None):
    """entries: {key: {'uk', 'src'}} -> [(kind, key, message)]"""
    issues = []
    terms = load_terms() if terms is None else terms
    add = lambda kind, key, msg: issues.append((kind, key, msg))
    for key, e in entries.items():
        uk = e.get('uk', '')
        if not uk:
            continue
        s = source.get(key)
        if s is None:
            add('unknown', key, 'not in the game any more')
            continue
        en = s['en']
        if e.get('src') and e['src'] != d4x.src_hash(en):
            add('stale', key, 'English changed since translation: ' + en[:80])

        if not s.get('base'):
            pe, le, te = d4x.markup(en)
            pu, lu, tu = d4x.markup(uk)
            if pe != pu:
                add('placeholder', key, '%s -> %s' % (diff(pe, pu)))
            if le != lu:
                add('links', key, '%s -> %s' % (diff(le, lu)))
            if te != tu:
                add('tags', key, '%s -> %s' % (diff(te, tu)))
            if en.count('\n') != uk.count('\n'):
                add('newline', key, '%d line breaks in English, %d here' % (en.count('\n'), uk.count('\n')))
            if (en[:1].isspace(), en[-1:].isspace()) != (uk[:1].isspace(), uk[-1:].isspace()):
                add('space', key, 'edge whitespace differs from the English')
            if uk == en and any(c.isalpha() for c in en):
                add('same', key, 'identical to the English')
            plain_en = d4x.LINK_RE.sub(' ', en)
            plain_uk = d4x.LINK_RE.sub(' ', uk).replace("'", '')
            hits = [(m.span(), stems, label) for en_re, stems, label in terms for m in en_re.finditer(plain_en)]
            spans = [h[0] for h in hits]
            missed = []
            for (a, b), stems, label in hits:
                # a term inside a longer one ("Shield" in "Shield Wall") is that one's business
                if any(c <= a and b <= d and (c, d) != (a, b) for c, d in spans):
                    continue
                if label not in missed and not all(st.search(plain_uk) for st in stems):
                    missed.append(label)
            for label in missed:
                add('term', key, label)
        if not d4x.tags_balanced(uk):
            add('xml', key, 'unbalanced tags')
        # | splits lists (names, tutorial goals, option levels): counts must
        # match. In a faction longName it only glues "House|Atreides" with a
        # no-break space, so the translation may drop it.
        if key.endswith('longName'):
            if uk.count('|') > 1:
                add('pipe', key, 'a longName takes at most one "|"')
        elif en.count('|') != uk.count('|') and not s.get('base'):
            add('pipe', key, '%d "|" in English, %d here' % (en.count('|'), uk.count('|')))

        for m in d4x.LINK_RE.finditer(uk):
            if m.group(2) not in d4x.LINK_SUFFIXES:
                add('suffix', key, '[%s]%s — unknown suffix "%s"' % (m.group(1), m.group(2), m.group(2)))
        chars = {c for c in d4x.TAG_RE.sub('', uk) if c not in charset}
        bad = sorted(c for c in chars if c not in d4x.FALLBACK)
        if bad:
            add('glyph', key, 'no glyph for ' + ' '.join('%r(U+%04X)' % (c, ord(c)) for c in bad))
        stand_in = sorted(c for c in chars if c in d4x.FALLBACK and c != '\u00a0')
        if stand_in:
            add('fallback', key, ' '.join('%r draws as %r' % (c, d4x.FALLBACK[c]) for c in stand_in))

    # a declined name needs its forms too
    for key, s in source.items():
        base = s.get('base')
        if base and entries.get(base, {}).get('uk') and not entries.get(key, {}).get('uk'):
            add('decl', key, 'name is translated, this form is not')
    return issues


def diff(a, b):
    ca, cb = collections.Counter(a), collections.Counter(b)
    return (sorted((ca - cb).elements()) or '-', sorted((cb - ca).elements()) or '-')


def neutral(en):
    """nothing to translate: only placeholders, links, tags, digits and
    punctuation ("[Hegemony]", "::name::", "???") — they already show the
    translated names they point to"""
    rest = d4x.TAG_RE.sub('', d4x.LINK_RE.sub('', d4x.PLACEHOLDER_RE.sub('', en)))
    rest = re.sub(r'%[A-Za-z]', '', rest)                     # strftime codes
    return not any(c.isalpha() for c in rest) or rest.strip() in ('me',)


def coverage(entries, source):
    total, done = collections.Counter(), collections.Counter()
    for key, s in source.items():
        has = bool(entries.get(key, {}).get('uk'))
        if not has and not s.get('base') and neutral(s['en']):
            continue
        area = 'texts' if key.startswith('texts:') else key[7:].split('/')[0]
        total[area] += 1
        if has:
            done[area] += 1
    return total, done


def main():
    d4x.configure_stdout()
    args = sys.argv[1:]
    verbose = '-v' in args
    only = args[args.index('--only') + 1] if '--only' in args else None
    source = d4x.load_source()
    with open(os.path.join(d4x.LOCAL, 'source', 'game.json'), encoding='utf-8') as f:
        charset = set(json.load(f)['charset'])

    if '--shipped' in args:
        game = d4x.Game()
        shipped = dict(d4x.parse_texts(game.lang_file('texts')), **d4x.parse_export(game.lang_file('export')))
        entries = {k: {'uk': v, 'src': d4x.src_hash(source[k]['en'])} for k, v in shipped.items() if v and k in source}
        label = 'shipped %s' % d4x.LANG
    else:
        entries = d4x.load_translation()
        label = 'translation/'

    issues = check(entries, source, charset)
    by_kind = collections.Counter(k for k, *_ in issues)
    total, done = coverage(entries, source)

    print('%s: %d of %d strings (%.1f%%)' % (label, sum(done.values()), sum(total.values()),
                                              100.0 * sum(done.values()) / max(1, sum(total.values()))))
    if verbose:
        for area in sorted(total, key=lambda a: -total[a]):
            print('  %-22s %5d / %5d' % (area, done[area], total[area]))
    print()
    for kind in ERRORS + WARNINGS:
        if by_kind[kind]:
            print('%-8s %-7s %d' % ('ERROR' if kind in ERRORS else 'warning', kind, by_kind[kind]))
    shown = [i for i in issues if (only and i[0] == only) or (not only and (i[0] in ERRORS or verbose))]
    if shown:
        print()
        for kind, key, msg in shown:
            print('%-7s %s\n        %s' % (kind, key, msg))
    sys.exit(1 if any(k in ERRORS for k in by_kind) and '--shipped' not in args else 0)


if __name__ == '__main__':
    main()
