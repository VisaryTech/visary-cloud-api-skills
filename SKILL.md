---
name: visary-cloud-api-skills
description: "Routes ERP API requests to specialized sub-skills for TaskTracker, Calendar, and Files APIs."
metadata: {"openclaw":{"requires":{"anyBins":["python","python3","py"]}}}
---

# Visary Cloud API Skills

Use this root skill as a router for ERP API work. It does not define API endpoints directly. For any concrete API call, load and follow the matching sub-skill under `subskills/`.

Shared runtime helpers live in repository-level `scripts/`. Specialized sub-skills should reuse those helpers instead of carrying duplicated HTTP or Visary Cloud auth/config code.

## Runtime Preflight

Before routing or making API calls, verify that Python is available. If it is unavailable, stop and report that Python is required. Do not use fallback tools or handwritten HTTP requests.

## Route Selection

- Use `subskills/tasktracker-api/SKILL.md` for ERP TaskTracker entities and workflows: tasks, epics, projects, comments, boards, sprints, milestones, labels, registries, project membership, task history, and epic history.
- Use `subskills/calendar-api/SKILL.md` for ERP Calendar entities and workflows: calendars, events, permissions, calendar import, and calendar export.
- Use `subskills/files-api/SKILL.md` for ERP Files entities and workflows: drives, items, uploads, downloads, previews, links, annotations, archive operations, cleanup, and file-system metadata.

If a user request spans multiple API domains, load every relevant sub-skill and handle each domain through its own workflow.

## Routing Rules

- Do not call API endpoints from this root skill directly.
- Do not invent fields, endpoints, payloads, or high-level scenarios at the root level.
- Before any concrete API call, open the selected sub-skill's `SKILL.md`.
- Follow the selected sub-skill's manifest-first workflow and use only endpoints listed in that sub-skill's runtime indexes.
- Use the selected sub-skill's `api.py` from that sub-skill root.
- If no sub-skill clearly covers the request, report that the request is outside the available Visary Cloud API skills and stop.

## Common Configuration

All sub-skills use client credentials and expect the same base ERP configuration:

- `VIS_CLIENT_ID`
- `VIS_CLIENT_SECRET`
- `VIS_API_BASE_URL`
- `VIS_TOKEN_URL`

Local user config may also be stored in one JSON file:

```json
{
  "apiBaseUrl": "https://vis.example",
  "tokenUrl": "https://id-vis.example/oidc/connect/token",
  "clientId": "client-id",
  "clientSecret": "client-secret"
}
```

Expected path:

```text
~/.config/visary-cloud.json
```

Secrets must not be committed to the repository.
