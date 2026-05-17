---
name: init-project
description: Use when starting a new project from this template — collects project name/description and team preferences, then runs the deterministic initializer to wire Knowledge Graph + the agent team in place.
---

# init-project

You are initializing THIS cloned template directory in place as a new project.

## Collect (ask only what's not already given, one question at a time)

1. Project name — default: current folder name.
2. Project description — one sentence.
3. Agent team? — default yes. If yes, template: `pair` / `team` (default) /
   `review` / `debate` / `managed`; providers: `all` (default) / `claude` /
   `gemini` / `codex`.
4. Reset git? — if the user cloned this template and wants fresh history,
   yes (moves `.git` to a timestamped backup, then `git init`).

## Run the engine (do NOT re-implement its steps)

Build one command and run it via Bash:

```
node scripts/initialize.js --name "<name>" --desc "<desc>" \
  [--no-team] [--providers <p>] [--template <t>] [--reset-git]
```

- Omit `--no-team` when a team is wanted; include it when not.
- Pass `--providers` / `--template` only when a team is wanted.

## After it runs

- Relay the engine's "Next steps" output to the user.
- If it exits non-zero: report the failing step verbatim. The fix is always
  "resolve the cause, then re-run this skill" — every step is idempotent.
- Do not hand-edit `.mcp.json`, `.claude/settings.json`, or `CLAUDE.md`; the
  engine owns them. Re-run the skill instead.
