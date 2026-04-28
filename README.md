# Visary Cloud API Skills

Skills for agent-driven work with Visary Cloud APIs.

The root `SKILL.md` acts as a router: it selects the specialized sub-skill for the requested API domain and does not define API endpoints directly.

## Contents

- `SKILL.md` - root router skill.
- `scripts/` - shared runtime helpers used by all sub-skills.
- `subskills/tasktracker-api/` - TaskTracker workflows: tasks, epics, projects, comments, boards, sprints, milestones, labels, and related entities.
- `subskills/calendar-api/` - Calendar workflows: calendars, events, permissions, calendar import, and calendar export.
- `subskills/files-api/` - Files workflows: drives, items, uploads, downloads, previews, links, annotations, cleanup, and file-system metadata.

Each sub-skill contains:

- its own `SKILL.md` with usage rules;
- `assets/index/manifest.json` as the entry point into runtime indexes;
- compact domain indexes in `assets/index/*.json`;
- `api.py` as the short CLI entry point from the sub-skill root.

Shared HTTP and Visary Cloud configuration helpers live in the repository-level `scripts/` directory. Sub-skills should reuse those helpers instead of carrying local copies.

## How It Works

1. The agent loads the root `SKILL.md`.
2. The user request is routed to one or more sub-skills.
3. For each selected sub-skill, the agent opens that sub-skill's `SKILL.md`.
4. Before an API call, the agent opens `assets/index/manifest.json` for the selected sub-skill.
5. Endpoints are selected only from runtime indexes.
6. Commands are executed through the selected sub-skill's `api.py`.

The root skill must not call APIs directly and must not invent endpoints, fields, or payloads.

## Requirements

- Python 3.10+
- access to the relevant Visary Cloud APIs
- configured connection settings and client credentials

Supported environment variables:

```text
VIS_API_BASE_URL
VIS_TOKEN_URL
VIS_CLIENT_ID
VIS_CLIENT_SECRET
```

Local user configuration can also be stored in one JSON file:

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

Environment variables are not the only supported configuration mechanism, so the root `SKILL.md` does not require them in metadata.

## Security

Secrets must not be stored in the repository.

Use an external secret source:

- environment variables;
- `~/.config/visary-cloud.json`;
- the agent runtime's secret storage.

## Development

When API behavior changes, update the relevant sub-skill instead of the root router skill.

Update the root `SKILL.md` only when:

- a new API domain is added;
- routing rules change;
- shared requirements for the entire skills package change.
