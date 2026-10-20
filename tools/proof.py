# -*- coding: utf-8 -*-
"""Manual proofreading: one CSV the proofreader edits, kept in step with translation/.

translation/proofreading.csv (UTF-8 with BOM, ";"-separated, so Excel opens it
in columns) has one row per translated line; a name and all its cases share
one row:

  ключ       the line's key (leave it alone)
  розділ     where the line shows up, to filter by
  EN         the game's English
  UA         the translation: edit it in place
  відмінки   names only, "Н; Р; Д; З; О; М | Н; Р; Д; З; О; М": edit in place
  вичитано   ✓ (or +) once the row is checked; ✗ or anything else flags it
             for a fix: kept as written, and the row stays out of releases
  дата       filled in by the tool: the day the row was marked
  коментар   free notes, kept as they are
  відбиток   filled in by the tool: what the row said when it was written out

Line breaks inside a text are written as \\n, as in the translation files.

Running the tool syncs both ways:
  1. reads the CSV: an edited UA / відмінки cell goes into translation/, and
     a mark records the row as proofread;
  2. writes the CSV again from translation/: new lines are added, and a mark
     is dropped when the translation changed after it was set.

When a row was edited in the CSV and changed in translation/ as well, the
CSV wins and the other version is printed, so nothing is lost.

tools/build.py --proofread ships the marked rows only.

--web syncs, then opens a page in the browser that shows one row at a time:
→ marks it ✓, ← marks it ✗ (a comment is required), ↓ writes a comment and
waits for ← or →, ↑ goes back a row. Under the UA it shows how the line reads
in the game: links replaced by the names in the right case, as far as the
game data tells. Every decision is written to the CSV at once, so the page
can be closed at any moment. Close the CSV in Excel first:
Excel locks the file.

Usage:
    python tools/proof.py            sync
    python tools/proof.py --status   progress by section and by day
    python tools/proof.py --web      sync, then proofread in the browser
"""
import collections, csv, datetime, io, json, os, re, sys
import d4x, merge

PATH = os.path.join(d4x.TRANSLATION, 'proofreading.csv')
HEAD = ['ключ', 'розділ', 'EN', 'UA', 'відмінки', 'вичитано', 'дата', 'коментар', 'відбиток']
OK_MARKS = {'✓', '✔', '+', 'v', 'V', '1'}       # what counts as "checked"
ok = lambda mark: mark.strip() in OK_MARKS
# what Excel leaves in a cell it took for a formula
EXCEL_ERROR = re.compile(r"^#(NAME\?|ИМЯ\?|ІМ'Я\?|VALUE!|ЗНАЧ!|REF!|ССЫЛКА!|ПОСИЛАННЯ!|N/A|Н/Д)")


def section(key):
    if key.startswith('texts:'):
        return 'інтерфейс/' + key[len('texts:'):].split('.')[0]
    return key[len('export:'):].split('/')[0]


def lines(source, entries):
    """translated lines in the game's order -> {key: (ua, forms)}"""
    declined = {s['base'] for s in source.values() if s.get('base')}
    out = {}
    for key, s in source.items():
        if s.get('base') or ('/texts.plural.' in key and key.replace('/texts.plural.', '/texts.') in declined):
            continue
        ua = entries.get(key, {}).get('uk', '')
        forms = merge.forms_of(key, entries) if key in declined else ''
        if ua or forms:
            out[key] = (ua, forms)
    return out


def fingerprint(ua, forms):
    return d4x.src_hash(ua + '\n' + forms)


def read_sheet(path=PATH):
    """-> {key: row} with UA / відмінки / EN unescaped"""
    if not os.path.isfile(path):
        return {}
    raw = open(path, 'rb').read()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp1251')
        print('warning: %s is not UTF-8 (Excel saved it as plain "CSV"?); read as Windows-1251.\n'
              '         Save it as "CSV UTF-8" next time.' % os.path.basename(path))
    first = text.split('\n', 1)[0]
    delim = ';' if first.count(';') >= first.count(',') else ','
    reader = csv.DictReader(io.StringIO(text, newline=''), delimiter=delim)
    missing = [h for h in HEAD if h not in (reader.fieldnames or [])]
    if missing:
        sys.exit('%s: columns missing: %s' % (path, ', '.join(missing)))
    out = {}
    for r in reader:
        key = (r['ключ'] or '').strip()
        if key:
            r = {h: (r.get(h) or '') for h in HEAD}
            for h in ('EN', 'UA', 'відмінки'):
                r[h] = d4x.unesc(r[h])
            out[key] = r
    return out


def write_sheet(rows, path=PATH):
    buf = io.StringIO(newline='')
    w = csv.writer(buf, delimiter=';', lineterminator='\r\n')
    w.writerow(HEAD)
    for r in rows:
        w.writerow([d4x.esc(r[h]) if h in ('EN', 'UA', 'відмінки') else r[h] for h in HEAD])
    tmp = path + '.tmp'                     # a failed write must not leave half a sheet
    try:
        with open(tmp, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(buf.getvalue())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def sync():
    source, entries = d4x.load_source(), d4x.load_translation()
    before = lines(source, entries)
    sheet = read_sheet()
    today = datetime.date.today().isoformat()
    edits, marks, notes, flags = {}, {}, {}, {}
    edited, conflicts, dropped, bad = [], [], [], []

    for key, r in sheet.items():
        if key not in source or key not in before:
            bad.append((key, 'not a translated line any more'))
            continue
        notes[key] = r['коментар']
        ua, forms = r['UA'], r['відмінки']
        if EXCEL_ERROR.match(ua) or EXCEL_ERROR.match(forms):
            bad.append((key, 'Excel turned the cell into a formula error: %s' % (ua or forms)))
            continue
        cur_ua, cur_forms = before[key]
        user_changed = fingerprint(ua, forms) != r['відбиток']
        if user_changed and (ua, forms) != (cur_ua, cur_forms):
            if fingerprint(cur_ua, cur_forms) != r['відбиток']:
                conflicts.append((key, cur_ua, cur_forms))
            try:
                new = merge.expand(key, forms, source) if forms and forms != cur_forms else {}
            except ValueError as e:
                bad.append((key, str(e)))
                continue
            if ua and ua != cur_ua:
                new[key] = merge.edges(source[key]['en'], ua)
            elif key in new:
                new[key] = cur_ua                   # forms edited, the name itself was not
            edits.update(new)
            edited.append(key)
        if r['вичитано'].strip() and not ok(r['вичитано']):
            flags[key] = r['вичитано'].strip()          # a request, not a check
        elif r['вичитано'].strip():
            if user_changed or fingerprint(cur_ua, cur_forms) == r['відбиток']:
                marks[key] = r['дата'] if (r['дата'] and not user_changed) else today
            else:
                dropped.append(key)                 # translation changed under the mark

    if edits:
        for k, v in edits.items():
            entries[k] = {'uk': v, 'src': d4x.src_hash(source[k]['en'])}
        d4x.save_translation(entries, source)
    after = lines(source, entries)

    rows = []
    for key, (ua, forms) in after.items():
        rows.append({'ключ': key, 'розділ': section(key), 'EN': source[key]['en'], 'UA': ua, 'відмінки': forms,
                     'вичитано': '✓' if key in marks else flags.get(key, ''), 'дата': marks.get(key, ''),
                     'коментар': notes.get(key, ''), 'відбиток': fingerprint(ua, forms)})
    write_sheet(rows)

    print('read     %d rows: %d edited, %d checked, %d flagged for a fix' % (len(sheet), len(edited), len(marks), len(flags)))
    print('written  %s  (%d rows)' % (os.path.relpath(PATH, d4x.ROOT), len(rows)))
    for key, ua, forms in conflicts:
        print('CONFLICT %s — your CSV edit was kept; translation/ had:\n         %s' % (key, ua + (' || ' + forms if forms else '')))
    for key in dropped:
        print('unmarked %s — the translation changed after it was checked' % key)
    for key, why in bad:
        print('SKIPPED  %s — %s' % (key, why))
    return rows


def proofread_keys(source, entries):
    """-> the keys a --proofread build may ship. Refuses an unsynced CSV."""
    sheet = read_sheet()
    current = lines(source, entries)
    pending = [k for k, r in sheet.items() if fingerprint(r['UA'], r['відмінки']) != r['відбиток']]
    if pending:
        sys.exit('%d rows of proofreading.csv were edited but not synced (e.g. %s) — run tools/proof.py first'
                 % (len(pending), pending[0]))
    declined = {s['base'] for s in source.values() if s.get('base')}
    keys = set()
    for key, r in sheet.items():
        if ok(r['вичитано']) and key in current and fingerprint(*current[key]) == r['відбиток']:
            keys |= merge.name_group(key, source) if key in declined else {key}
    return keys


def dangling(keys, source):
    """shipped lines linking to a declined name that is not shipped (it would
    show in English, undeclined) -> {link target: number of lines}"""
    names = collections.defaultdict(set)
    for s in source.values():
        if s.get('base'):
            names[s['base'].split('/')[1].lower()].add(s['base'])
    out = collections.Counter()
    for key in keys:
        if source[key].get('base'):
            continue
        for m in d4x.LINK_RE.finditer(source[key]['en']):
            t = d4x.link_target(m.group(1))
            if t in names and not names[t] & keys:
                out[t] += 1
    return out


def status():
    source, entries = d4x.load_source(), d4x.load_translation()
    sheet = read_sheet()
    current = lines(source, entries)
    keys = proofread_keys(source, entries)
    total = collections.Counter(section(k) for k in current)
    done = collections.Counter(section(k) for k, r in sheet.items()
                               if ok(r['вичитано']) and k in current and fingerprint(*current[k]) == r['відбиток'])
    days = collections.Counter(r['дата'] for r in sheet.values() if ok(r['вичитано']) and r['дата'])
    flagged = [k for k, r in sheet.items() if r['вичитано'].strip() and not ok(r['вичитано'])]
    import check
    cov_total, _ = check.coverage(entries, source)
    print('proofread %d of %d rows; ships %d of %d strings (%.1f%% of the game)'
          % (sum(done.values()), sum(total.values()), len(keys), sum(cov_total.values()),
             100.0 * len(keys) / max(1, sum(cov_total.values()))))
    for s in sorted(total, key=lambda s: -total[s]):
        print('  %-28s %5d / %5d' % (s, done[s], total[s]))
    if days:
        print('by day:')
        for d in sorted(days):
            print('  %s  %d' % (d, days[d]))
    if flagged:
        print('flagged for a fix (%d):' % len(flagged))
        for k in flagged:
            print('  %s %s  %s' % (sheet[k]['вичитано'].strip(), k, sheet[k]['коментар']))
    gaps = dangling(keys, source)
    if gaps:
        print('proofread lines that link to names not proofread yet (they would show in English):')
        for t, n in gaps.most_common(15):
            print('  [%s] in %d lines' % (t, n))


def set_mark(key, mark, note):
    """one decision from the page -> the CSV. The sheet is read again first, so
    nothing written to it in the meantime is lost."""
    sheet = read_sheet()
    if key not in sheet:
        raise KeyError(key)
    r = sheet[key]
    if not (ok(mark) and ok(r['вичитано'])):     # re-accepting keeps the first date
        r['дата'] = datetime.date.today().isoformat() if ok(mark) else ''
    r['вичитано'], r['коментар'] = mark, note
    write_sheet(sheet.values())


NAME_KEY = re.compile(r'^export:[^/]+/([^/]+)/(?:texts\.)?(?:([a-zA-Z]+)\.)?(name|shortName|longName|adjective)$')


def link_names(source, entries):
    """-> {link target: {field: {case: text}}}: what a link turns into in the
    game, for the page's preview (the Ukrainian where there is one). Only the
    targets some line links to are kept."""
    targets = {d4x.link_target(m.group(1)) for s in source.values() for m in d4x.LINK_RE.finditer(s['en'])}
    found = collections.defaultdict(dict)
    for key, s in source.items():
        m = NAME_KEY.match(key)
        if not m or m.group(1).lower() not in targets:
            continue
        fields = found[m.group(1).lower()].setdefault(key.split('/', 1)[0], {})
        fields.setdefault(m.group(3).lower(), {})[m.group(2) or ''] = entries.get(key, {}).get('uk') or s['en']
    # an id used on several sheets: the one with case forms is what links mean
    return {t: max(sheets.values(), key=lambda f: sum(map(len, f.values()))) for t, sheets in found.items()}


def web(port=8723):
    import http.server, webbrowser
    try:
        sync()
    except PermissionError:
        sys.exit('proofreading.csv is open in another program (Excel?): close it and run again')
    page = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'proof.html')
    names = link_names(d4x.load_source(), d4x.load_translation())

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, body, ctype='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/':
                self.reply(200, open(page, 'rb').read(), 'text/html; charset=utf-8')
            elif self.path == '/rows':
                self.reply(200, [{'key': k, 'section': r['розділ'], 'en': r['EN'], 'ua': r['UA'],
                                  'forms': r['відмінки'], 'mark': r['вичитано'], 'note': r['коментар']}
                                 for k, r in read_sheet().items()])
            elif self.path == '/names':
                self.reply(200, names)
            else:
                self.reply(404, {'error': 'not found'})

        def do_POST(self):
            if self.path != '/mark':
                return self.reply(404, {'error': 'not found'})
            try:
                req = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                set_mark(req['key'], req['mark'], req['note'])
            except PermissionError:
                return self.reply(423, {'error': 'proofreading.csv зайнятий іншою програмою (Excel?). Закрийте його.'})
            except KeyError as e:
                return self.reply(409, {'error': 'рядка %s немає в CSV' % e})
            self.reply(200, {'ok': True})

    try:
        server = http.server.HTTPServer(('127.0.0.1', port), Handler)
    except OSError:
        server = http.server.HTTPServer(('127.0.0.1', 0), Handler)      # the port is taken
    url = 'http://127.0.0.1:%d/' % server.server_address[1]
    print('proofreading at %s  (Ctrl+C stops it)' % url)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    d4x.configure_stdout()
    if '--status' in sys.argv:
        status()
    elif '--web' in sys.argv:
        web()
    else:
        sync()


if __name__ == '__main__':
    main()
