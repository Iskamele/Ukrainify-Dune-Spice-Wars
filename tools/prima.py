# -*- coding: utf-8 -*-
"""A Prima export as a batch for merge.py.

Prima keeps the delimiter of the file it imported, so the export is a CSV
with "," or ";" and the imported file's columns: key, the translation
("translation", "uk" or "UA") and, for names, the declension forms ("forms"
or "Відмінки"). Columns are found by header name, case-insensitively.

For each row with a translation: key<TAB>translation (line breaks as \\n).
For each row with forms: key=forms<TAB>forms, also when the translation is
empty (merge.py takes a forms line alone). Rows with neither are skipped. Prima prefixes a cell that starts with = + - @ with
a single quote, so a spreadsheet does not read it as a formula; one such
quote is taken off.

Usage:
    python tools/prima.py <prima-export.csv> > batch.tsv
    python tools/merge.py batch.tsv

>>> import io
>>> data = ('key,context,source,translation,forms\\n'
...         'texts:menu.quit,UI,Quit,Вийти,\\n'
...         'export:unit/A_Trooper/texts.name,unit,Trooper,Піхотинець,'
...         'піхотинець; піхотинця; піхотинцеві; піхотинця; піхотинцем; піхотинцеві'
...         ' | піхотинці; піхотинців; піхотинцям; піхотинців; піхотинцями; піхотинцях\\n'
...         'texts:menu.empty,UI,Empty,,\\n'
...         'export:unit/B_Scout/texts.name,unit,Scout,,'
...         'розвідник; розвідника; розвідникові; розвідника; розвідником; розвідникові'
...         ' | розвідники; розвідників; розвідникам; розвідників; розвідниками; розвідниках\\n')
>>> show = lambda data: print(''.join(portion(io.StringIO(data))).replace('\\t', ' <TAB> '), end='')
>>> show(data)
texts:menu.quit <TAB> Вийти
export:unit/A_Trooper/texts.name <TAB> Піхотинець
export:unit/A_Trooper/texts.name=forms <TAB> піхотинець; піхотинця; піхотинцеві; піхотинця; піхотинцем; піхотинцеві | піхотинці; піхотинців; піхотинцям; піхотинців; піхотинцями; піхотинцях
export:unit/B_Scout/texts.name=forms <TAB> розвідник; розвідника; розвідникові; розвідника; розвідником; розвідникові | розвідники; розвідників; розвідникам; розвідників; розвідниками; розвідниках
>>> data = ("key;uk;Відмінки\\r\\n"
...         "texts:a;'-- ніщо;\\r\\n"
...         "texts:b;\\"рядок\\nдругий\\";\\r\\n")
>>> show(data)
texts:a <TAB> -- ніщо
texts:b <TAB> рядок\\nдругий
"""
import csv, sys
import d4x

TRANSLATION = ('translation', 'uk', 'ua')
FORMS = ('forms', 'відмінки')
FORMULA = '=+-@'


def unprotect(cell):
    """take off the one quote Prima put before a cell starting with = + - @"""
    return cell[1:] if cell[:1] == "'" and cell[1:2] and cell[1] in FORMULA else cell


def column(header, names):
    for i, h in enumerate(header):
        if h.strip().lower() in names:
            return i
    return None


def portion(f):
    """rows of an open CSV file -> the lines of a batch"""
    head = f.readline()
    f.seek(0)
    delimiter = ';' if head.count(';') > head.count(',') else ','
    rows = csv.reader(f, delimiter=delimiter)
    header = next(rows, [])
    key, uk, forms = column(header, ('key',)), column(header, TRANSLATION), column(header, FORMS)
    if key is None or uk is None:
        raise SystemExit('need a "key" column and a "translation" (or "uk", "UA") one; got %s' % header)
    for n, row in enumerate(rows, 2):
        cell = lambda i: row[i] if i is not None and i < len(row) else ''
        k = cell(key).strip()
        text, spec = unprotect(cell(uk)), unprotect(cell(forms)).strip()
        if not k:
            continue
        if text.strip():
            yield '%s\t%s\n' % (k, d4x.esc(text))
        if spec:
            yield '%s=forms\t%s\n' % (k, d4x.esc(spec))


def main():
    d4x.configure_stdout()
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding='utf-8-sig', newline='') as f:
        for line in portion(f):
            sys.stdout.write(line)


if __name__ == '__main__':
    main()
