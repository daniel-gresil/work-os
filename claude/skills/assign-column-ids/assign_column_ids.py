#!/usr/bin/env python3
"""Assign Lave column IDs: claim free rows in the central column registry and
stamp the IDs into row 1 of a target sheet tab. Never inserts columns.

Registry ("9085"): Google Sheet 1KM8vJCuAIGoWP5nmIBnnXZPcsz4Qzn459aIyk1V4eCY,
tab "1) Column Headers", header row 3, data from row 6. A=Header Number (ID),
B-E=Column Header 1-4, F=Department, H=Assigned Date, P=Hyperlink, W=Notes.
A row whose B is blank is free. Rows 7272-7500 are reserved for Vintage
Industries (marker in C, no department) -- use --vintage for VI files.

Auth: OAuth client + Sheets refresh token from 1Password (op://infra, item
ddyor7povtvi522bbgvgwottie), cached by lave-file-access-audit/.cf_creds.json.

Usage:
  assign_column_ids.py find --dept Finance            # free IDs in that dept
  assign_column_ids.py find --vintage -n 8            # free IDs in the VI block
  assign_column_ids.py claim --id 7272 --h1 TxnDate --h3 "Invoice VI" \
      --dept Finance --file 7002 --notes "Invoice date sent to QBO" [--url URL]
  assign_column_ids.py stamp --sheet <id-or-url> --tab Invoices C=7272 F=7273
"""
import argparse, json, re, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

REG = '1KM8vJCuAIGoWP5nmIBnnXZPcsz4Qzn459aIyk1V4eCY'
TAB = '1) Column Headers'
FIRST_DATA_ROW = 6
OP_ITEM = 'ddyor7povtvi522bbgvgwottie'
CRED_CACHE = Path.home() / 'Developer/lave-file-access-audit/.cf_creds.json'
FILE_URLS = {
    '9025': 'https://docs.google.com/spreadsheets/d/1VnP52UxzIdfnZhoZs2U2otOz7XGRhKajmshfNOb345k/edit',
    '7002': 'https://docs.google.com/spreadsheets/d/1yUgXI9RMHUhd6dVRQsBMWmOE0nGkI7t16n7dYsff8sw/edit',
}
_token = None


def op_read(field):
    if CRED_CACHE.exists():
        val = json.loads(CRED_CACHE.read_text()).get(field)
        if val:
            return val
    return subprocess.run(['op', 'read', f'op://infra/{OP_ITEM}/{field}'],
                          capture_output=True, text=True, check=True).stdout.strip()


def token():
    global _token
    if _token is None:
        body = urllib.parse.urlencode({
            'client_id': op_read('client_id'), 'client_secret': op_read('client_secret'),
            'refresh_token': op_read('sheets_refresh_token'), 'grant_type': 'refresh_token'}).encode()
        _token = json.load(urllib.request.urlopen(
            urllib.request.Request('https://oauth2.googleapis.com/token', data=body)))['access_token']
    return _token


def api(sheet, path, body=None, method=None):
    for attempt in range(4):  # Sheets returns the odd 503; retry briefly
        req = urllib.request.Request(
            f'https://sheets.googleapis.com/v4/spreadsheets/{sheet}/{path}',
            data=json.dumps(body).encode() if body else None, method=method)
        req.add_header('Authorization', 'Bearer ' + token())
        if body:
            req.add_header('Content-Type', 'application/json')
        try:
            return json.load(urllib.request.urlopen(req))
        except urllib.error.HTTPError as e:
            if e.code != 503 or attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def q(rng):
    return 'values/' + urllib.parse.quote(rng)


def registry():
    """{id: (rownum, row)} for every numeric-ID row."""
    rows = api(REG, q(f"'{TAB}'!A1:W")).get('values', [])
    return {r[0]: (i, r) for i, r in enumerate(rows, 1)
            if i >= FIRST_DATA_ROW and r and r[0].isdigit()}


def cell(row, i):
    return row[i].strip() if len(row) > i else ''


def is_free(row):
    return cell(row, 1) == ''


def cmd_find(a):
    free = []
    for id_, (rn, r) in registry().items():
        if not is_free(r):
            continue
        if a.vintage and 'vintage' not in cell(r, 2).lower():
            continue
        if a.dept and cell(r, 5).lower() != a.dept.lower():
            continue
        free.append((int(id_), rn))
    if not free:
        sys.exit('No free IDs match.')
    free.sort()
    print(f'{len(free)} free IDs: ' + ', '.join(str(i) for i, _ in free[:a.n])
          + (' ...' if len(free) > a.n else ''))
    print('NEXT_IDS=' + ','.join(str(i) for i, _ in free[:a.n]))


def cmd_claim(a):
    reg = registry()
    if a.id not in reg:
        sys.exit(f'ID {a.id} not in registry column A.')
    rn, r = reg[a.id]
    if not is_free(r):
        sys.exit(f'ID {a.id} (row {rn}) is taken: {r[1]!r}. Nothing changed.')
    url = a.url or FILE_URLS.get(a.file)
    if not url:
        sys.exit(f'No known URL for file {a.file!r}; pass --url. Nothing changed.')
    put = lambda col, v: {'range': f"'{TAB}'!{col}{rn}", 'values': [[v]]}
    data = [put('B', a.h1), put('F', a.dept), put('H', time.strftime('%-m/%-d/%Y')),
            put('P', f'=HYPERLINK("{url}","{a.file}")'), put('W', a.notes)]
    for col, v in (('C', a.h2), ('D', a.h3), ('E', a.h4)):
        if v:  # C keeps its reservation marker unless a header is given
            data.append(put(col, v))
    api(REG, 'values:batchUpdate', {'valueInputOption': 'USER_ENTERED', 'data': data}, 'POST')
    print(f'Claimed ID {a.id} (row {rn}): {a.h1!r} dept={a.dept} file={a.file} notes={a.notes!r}')


def cmd_stamp(a):
    m = re.search(r'/d/([\w-]+)', a.sheet)
    sheet = m.group(1) if m else a.sheet
    pairs = [p.split('=', 1) for p in a.pairs]
    reg = registry()
    for col, id_ in pairs:
        if id_ not in reg or is_free(reg[id_][1]):
            sys.exit(f'ID {id_} is not a claimed registry ID. Nothing changed.')
    top = api(sheet, q(f"'{a.tab}'!1:{a.header_row}")).get('values', [])
    row1 = top[0] if top else []
    hdr = top[a.header_row - 1] if len(top) >= a.header_row else []
    for col, id_ in pairs:
        i = 0
        for ch in col.upper():  # A=0 ... Z=25, AA=26, DY=128
            i = i * 26 + (ord(ch) - 64)
        i -= 1
        if cell(row1, i) and not a.force:
            sys.exit(f'{a.tab}!{col}1 already holds {row1[i]!r}; pass --force to overwrite. Nothing changed.')
        print(f'{col}1 <- {id_}   ({cell(hdr, i) or "<no header>"} / registry: {reg[id_][1][1]})')
    api(sheet, 'values:batchUpdate', {'valueInputOption': 'RAW', 'data': [
        {'range': f"'{a.tab}'!{col.upper()}1", 'values': [[int(id_)]]} for col, id_ in pairs]}, 'POST')
    print('Row 1 now:', api(sheet, q(f"'{a.tab}'!1:1")).get('values', [[]])[0])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    f = sub.add_parser('find')
    f.add_argument('--dept'); f.add_argument('--vintage', action='store_true')
    f.add_argument('-n', type=int, default=10)
    c = sub.add_parser('claim')
    for flag in ('--id', '--h1', '--dept', '--file', '--notes'):
        c.add_argument(flag, required=True)
    for flag in ('--h2', '--h3', '--h4', '--url'):
        c.add_argument(flag)
    s = sub.add_parser('stamp')
    s.add_argument('--sheet', required=True); s.add_argument('--tab', required=True)
    s.add_argument('--header-row', type=int, default=2)
    s.add_argument('--force', action='store_true')
    s.add_argument('pairs', nargs='+', metavar='COL=ID')
    a = p.parse_args()
    {'find': cmd_find, 'claim': cmd_claim, 'stamp': cmd_stamp}[a.cmd](a)
