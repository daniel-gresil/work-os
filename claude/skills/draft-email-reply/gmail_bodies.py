#!/usr/bin/env python3
"""Read-only Gmail reader: print the bodies of the N newest messages matching a query.
  ../gmail-draft/run.sh --script gmail_bodies.py <mailbox> "<gmail query>" <n>
"""
import sys, os, re, html
from pathlib import Path
sys.path.insert(0, str(Path.home()/"Developer/GitHub/work-os/claude/skills/gmail-draft/scripts"))
import gmail_draft as gd
helper = os.environ["GMAIL_DRAFT_CREDENTIAL_HELPER"]
subject, query, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
def text_of(p):
    t = gd._mime_text(p, "text/plain")
    if t.strip(): return t
    raw = gd._mime_text(p, "text/html")
    raw = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", raw)
    return html.unescape(re.sub(r"<[^>]+>", "", raw))
with gd.delegated_credentials(subject, "unused", helper) as creds:
    s = gd.api_session(creds)
    r = s.get(f"{gd.GMAIL_API}/users/me/messages", params={"q": query, "maxResults": n}, timeout=60); r.raise_for_status()
    for m in r.json().get("messages") or []:
        d = s.get(f"{gd.GMAIL_API}/users/me/messages/{m['id']}", params={"format": "full"}, timeout=60).json()
        h = gd._header_map(d.get("payload") or {})
        body = re.sub(r"\n\s*\n+", "\n", text_of(d["payload"])).strip()
        print("="*80); print(h.get("date"), "|", h.get("subject")); print("-"*80); print(body[:1800])
