---
name: ado-add-task
description: Use when Daniel asks to add a task, issue, or card to the ADO board, IT board, Azure DevOps backlog, or says things like "leave a task on ADO", "put this on the board", "create an issue for X" — from any repo.
---

# ado-add-task

Create Issue work items on the LaveApparel / IT Dept board from a short request.
Parse title, description, assignee, and effort from the message; everything else is fixed below.

**Level: L2.** A short, fully specified request ("put X on the board") is its own approval.
A card built from a customer request is created only after Daniel approves the drafted card.

## Cards from a customer request (task app link)

1. The task app link (`script.google.com/.../exec?task_id=<id>`) does not load in the automated
   browser. `<id>` is a Google Doc: read it at `https://docs.google.com/document/d/<id>/mobilebasic`.
2. Look up what the request touches (sheets, repos) before drafting; don't ask Daniel what can be checked.
   Read sheet tabs in the browser with `/gviz/tq?tqx=out:html&sheet=<tab>&range=<A1>&headers=0`;
   never `out:csv`, which downloads a file. Merged header cells are dropped, so find columns by
   content too.
   When a cell holds a link, open the linked file before asking what it is. `gviz` returns only
   the link text; read link targets with `/htmlview/sheet?headers=true&gid=<gid>`, and list a
   file's tabs from the `/htmlview` page source.
   Always search the board for open cards on the same file (query below) and match their
   conventions (Epic, schedule, lookup rules).
3. The card covers what the request says and what Daniel describes. Downstream consequences
   (for example, how a total should behave later) go on the card as a note or a question for the
   requester; do not turn them into questions for Daniel.
   Show the drafted card and the gaps in the spec. Settle the gaps with Daniel one question at a
   time, each with a concrete example and a recommendation.
4. Create the card only after he approves the final draft. Questions for the requester go on the
   card and into a message Daniel sends himself.
   Before creating, list what is still open. Any decision that changes the requester's file or
   process is a point to confirm with them, even when Daniel has decided it; offer the message.
   Ask Daniel whether each such point is already confirmed before listing it for the requester;
   when he confirms it, state it as a rule on the card and drop the message.

## Check for an existing card (when Daniel asks)

Search every card with one WIQL query: `[System.Title]`, `[System.Description]` and
`[System.History]` (comments) each `CONTAINS` the request's keywords, in English and Spanish.
List the open matches with state and assignee, and read their descriptions, before drafting.

## Defaults

| Field | Value |
|---|---|
| Type / State | Issue / To Do (state is the default; don't set it) |
| Title | Required — draft one from the prose if not given verbatim |
| Description | Only if given; simple HTML in `System.Description` |
| Assignee | **Unassigned** unless named |
| Effort | `Microsoft.VSTS.Scheduling.Effort` = **1** unless specified (days; 0.5 = half day) |
| Iteration | `IT Dept` (backlog root — never a sprint; sprints are assigned deliberately later) |
| Parent Epic | **Ask** which Epic (list them) — unless the user already named one. One question covers a whole batch. |

## Roster (exact emails — do NOT guess patterns)

| Name | uniqueName |
|---|---|
| Daniel Souza | Daniel.Souza@laveapparel.com |
| Jose Chavez | jose.guadarrama@laveapparel.com |
| Rogelio Reyes | rogelio.reyes@laveapparel.com |
| Isaac Valdez | isaac.valdez@laveapparel.com |
| Gerardo Garcia | itsupport@laveapparel.com |
| Byron Corona | byron.corona@laveapparel.com |

First-name match is fine ("assign to Isaac"). Unknown name → ask.
For `System.AssignedTo` always send the combo format `"Name <uniqueName>"`
(e.g. `"Byron Corona <byron.corona@laveapparel.com>"`) — a bare email fails with
"unknown identity" for recently added org members; the combo format resolves them.

## Auth (never echo the PAT)

```bash
source ~/.cache/claude-secrets/it-tasks-dashboard/env.sh && [ -n "$ADO_PAT" ] || echo "no ADO_PAT"
```

If that cache is missing: in a repo with an op-secrets manifest (work-os included) a hook blocks
ad-hoc `op read`, even as a fallback inside a longer command. Add
`ADO_PAT = op://Private/ADO PAT it-board-dashboard/credential @ laveapparel.1password.com`
to the repo's manifest, run `~/.claude/op-secrets-load.sh`, and source that repo's cache.
Only in a repo with no manifest, read that same reference with `op read` directly.

## Calls

List Epics (for the parent question) — WIQL then titles:

```bash
curl -s -u ":$ADO_PAT" -X POST -H "Content-Type: application/json" \
  -d '{"query":"SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project AND [System.WorkItemType] = '"'"'Epic'"'"'"}' \
  "https://dev.azure.com/LaveApparel/IT%20Dept/_apis/wit/wiql?api-version=7.1"
# then: POST ids to .../wit/workitemsbatch with fields ["System.Title"]
```

Create (Content-Type MUST be `application/json-patch+json`):

```bash
curl -s -u ":$ADO_PAT" -X POST -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/LaveApparel/IT%20Dept/_apis/wit/workitems/\$Issue?api-version=7.1" -d '[
  {"op":"add","path":"/fields/System.Title","value":"<title>"},
  {"op":"add","path":"/fields/Microsoft.VSTS.Scheduling.Effort","value":1},
  {"op":"add","path":"/fields/System.IterationPath","value":"IT Dept"},
  {"op":"add","path":"/fields/System.AssignedTo","value":"Name <uniqueName>"},
  {"op":"add","path":"/fields/System.Description","value":"<div>...</div>"},
  {"op":"add","path":"/relations/-","value":{"rel":"System.LinkTypes.Hierarchy-Reverse","url":"https://dev.azure.com/LaveApparel/IT%20Dept/_apis/wit/workItems/<epicId>"}}
]'
```

New Epic (only when Daniel asks for one): same call with `\$Epic` in the URL and just the
Title and IterationPath entries; use the returned id as `<epicId>`.

Update an existing card: `PATCH .../wit/workitems/<id>?api-version=7.1` with
`[{"op":"replace","path":"/fields/System.Description","value":"..."}]`. Build long HTML bodies
with `jq -n --arg d "$DESC" '[...]' | curl ... -d @-` so quotes are escaped.

Drop the AssignedTo/Description entries when not provided. Reply with:
`https://dev.azure.com/LaveApparel/IT%20Dept/_workitems/edit/<id>`

## Errors

On any failure: report the API error verbatim AND the full intended card content
(title/description/assignee/effort/epic) so nothing is lost. One retry on transient
network errors only. "Unknown identity" → the account isn't an org member; tell Daniel
(fixed in org Settings → Users), don't retry.
