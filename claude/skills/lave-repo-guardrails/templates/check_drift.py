#!/usr/bin/env python3
"""Compare LIVE Apps Script source (from the Apps Script REST API projects.getContent)
against the files committed in this repo, and decide whether to notify Teams.

Stdlib only — no pip installs needed in CI.

Inputs (paths via args):
  --live   live content JSON  (the projects.getContent response: {"files":[{name,type,source}]})
  --meta   project meta JSON  (projects.get response: has lastModifyUser.email, updateTime)
  --repo   repo root to compare against (default ".")
  --prev-sig  file holding the previous drift signature (may not exist)
  --out-card  where to write the Teams Adaptive Card JSON (only if notifying)
  --out-sig   where to write the new drift signature

Outputs:
  - Writes the new signature to --out-sig.
  - If there is drift AND the signature changed since --prev-sig, writes the Adaptive
    Card to --out-card and prints "NOTIFY=true"; otherwise prints "NOTIFY=false".
  - Always prints a human-readable summary to stdout (shown in the Actions log).

Comparison rules (mirror how clasp manages the project):
  - Only clasp-managed files are compared: type SERVER_JS -> <name>.js,
    HTML -> <name>.html, JSON -> <name>.json (i.e. appsscript.json).
  - appsscript.json is compared by parsing JSON and deep-comparing (clasp reformats it,
    so a textual diff would be a false positive).
  - Other files: line endings normalized to LF and trailing EOF newline ignored.
  - Classifies each file as: modified | live_only | repo_only.
"""
import argparse, json, hashlib, os, sys

TYPE_EXT = {"SERVER_JS": ".js", "HTML": ".html", "JSON": ".json"}

def norm_text(s):
    return s.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")

def load_live(path):
    data = json.load(open(path))
    out = {}
    for f in data.get("files", []):
        ext = TYPE_EXT.get(f.get("type"))
        if not ext:
            continue
        out[f["name"] + ext] = f.get("source", "")
    return out

def repo_files(root):
    """Clasp-managed files committed in the repo: root-level *.js, *.html, appsscript.json."""
    out = {}
    for name in os.listdir(root):
        p = os.path.join(root, name)
        if not os.path.isfile(p):
            continue
        if name.endswith(".js") or name.endswith(".html") or name == "appsscript.json":
            out[name] = open(p, encoding="utf-8").read()
    return out

def same(name, live_src, repo_src):
    if name == "appsscript.json":
        try:
            return json.loads(live_src) == json.loads(repo_src)
        except Exception:
            pass  # fall through to text compare if either side isn't valid JSON
    return norm_text(live_src) == norm_text(repo_src)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--prev-sig", default="")
    ap.add_argument("--out-card", default="card.json")
    ap.add_argument("--out-sig", default="sig.txt")
    ap.add_argument("--repo-url", default="")
    ap.add_argument("--repo-name", default="")
    a = ap.parse_args()

    live = load_live(a.live)
    repo = repo_files(a.repo)
    meta = json.load(open(a.meta)) if os.path.exists(a.meta) else {}

    live_names, repo_names = set(live), set(repo)
    modified = sorted(n for n in (live_names & repo_names) if not same(n, live[n], repo[n]))
    live_only = sorted(live_names - repo_names)   # on live, not committed -> the main concern
    repo_only = sorted(repo_names - live_names)   # in repo, not pushed to live

    drift = bool(modified or live_only or repo_only)

    # signature = stable hash of the drift set (filenames + which bucket). Changes only
    # when the SET of out-of-sync files changes, so we don't re-alert every hour.
    sig_basis = json.dumps({"modified": modified, "live_only": live_only, "repo_only": repo_only},
                           sort_keys=True)
    sig = hashlib.sha256(sig_basis.encode()).hexdigest() if drift else "INSYNC"
    open(a.out_sig, "w").write(sig)

    prev = ""
    if a.prev_sig and os.path.exists(a.prev_sig):
        prev = open(a.prev_sig).read().strip()

    who = (meta.get("lastModifyUser") or {}).get("email", "unknown")
    when = meta.get("updateTime", "unknown")

    # --- human-readable summary (Actions log) ---
    print("=== Live vs GitHub drift check ===")
    print(f"live files: {len(live)} | repo files: {len(repo)}")
    print(f"modified:  {modified or 'none'}")
    print(f"live-only (edited live, not in GitHub): {live_only or 'none'}")
    print(f"repo-only (in GitHub, not pushed live): {repo_only or 'none'}")
    print(f"last live edit: {who} at {when}")
    print(f"signature: {sig} (prev: {prev or 'none'})")

    notify = drift and sig != prev
    print(f"NOTIFY={'true' if notify else 'false'}")
    if not notify:
        return

    def bullets(title, items):
        return f"\n\n**{title}:**\n" + "\n".join(f"- {x}" for x in items) if items else ""

    body_md = (
        f"Someone edited the **live Apps Script** (ProductionWIP) without committing to GitHub, "
        f"or the repo is ahead of live. The two are **out of sync**."
        f"\n\n**Last live edit:** {who} — {when}"
        + bullets("Edited live, NOT in GitHub", live_only)
        + bullets("Changed (live ≠ GitHub)", modified)
        + bullets("In GitHub, NOT pushed live", repo_only)
        + "\n\nPlease reconcile: pull live → commit/PR, or push the repo to live."
    )

    card = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {"type": "TextBlock", "size": "Large", "weight": "Bolder", "color": "Attention",
                     "text": f"⚠️ Live code is out of sync with GitHub"
                             + (f" — {a.repo_name}" if a.repo_name else ""), "wrap": True},
                    {"type": "TextBlock", "text": body_md, "wrap": True},
                ],
                "actions": ([{"type": "Action.OpenUrl", "title": "Open repo", "url": a.repo_url}]
                            if a.repo_url else []),
            },
        }],
    }
    json.dump(card, open(a.out_card, "w"))
    print(f"wrote Adaptive Card -> {a.out_card}")

if __name__ == "__main__":
    main()
