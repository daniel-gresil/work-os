---
name: ado-add-task
description: Use when Daniel asks to add a task, issue, or card to the ADO board, IT board, Azure DevOps backlog, or says things like "leave a task on ADO", "put this on the board", "create an issue for X" — from any repo.
---

# ado-add-task

Create Issue work items on the LaveApparel / IT Dept board from a short request.
Parse title, description, assignee, and effort from the message; everything else is fixed below.

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
[ -f ~/.cache/claude-secrets/it-tasks-dashboard/env.sh ] \
  && source ~/.cache/claude-secrets/it-tasks-dashboard/env.sh \
  || export ADO_PAT=$(op read "op://Private/ADO PAT it-board-dashboard/credential" --account laveapparel.1password.com)
```

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

Drop the AssignedTo/Description entries when not provided. Reply with:
`https://dev.azure.com/LaveApparel/IT%20Dept/_workitems/edit/<id>`

## Errors

On any failure: report the API error verbatim AND the full intended card content
(title/description/assignee/effort/epic) so nothing is lost. One retry on transient
network errors only. "Unknown identity" → the account isn't an org member; tell Daniel
(fixed in org Settings → Users), don't retry.
