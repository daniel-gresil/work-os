#!/usr/bin/env python3
"""
Build / format a "SPD Dashboard vs WIP Lavanderia" comparison record sheet via the Sheets API.

  uv run --with google-api-python-client --with google-auth tools/spd_compare.py build  <record_ss_id|new> <src_id> <lav_id> <label>
  uv run --with google-api-python-client --with google-auth tools/spd_compare.py format <record_ss_id> [sheet_title]
  uv run --with google-api-python-client --with google-auth tools/spd_compare.py draft  <record_ss_id> <src_id> <lav_id> <label> "<gmail search>"
  uv run --with google-api-python-client --with google-auth tools/spd_compare.py compare <src_id> <lav_id>   # read-only counts
  uv run --with google-api-python-client --with google-auth tools/spd_compare.py run    <record_ss_id|new> <src_id> <lav_id> <label> "<gmail search>"   # build + draft

build  : reads WIP Planned + Open Production, writes the matched rows (differences first) into the
         record spreadsheet (tab "<label> <lav_id>"), renames the file, applies formatting.
format : re-applies formatting only (header, freeze, filter, Y/N dropdown, yellow on non-"same" rows).
draft  : finds the newest inbox message matching <gmail search> (as daniel.souza@laveapparel.com via
         domain-wide delegation) and saves a REPLY DRAFT (never sends) summarising the sync + record sheet.

Credentials: service account from 1Password, read in-process, never written to disk.
"""
import json, os, subprocess, sys, datetime, base64
from email.message import EmailMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPD_ID = "1AMN1Ivy-bPPImI7Z_Y5d-0_nWph1In6Aee_88tJfFmA"
SPD_TAB = "WIP Planned "
SPD_TABS = ["WIP Planned ", "WIP Shipped"]  # same as dashboardSheetNames in the engine; Planned wins on a duplicate
LAV_ID = "1QrWLs4g-7qiz0I7x6-KAymXK0TNZX5hJJdHaCXJwztM"
LAV_TAB = "Open Production"
SPD_START, LAV_START = 8, 6
OP_ACCOUNT = "laveapparel.1password.com"  # Lave Apparel account; Daniel's personal account has no infra vault
IMPERSONATE = "daniel.souza@laveapparel.com"
DEFAULT_CC = ("Jessie Leal <Jessie@vintageindustries.mx>, Jose Anaya <Jose@vintageindustries.mx>, "
              "Sandra Medina <Sandra.Medina@laveapparel.com>, Giezi Mizraim <giezi@vintageindustries.mx>, "
              "Jocelyn Anguiano <jocelyn@vintageindustries.mx>, Daniel Flores <daniel@vintageindustries.mx>")  # DWD fallback when the SA is not shared on the file

HEADER = ["VI Job#", "Lave row", "Lave Customer Style (6095)", "Lave Colorway (6157)",
          "Lave Mill Blank Style# (6116)", "Lave Mill Blank Colorway (6117)", "SPD row",
          "SPD Mill Blank Style# (S1011)", "SPD Colorway (S1013)", "status",
          None, None, "Client OK to overwrite? (Y/N)", "Client comments"]
BLUE = {"red": 0.788, "green": 0.855, "blue": 0.973}
YELLOW = {"red": 1, "green": 0.949, "blue": 0.8}


_SA = {}
# Preferred: workspace SA with domain-wide delegation (creates files in Daniel's Drive, reads/writes any of
# his sheets, saves Gmail drafts). Fallback: wip-sync-tool SA (needs the sheet shared with it).
WS_ITEM = "op://hermes-crew/google-workspace-lave-service-account/credential"
WIP_ITEM = "op://infra/GCP SA - wip-sync-tool/credential"


def op_read(ref):
    """One `op read` per item per process (one desktop prompt), always the Lave Apparel account."""
    if ref in _SA:
        return _SA[ref]
    acct = os.environ.get("OP_ACCOUNT") or OP_ACCOUNT
    r = subprocess.run(["op", "read", ref, "--account", acct], capture_output=True, text=True)
    if r.returncode != 0:
        err = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "?"
        raise SystemExit(f"op read {ref} failed: {err}")
    _SA[ref] = json.loads(r.stdout)
    print(f"1Password: read {ref.split('/')[3]} from {acct}", file=sys.stderr)
    return _SA[ref]


def sa_info():
    return op_read(WIP_ITEM)


SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose", "https://www.googleapis.com/auth/gmail.readonly"]


def creds_for(scopes, subject=None, info=None):
    c = service_account.Credentials.from_service_account_info(info or sa_info(), scopes=scopes)
    return c.with_subject(subject) if subject else c


def ws_creds(scopes):
    """Workspace SA impersonating Daniel; verified by fetching a token."""
    c = creds_for(scopes, IMPERSONATE, op_read(WS_ITEM))
    from google.auth.transport.requests import Request
    c.refresh(Request())
    return c


def svc(subject=None):
    return build("sheets", "v4", cache_discovery=False, credentials=creds_for(SHEETS_SCOPES, subject))


def sheets_as_daniel():
    try:
        return build("sheets", "v4", cache_discovery=False, credentials=ws_creds(SHEETS_SCOPES))
    except Exception as e:  # noqa
        print(f"note: workspace SA unavailable for Sheets ({str(e)[:80]}); using wip-sync-tool", file=sys.stderr)
        return None


def gmail():
    try:
        return build("gmail", "v1", cache_discovery=False, credentials=ws_creds(GMAIL_SCOPES))
    except Exception as e:  # noqa
        print(f"note: workspace SA unavailable for Gmail ({str(e)[:80]}); using wip-sync-tool DWD", file=sys.stderr)
        return build("gmail", "v1", cache_discovery=False, credentials=creds_for(GMAIL_SCOPES, IMPERSONATE))


def new_record_sheet(title):
    """Create an empty spreadsheet in Daniel's My Drive (workspace SA impersonating him)."""
    s = build("sheets", "v4", cache_discovery=False, credentials=ws_creds(SHEETS_SCOPES))
    ss = s.spreadsheets().create(body={"properties": {"title": title}}, fields="spreadsheetId").execute()
    return ss["spreadsheetId"]


def summary_text(label, lav_id, src_id, counts, record_url):
    n_over = sum(v for k, v in counts.items() if k != "same")
    lines = [
        f"the {label} column has been added to the nightly SPD Dashboard -> WIP Lavanderia sync "
        f"(dashboard {src_id} -> Lavanderia column {lav_id}), as approved in the ADO ticket. "
        f"On the next run the Lavanderia values will be overwritten with the dashboard values.",
        "",
        *([os.environ["DRAFT_NOTE"], ""] if os.environ.get("DRAFT_NOTE") else []),
        *([f"Comparison record for your review: {record_url}", ""] if record_url else []),
        f"What the comparison shows ({sum(counts.values())} matched jobs):",
    ]
    for k in ("same", "different", "blank on Lavanderia", "blank on SPD"):
        if counts.get(k):
            lines.append(f"  - {k}: {counts[k]}")
    if os.environ.get("DRAFT_GUARDED"):
        lines += ["", f"With the blank/zero guard in place, none of these {n_over} rows change on the first run. "
                  f"The sheet lists them first with the dashboard value highlighted so you can see exactly what would be "
                  f"written once the dashboard column is filled."]
    elif n_over:
        lines += ["", f"So {n_over} rows change on the first run; the rows that change are listed first and the "
                  f"dashboard value that will be written is highlighted in yellow. Use the \"Client OK to overwrite?\" "
                  f"column and comments if anything should not be updated."]
    else:
        lines += ["", "Every matched job already carries the dashboard value, so nothing changes on the first run; "
                  "from now on any dashboard update flows to Lavanderia nightly."]
    return "\n".join(lines)


def cmd_draft(record_id, src_id, lav_id, label, query):
    no_record = record_id == "-"
    s = open_sheets(LAV_ID if no_record else record_id)
    rows, counts = compute(s, src_id, lav_id)
    if no_record:
        record_url = None
    else:
        sid = sheet_id_by_title(s, record_id, f"{label} {lav_id}")
        record_url = f"https://docs.google.com/spreadsheets/d/{record_id}/edit" + (f"#gid={sid}" if sid is not None else "")
    g = gmail()
    h, thread_id = {}, None
    try:  # DWD may only be authorized for gmail.compose; then fall back to from:/subject: in the query
        if query.startswith("to:"):  # brand-new email, no thread: "to:<addr>" + DRAFT_SUBJECT
            h = {"from": query[3:].strip(), "subject": os.environ["DRAFT_SUBJECT"]}
            raise StopIteration
        if query.startswith("thread:"):  # exact thread id: reply to its newest message not sent by Daniel
            msgs = g.users().threads().get(userId="me", id=query.split(":", 1)[1], format="metadata", metadataHeaders=["From"]).execute()["messages"]
            theirs = [x for x in msgs if IMPERSONATE.lower() not in " ".join(h["value"] for h in x["payload"]["headers"]).lower()]
            hits = [{"id": (theirs or msgs)[-1]["id"]}]
        else:
            hits = g.users().messages().list(userId="me", q=query, maxResults=1).execute().get("messages", [])
        if not hits:
            raise SystemExit(f"no message matches: {query} (nothing created)")
        if hits:
            m = g.users().messages().get(userId="me", id=hits[0]["id"], format="metadata",
                                         metadataHeaders=["From", "To", "Cc", "Subject", "Message-ID", "References"]).execute()
            h = {x["name"].lower(): x["value"] for x in m["payload"]["headers"]}
            thread_id = m["threadId"]
    except SystemExit:
        raise
    except StopIteration:
        pass
    except Exception as e:  # noqa
        import re
        h["from"] = (re.search(r"from:(\S+)", query) or [None, ""])[1]
        h["subject"] = (re.search(r'subject:"([^"]+)"', query) or [None, ""])[1]
        print(f"note: inbox search unavailable ({str(e)[:60]}...); creating a standalone draft", file=sys.stderr)
    msg = EmailMessage()
    msg["To"] = h.get("from", "")
    import re as _re
    others = [a.strip() for a in _re.split(r",(?![^<]*>)", (h.get("to", "") + "," + h.get("cc", ""))) if a.strip()]
    others = [a for a in others if IMPERSONATE.lower() not in a.lower() and h.get("from", "").lower() not in a.lower()]
    msg["Cc"] = ", ".join(others) if others else DEFAULT_CC
    subj = h.get("subject", "")
    msg["Subject"] = subj if (subj.lower().startswith("re:") or query.startswith("to:")) else f"Re: {subj}"
    if h.get("message-id"):
        msg["In-Reply-To"] = h["message-id"]
        msg["References"] = (h.get("references", "") + " " + h["message-id"]).strip()
    first = msg["To"].split("<")[0].strip().strip('"').split(" ")[0]
    if "@" in first or not first:
        first = msg["To"].split("<")[-1].split("@")[0].split(".")[0].capitalize()
    body_text = os.environ.get("DRAFT_BODY") or summary_text(label, lav_id, src_id, counts, record_url)
    msg.set_content(f"Hi {first},\n\n" + body_text + "\n\nThanks,\nDaniel")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    body = {"message": {"raw": raw}}
    if thread_id:
        body["message"]["threadId"] = thread_id
    # replace any earlier draft on the same subject so re-runs never leave duplicates
    # (drafts.list q= does not match standalone drafts, so check subjects via metadata)
    old = []
    for od in g.users().drafts().list(userId="me", maxResults=40).execute().get("drafts", []):
        hdrs = g.users().drafts().get(userId="me", id=od["id"], format="metadata").execute()["message"]["payload"]["headers"]
        osubj = next((x["value"] for x in hdrs if x["name"].lower() == "subject"), "")
        if osubj.lower().lstrip("re: ") == msg["Subject"].lower().lstrip("re: "):
            g.users().drafts().delete(userId="me", id=od["id"]).execute(); old.append(od["id"])
    d = g.users().drafts().create(userId="me", body=body).execute()
    print(json.dumps({"draft_id": d["id"], "replaced": len(old), "to": msg["To"], "subject": msg["Subject"], "counts": counts}))
    print(msg.get_content())


def open_sheets(ss_id):
    """Sheets service that can read ss_id: workspace SA as Daniel first, then wip-sync-tool."""
    cands = [c for c in (sheets_as_daniel(), svc()) if c]
    for s in cands:
        try:
            s.spreadsheets().get(spreadsheetId=ss_id, fields="spreadsheetId").execute()
            return s
        except Exception as e:  # noqa
            last = e
    raise SystemExit(f"cannot open {ss_id}: {last}")


def grid(s, ss_id, tab):
    rows = s.spreadsheets().values().get(spreadsheetId=ss_id, range=f"'{tab}'",
                                         valueRenderOption="FORMATTED_VALUE").execute().get("values", [])
    ids = {}
    for i, v in enumerate(rows[0] if rows else []):
        v = str(v).strip()
        if v and v not in ids:
            ids[v] = i
    return rows, ids


def cell(rows, r, c):  # r is 1-based sheet row
    row = rows[r - 1] if r - 1 < len(rows) else []
    return str(row[c]).strip() if c < len(row) else ""


def key(v):
    v = v.strip().lower()
    return "" if (not v or v == "tbd") else v


def split(v):  # blank counts as 01; "1" and "01" are the same split
    v = v.strip().lower()
    return "1" if not v else (str(int(v)) if v.isdigit() else v)


def pair(job, sp):  # same key as spdRowKey_ in _sync_spd_dashboard.js
    k = key(job)
    return f"{k}|{split(sp)}" if k else ""


def norm(v):
    t = v.replace("$", "").replace(",", "").strip()
    try:
        return f"{round(float(t), 4):g}"
    except ValueError:
        return v.strip().lower()


# Dashboard -> Lavanderia value transforms, same as `derive` in _sync_spd_dashboard.js ("" = keep Lavanderia value)
DERIVE = {"S1264": lambda v: {"yes-w": "Yes", "yes-m": "Yes", "no": "No"}.get(v.strip().lower(), "")}


def compute(s, src_id, lav_id):
    lav, li = grid(s, LAV_ID, LAV_TAB)
    missing = [w for w in ["6059", "7285", "6095", "6157", "6116", "6117", str(lav_id)] if w not in li]
    if missing:
        raise SystemExit(f"missing in {LAV_TAB}: {missing}")
    jm = {}  # key -> (tab rows, tab cols, row number)
    for tab in SPD_TABS:
        spd, si = grid(s, SPD_ID, tab)
        missing = [w for w in ["S1005", "S1242", "S1011", "S1013", src_id] if w not in si]
        if missing:
            raise SystemExit(f"missing in {tab}: {missing}")
        for r in range(SPD_START, len(spd) + 1):
            k = pair(cell(spd, r, si["S1005"]), cell(spd, r, si["S1242"]))
            if k and k not in jm:
                jm[k] = (spd, si, r)
    out, counts = [], {}
    for r in range(LAV_START, len(lav) + 1):
        k = pair(cell(lav, r, li["6059"]), cell(lav, r, li["7285"]))
        if not k or k not in jm:
            continue
        spd, si, sr = jm[k]
        lv, sv = cell(lav, r, li[str(lav_id)]), DERIVE.get(src_id, lambda v: v)(cell(spd, sr, si[src_id]))
        st = "same" if norm(lv) == norm(sv) else ("blank on Lavanderia" if not lv else ("blank on SPD" if not sv else "different"))
        counts[st] = counts.get(st, 0) + 1
        sp = split(cell(lav, r, li["7285"]))
        out.append([cell(lav, r, li["6059"]) + ("" if sp == "1" else f" / split {cell(lav, r, li['7285'])}"), r, cell(lav, r, li["6095"]), cell(lav, r, li["6157"]),
                    cell(lav, r, li["6116"]), cell(lav, r, li["6117"]), sr, cell(spd, sr, si["S1011"]),
                    cell(spd, sr, si["S1013"]), st, lv, sv, "", ""])
    order = {"blank on Lavanderia": 0, "different": 1, "blank on SPD": 2, "same": 3}
    out.sort(key=lambda x: (order[x[9]], x[1]))
    return out, counts


def sheet_id_by_title(s, ss_id, title):
    meta = s.spreadsheets().get(spreadsheetId=ss_id, fields="sheets.properties").execute()
    for sh in meta["sheets"]:
        if sh["properties"]["title"] == title:
            return sh["properties"]["sheetId"]
    return None


def format_requests(sid, n_rows, statuses):
    """n_rows = data rows (excluding header). statuses = list aligned with data rows."""
    reqs = [
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": 14},
                        "cell": {"userEnteredFormat": {"backgroundColor": BLUE, "textFormat": {"bold": True}, "wrapStrategy": "WRAP", "verticalAlignment": "BOTTOM"}},
                        "fields": "userEnteredFormat(backgroundColor,textFormat,wrapStrategy,verticalAlignment)"}},
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
        {"clearBasicFilter": {"sheetId": sid}},
        {"setBasicFilter": {"filter": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": n_rows + 1, "startColumnIndex": 0, "endColumnIndex": 14}}}},
        {"setDataValidation": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": n_rows + 1, "startColumnIndex": 12, "endColumnIndex": 13},
                               "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "Y"}, {"userEnteredValue": "N"}]}, "showCustomUi": True, "strict": False}}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": n_rows + 1, "startColumnIndex": 10, "endColumnIndex": 12},
                        "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": 1, "blue": 1}}}, "fields": "userEnteredFormat.backgroundColor"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": n_rows + 1, "startColumnIndex": 0, "endColumnIndex": 14},
                        "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP"}}, "fields": "userEnteredFormat.wrapStrategy"}},
        {"autoResizeDimensions": {"dimensions": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 14}}},
    ]
    # yellow on the SPD value cell only where the row is not "same"
    for i, st in enumerate(statuses):
        if st != "same":
            reqs.append({"repeatCell": {"range": {"sheetId": sid, "startRowIndex": i + 1, "endRowIndex": i + 2, "startColumnIndex": 11, "endColumnIndex": 12},
                                        "cell": {"userEnteredFormat": {"backgroundColor": YELLOW}}, "fields": "userEnteredFormat.backgroundColor"}})
    return reqs


def cmd_build(record_id, src_id, lav_id, label):
    if record_id == "new":
        record_id = new_record_sheet(f"WIP Lavanderia - {label} ({lav_id}) comparison ({datetime.date.today().isoformat()})")
        print(f"created record sheet {record_id}", file=sys.stderr)
    s = open_sheets(record_id)
    rows, counts = compute(s, src_id, lav_id)
    header = [h if h else (f"Lave {label} ({lav_id})" if i == 10 else f"SPD {label} ({src_id})") for i, h in enumerate(HEADER)]
    tab = f"{label} {lav_id}"
    sid = sheet_id_by_title(s, record_id, tab)
    if sid is None:
        first = s.spreadsheets().get(spreadsheetId=record_id, fields="sheets.properties").execute()["sheets"][0]["properties"]
        if first["title"].startswith("Sheet"):
            sid = first["sheetId"]
            s.spreadsheets().batchUpdate(spreadsheetId=record_id, body={"requests": [
                {"updateSheetProperties": {"properties": {"sheetId": sid, "title": tab}, "fields": "title"}}]}).execute()
        else:
            sid = s.spreadsheets().batchUpdate(spreadsheetId=record_id, body={"requests": [{"addSheet": {"properties": {"title": tab}}}]}
                                               ).execute()["replies"][0]["addSheet"]["properties"]["sheetId"]
    s.spreadsheets().values().clear(spreadsheetId=record_id, range=f"'{tab}'").execute()
    s.spreadsheets().values().update(spreadsheetId=record_id, range=f"'{tab}'!A1", valueInputOption="USER_ENTERED",
                                     body={"values": [header] + rows}).execute()
    today = datetime.date.today().isoformat()
    reqs = [{"updateSpreadsheetProperties": {"properties": {"title": f"WIP Lavanderia - {label} ({lav_id}) comparison ({today})"}, "fields": "title"}}]
    reqs += format_requests(sid, len(rows), [r[9] for r in rows])
    s.spreadsheets().batchUpdate(spreadsheetId=record_id, body={"requests": reqs}).execute()
    print(json.dumps({"record_id": record_id, "tab": tab, "rows": len(rows), "counts": counts,
                      "url": f"https://docs.google.com/spreadsheets/d/{record_id}/edit#gid={sid}"}))
    return record_id


def cmd_format(record_id, title=None):
    s = open_sheets(record_id)
    meta = s.spreadsheets().get(spreadsheetId=record_id, fields="sheets.properties").execute()["sheets"]
    props = next((m["properties"] for m in meta if title is None or m["properties"]["title"] == title))
    tab, sid = props["title"], props["sheetId"]
    vals = s.spreadsheets().values().get(spreadsheetId=record_id, range=f"'{tab}'!A1:N").execute().get("values", [])
    data = [r for r in vals[1:] if r and str(r[0]).strip()]
    statuses = [(r[9] if len(r) > 9 else "") for r in data]
    s.spreadsheets().batchUpdate(spreadsheetId=record_id, body={"requests": format_requests(sid, len(data), statuses)}).execute()
    print(json.dumps({"tab": tab, "rows": len(data), "yellow": sum(1 for x in statuses if x != "same")}))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "build" and len(a) == 5:
        cmd_build(a[1], a[2], a[3], a[4])
    elif a and a[0] == "format" and len(a) in (2, 3):
        cmd_format(*a[1:])
    elif a and a[0] == "draft" and len(a) == 6:
        cmd_draft(*a[1:])
    elif a and a[0] == "selftest" and len(a) == 1:  # create + delete a scratch sheet as Daniel
        rid = new_record_sheet("zz spd_compare selftest (delete me)")
        build("drive", "v3", cache_discovery=False, credentials=ws_creds(SHEETS_SCOPES)).files().delete(fileId=rid).execute()
        g = gmail(); g.users().drafts().list(userId="me", maxResults=1).execute()
        print(json.dumps({"created_and_deleted": rid, "gmail_ok": True}))
    elif a and a[0] == "compare" and len(a) == 3:  # read-only
        s = open_sheets(LAV_ID)
        rows, counts = compute(s, a[1], a[2])
        spd, si = grid(s, SPD_ID, SPD_TAB); lav, li = grid(s, LAV_ID, LAV_TAB)
        hdr = {"spd": [cell(spd, r, si[a[1]]) for r in range(2, SPD_START)], "lav": [cell(lav, r, li[a[2]]) for r in range(2, LAV_START)]}
        print(json.dumps({"headers": hdr, "counts": counts, "spd_values": sorted({r[11] for r in rows}),
                          "changes": [[r[0], r[1], r[10], r[11], r[9]] for r in rows if r[9] != "same"][:60]}))
    elif a and a[0] == "run" and len(a) == 6:  # build + draft, one process; record_ss_id may be "new"
        rid = cmd_build(*a[1:5])
        cmd_draft(rid, *a[2:])
    else:
        raise SystemExit(__doc__)
