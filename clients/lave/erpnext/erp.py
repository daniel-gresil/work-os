"""Thin ERPNext REST client. Cookie login with ERPNEXT_PROD_ADMIN_USER/PASS from the work-os secrets cache.
usage: python3 erp.py get 'Item' --filters '{"item_group":"Mill Blank"}'   (quick reads from the shell)
"""
import http.cookiejar, json, os, sys, urllib.parse, urllib.request

BASE = os.environ.get('ERPNEXT_BASE', 'https://erpnext.laveapparel.com')
_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))
_logged_in = False


def _call(method, path, body=None, params=None):
    global _logged_in
    if not _logged_in:
        _logged_in = True
        _call('POST', '/api/method/login', {'usr': os.environ['ERPNEXT_PROD_ADMIN_USER'], 'pwd': os.environ['ERPNEXT_PROD_ADMIN_PASS']})
    url = BASE + path + ('?' + urllib.parse.urlencode(params) if params else '')
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    try:
        with _opener.open(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{method} {path} -> {e.code}: {e.read().decode()[:600]}') from None


def get_list(doctype, fields=('name',), filters=None, limit=0):
    p = {'fields': json.dumps(list(fields)), 'limit_page_length': limit}
    if filters: p['filters'] = json.dumps(filters)
    return _call('GET', f'/api/resource/{urllib.parse.quote(doctype)}', params=p)['data']


def get_doc(doctype, name):
    return _call('GET', f'/api/resource/{urllib.parse.quote(doctype)}/{urllib.parse.quote(name)}')['data']


def exists(doctype, name):
    try:
        get_doc(doctype, name); return True
    except RuntimeError as e:
        if '-> 404' in str(e): return False
        raise


def insert(doc):
    return _call('POST', f'/api/resource/{urllib.parse.quote(doc["doctype"])}', doc)['data']


def update(doctype, name, fields):
    return _call('PUT', f'/api/resource/{urllib.parse.quote(doctype)}/{urllib.parse.quote(name)}', fields)['data']


def method(name, **kwargs):
    return _call('POST', f'/api/method/{name}', kwargs)['message']


if __name__ == '__main__':
    if sys.argv[1] == 'get':
        f = json.loads(sys.argv[sys.argv.index('--filters') + 1]) if '--filters' in sys.argv else None
        for r in get_list(sys.argv[2], fields=('*',), filters=f, limit=20): print(json.dumps(r, default=str)[:300])
