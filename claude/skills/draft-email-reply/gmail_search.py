#!/usr/bin/env python3
"""Read-only Gmail search: list messages matching a query in any Lave mailbox.
  ../gmail-draft/run.sh --script gmail_search.py <mailbox> "<gmail query>"
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path.home()/"Developer/GitHub/work-os/claude/skills/gmail-draft/scripts"))
import gmail_draft as gd
import os
helper = os.environ["GMAIL_DRAFT_CREDENTIAL_HELPER"]
subject, query = sys.argv[1], sys.argv[2]
with gd.delegated_credentials(subject, "unused", helper) as creds:
    s = gd.api_session(creds)
    r = s.get(f"{gd.GMAIL_API}/users/me/messages", params={"q": query, "maxResults": 30}, timeout=60)
    r.raise_for_status()
    for m in r.json().get("messages") or []:
        d = s.get(f"{gd.GMAIL_API}/users/me/messages/{m['id']}", params={"format": "metadata", "metadataHeaders": ["From","To","Subject","Date"]}, timeout=60).json()
        h = gd._header_map(d.get("payload") or {})
        print(f"{h.get('date','')[:25]:25} | {h.get('from','')[:40]:40} | {h.get('to','')[:35]:35} | {h.get('subject','')}")
