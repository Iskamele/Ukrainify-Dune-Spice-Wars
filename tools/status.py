# -*- coding: utf-8 -*-
"""Progress figures for the README: translated, and edited by hand.

Translated counts every string that has a Ukrainian line (check.py's
figure). Edited counts the strings behind the rows checked in
translation/proofreading.csv (tools/proof.py): the ones a release ships.

--readme rewrites, in README.md, the two badges after the game badge and the
two lines this tool owns: the one starting "Перекладено **" and the one
starting "**Status:**". Everything else in the README is left as written.
It also rewrites ukrainify.json, which the GitHub profile (Iskamele/iskamele)
reads to show this translation's progress.

Usage:
    python tools/status.py            print the figures
    python tools/status.py --readme   and update README.md
"""
import json, os, re, sys
import d4x, check, proof

README = os.path.join(d4x.ROOT, 'README.md')
MANIFEST = os.path.join(d4x.ROOT, 'ukrainify.json')


def figures():
    source, entries = d4x.load_source(), d4x.load_translation()
    total, done = check.coverage(entries, source)
    shipped = proof.proofread_keys(source, entries)
    return sum(done.values()), len(shipped), sum(total.values())


def pct(n, total):
    p = 100.0 * n / max(1, total)
    return '0%' if n == 0 else '<1%' if p < 1 else '%d%%' % p


def badge(alt, label, n, total, color):
    msg = pct(n, total).replace('%', '%25').replace('<', '%3C')
    return '![%s](https://img.shields.io/badge/%s-%s-%s)' % (alt, label, msg, color)


def update_readme(tr, pr, total):
    text = open(README, encoding='utf-8').read()
    ua = lambda n: '{:,}'.format(n).replace(',', ' ')
    badges = (badge('переклад', 'переклад', tr, total, 'orange') + ' ' +
              badge('редактура', 'редактура', pr, total, 'blue'))
    rules = [
        (r'!\[(?:статус|переклад)\]\(https://img\.shields\.io/badge/переклад-[^)]*\)'
         r'(?: !\[(?:вичитка|редактура)\]\(https://img\.shields\.io/badge/(?:вичитано_вручну|редактура)-[^)]*\))?', badges),
        (r'(?m)^Перекладено \*\*.*$',
         'Перекладено **%s з %s рядків (%s)**, відредаговано вручну **%s (%s)**. '
         'До збірки потрапляють лише відредаговані рядки, решту гра показує англійською.'
         % (ua(tr), ua(total), pct(tr, total), ua(pr), pct(pr, total))),
        (r'(?m)^\*\*Status:\*\* .*$',
         '**Status:** {:,} of {:,} strings translated ({}), {:,} edited by hand ({}). '
         'Releases ship edited lines only; everything else shows in English.'
         .format(tr, total, pct(tr, total), pr, pct(pr, total))),
    ]
    for pattern, new in rules:
        text, n = re.subn(pattern, lambda m: new, text, count=1)
        if not n:
            sys.exit('README.md: nothing matches %s' % pattern)
    with open(README, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)


def write_manifest(tr, pr, total):
    manifest = {'game': 'Dune: Spice Wars', 'steam_appid': 1605220,
                'lines': {'done': tr, 'total': total}, 'edited': pr}
    with open(MANIFEST, 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


def main():
    d4x.configure_stdout()
    tr, pr, total = figures()
    print('translated %6d of %d  (%s)' % (tr, total, pct(tr, total)))
    print('edited     %6d of %d  (%s)' % (pr, total, pct(pr, total)))
    if '--readme' in sys.argv:
        update_readme(tr, pr, total)
        print('updated  README.md')
        write_manifest(tr, pr, total)
        print('updated  ukrainify.json')


if __name__ == '__main__':
    main()
