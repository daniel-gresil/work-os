#!/usr/bin/env python3
"""Write the LIVE Apps Script source (from a projects.getContent JSON, e.g. live.json
produced by fetch_live.py) into a target directory as the GAS files, so the repo's
working tree matches live. Use to establish a "main == live" baseline.

  python materialize_live.py --live live.json --into <repo_dir>

- Overwrites/creates <name>.js / <name>.html / appsscript.json from live.
- Does NOT delete files that exist in the repo but not on live; it prints them as
  "repo-only (not on live)" so a human can decide (deleting could drop intentional
  local-only files).
"""
import argparse, json, os

TYPE_EXT = {"SERVER_JS": ".js", "HTML": ".html", "JSON": ".json"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", required=True)
    ap.add_argument("--into", default=".")
    a = ap.parse_args()
    data = json.load(open(a.live))

    live_names = set()
    written = 0
    for f in data.get("files", []):
        ext = TYPE_EXT.get(f.get("type"))
        if not ext:
            continue
        fn = f["name"] + ext
        live_names.add(fn)
        with open(os.path.join(a.into, fn), "w", encoding="utf-8") as out:
            out.write(f.get("source", ""))
        written += 1

    # report repo-only GAS files (present in repo, absent from live) — NOT deleted
    repo_only = []
    for name in os.listdir(a.into):
        if (name.endswith(".js") or name.endswith(".html") or name == "appsscript.json") \
                and name not in live_names:
            repo_only.append(name)

    print(f"materialized {written} live files into {a.into}")
    if repo_only:
        print("repo-only (in repo, NOT on live) — left in place for review:")
        for n in sorted(repo_only):
            print(f"  - {n}")

if __name__ == "__main__":
    main()
