#!/usr/bin/env python3
"""
Insert a new column into SPD Dashboard > "WIP Planned " and seed it from a WIP Lavanderia column.

  uv run --with google-api-python-client --with google-auth tools/spd_add_column.py \\
      <after_sid> <new_sid> <lav_id> "<row4 group>" "<row5 sizes>" "<row6 label>"  [... more 6-arg groups]

Header rows written: 1=<new_sid>, 2=<lav_id>, 3=SPD, 4=group, 5=sizes, 6=label. Formatting is inherited
from the column to the left; data rows get number format "0". Seed: for every dashboard job (S1005) that
matches a Lavanderia VI Ref# (6059), the first non-blank Lavanderia value for that job is written.
Several groups are processed right-to-left so earlier insertions do not shift later targets.
Each new S-id is also appended to the dashboard's "Column Config" tab, which is its S-id registry.
"""
import json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import spd_compare as sc


def main(specs):
    s = sc.open_sheets(sc.SPD_ID)
    meta = s.spreadsheets().get(spreadsheetId=sc.SPD_ID, fields="sheets.properties").execute()
    sid = next(sh["properties"]["sheetId"] for sh in meta["sheets"] if sh["properties"]["title"] == sc.SPD_TAB)
    spd, si = sc.grid(s, sc.SPD_ID, sc.SPD_TAB)
    lav, li = sc.grid(s, sc.LAV_ID, sc.LAV_TAB)
    n_rows = len(spd)
    for sp in specs:
        if sp["new_sid"] in si:
            raise SystemExit(f"{sp['new_sid']} already exists in {sc.SPD_TAB}")
        if sp["after_sid"] not in si or sp["lav_id"] not in li:
            raise SystemExit(f"missing column: {sp['after_sid']} / {sp['lav_id']}")
    # Lavanderia job -> first non-blank value per lav column
    seeds = {}
    for sp in specs:
        m = {}
        for r in range(sc.LAV_START, len(lav) + 1):
            k = sc.key(sc.cell(lav, r, li["6059"]))
            v = sc.cell(lav, r, li[sp["lav_id"]])
            if k and v and k not in m:
                m[k] = v
        seeds[sp["lav_id"]] = m
    report = []
    for sp in sorted(specs, key=lambda x: -si[x["after_sid"]]):  # right-to-left
        at = si[sp["after_sid"]] + 1  # 0-based index of the new column
        reqs = [
            {"insertDimension": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": at, "endIndex": at + 1}, "inheritFromBefore": True}},
            {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": sc.SPD_START - 1, "startColumnIndex": at, "endColumnIndex": at + 1},
                            "cell": {"userEnteredFormat": {"numberFormat": {"type": "NUMBER", "pattern": "0.##"}}},
                            "fields": "userEnteredFormat.numberFormat"}},
        ]
        s.spreadsheets().batchUpdate(spreadsheetId=sc.SPD_ID, body={"requests": reqs}).execute()
        col = sc.a1(at) if hasattr(sc, "a1") else a1(at)
        header = [[sp["new_sid"]], [sp["lav_id"]], ["SPD"], [sp["group"]], [sp["sizes"]], [sp["label"]]]
        data, written, jobs = [], 0, 0
        for r in range(sc.SPD_START, n_rows + 1):
            k = sc.key(sc.cell(spd, r, si["S1005"]))
            v = seeds[sp["lav_id"]].get(k, "") if k else ""
            if k: jobs += 1
            if v != "": written += 1
            data.append([v])
        s.spreadsheets().values().batchUpdate(spreadsheetId=sc.SPD_ID, body={"valueInputOption": "USER_ENTERED", "data": [
            {"range": f"'{sc.SPD_TAB}'!{col}1:{col}6", "values": header},
            {"range": f"'{sc.SPD_TAB}'!{col}{sc.SPD_START}:{col}{n_rows}", "values": data},
        ]}).execute()
        report.append({"new_sid": sp["new_sid"], "lav_id": sp["lav_id"], "column": col, "after": sp["after_sid"],
                       "dashboard_jobs": jobs, "seeded": written, "lav_jobs_with_value": len(seeds[sp["lav_id"]])})
    # record the new S-ids in the dashboard's own registry tab (Column ID | Column Name | Tab)
    s.spreadsheets().values().append(spreadsheetId=sc.SPD_ID, range="'Column Config'!A1", valueInputOption="USER_ENTERED",
                                     insertDataOption="INSERT_ROWS",
                                     body={"values": [[sp["new_sid"], f"{sp['group']} {sp['label']}".strip(), sc.SPD_TAB] for sp in specs]}).execute()
    # verify by re-reading row 1/2
    spd2, si2 = sc.grid(s, sc.SPD_ID, sc.SPD_TAB)
    for rep in report:
        c = si2.get(rep["new_sid"]); rep["verified"] = c is not None and sc.cell(spd2, 2, c) == rep["lav_id"] and sc.cell(spd2, 1, c - 1) == rep["after"]
    print(json.dumps(report, indent=1))


def a1(c):
    r = ""; c += 1
    while c:
        c, m = divmod(c - 1, 26); r = chr(65 + m) + r
    return r


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or len(a) % 6:
        raise SystemExit(__doc__)
    keys = ["after_sid", "new_sid", "lav_id", "group", "sizes", "label"]
    main([dict(zip(keys, a[i:i + 6])) for i in range(0, len(a), 6)])
