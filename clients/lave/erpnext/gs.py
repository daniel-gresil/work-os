"""Read-only Google Sheets helper. usage: gs.py tabs <id> | gs.py get <id> '<Tab>!A1:Z5'"""
import json, os, sys, urllib.parse, urllib.request
_tok = None
def token():
    global _tok
    if _tok is None:
        body = urllib.parse.urlencode({'client_id': os.environ['SHEETS_CLIENT_ID'], 'client_secret': os.environ['SHEETS_CLIENT_SECRET'],
            'refresh_token': os.environ['SHEETS_REFRESH_TOKEN'], 'grant_type': 'refresh_token'}).encode()
        _tok = json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=body)))['access_token']
    return _tok
def api(sheet, path):
    req = urllib.request.Request(f'https://sheets.googleapis.com/v4/spreadsheets/{sheet}/{path}')
    req.add_header('Authorization', 'Bearer ' + token())
    return json.load(urllib.request.urlopen(req))
def tabs(sheet):
    meta = api(sheet, '?fields=properties.title,sheets.properties')
    print(meta['properties']['title'])
    for s in meta['sheets']:
        p = s['properties']; g = p.get('gridProperties', {})
        print(f"  {p['title']!r}: {g.get('rowCount')}x{g.get('columnCount')} hidden={p.get('hidden', False)}")
def get(sheet, rng):
    return api(sheet, 'values/' + urllib.parse.quote(rng, safe='') + '?valueRenderOption=UNFORMATTED_VALUE').get('values', [])
if __name__ == '__main__':
    cmd, sheet = sys.argv[1], sys.argv[2]
    if cmd == 'tabs': tabs(sheet)
    else:
        for r in get(sheet, sys.argv[3]): print(json.dumps(r, default=str))
