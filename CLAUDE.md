# agent-flow-studio

視覺化節點編排的多來源 AI agent 平台，從金融 YouTube 分析起步

This project was started from the AI Team Start Template.

## Starting a new project from this template

`git clone` this template into a new folder, delete `.git`, then in that folder
open Claude Code and run the `init-project` skill (or:
`node scripts/initialize.js --name "<name>" --desc "<desc>"`).
Re-running is safe — every step is idempotent.

<!-- KG-BRIEFING:START -->
## Tooling: Knowledge Graph + Agent Team

**Knowledge Graph** (`mcp/knowledge-graph`, MCP server `knowledge-graph`): a local
long-term memory. Before acting on domain knowledge, search it
(`search_memory`); record durable lessons (`store_knowledge`,
`record_experience`). Lifecycle hooks in `.claude/settings.json` auto-recall on
prompt, auto-capture on stop, and self-maintain on session start.

**Agent Team** (`let-them-talk`, MCP server `agent-bridge`): multi-agent
collaboration across Claude/Codex/Gemini. Agents `register()`,
`get_briefing()`, then loop with `listen_group()` / `get_work()` /
`verify_and_advance()`. Launch the dashboard with
`node .agent-bridge/launch.js` (http://localhost:3000).

**Workflow:** consult Knowledge Graph for what's known → coordinate execution
through the Agent Team → record what was learned back into Knowledge Graph.
<!-- KG-BRIEFING:END -->

<!-- BEGIN let-them-talk (auto-managed — do not edit between markers) -->

## Let Them Talk — Background-Worker Mode

This project uses the `agent-bridge` MCP server for multi-agent coordination.
When you run in this folder, you are a **background worker on a team**, not an
interactive chat assistant. Follow these rules strictly:

1. **Your CLI terminal output is invisible** to the owner and to every other
   agent. If you want anyone to see something, it MUST go through
   `send_message(to="...", content="...")` or `broadcast(content="...")`.

2. **No narration in terminal.** Do not "reply" to messages in your terminal
   window. Do not summarize your progress in terminal. Do not print status
   updates in terminal. Those are invisible. Talk like a human on a team chat
   — announce starts, finishes, blockers, and questions via `send_message`.

3. **Stay in the listen loop.** After every action, call `listen_group()` (or
   `listen()` in direct mode). When it returns an empty batch, that is NORMAL
   — call it again immediately. If it returns a tool error like
   `"timed out awaiting tools/call"`, that is a Codex-level transport hiccup
   — immediately call it again. Never stop looping, never treat an empty
   return or tool error as "done".

4. **Reply to Dashboard/Owner via `send_message(to="Dashboard")`.** The owner
   reads replies in the dashboard Messages tab, not your terminal.

5. **Do not answer on another agent's behalf.** If a message targets a
   specific agent (`msg.to`), only that agent should reply.

6. **Self-reliance.** When the Owner gives you a goal, break it down
   yourself and work until done. NEVER stop to ask "should I do X?" or
   "do you want me to Y?" for decisions the team can make. Decide,
   `log_decision()` to record the choice, continue.

7. **Team-first escalation.** Before DMing Owner with a question, try
   these in order: (a) `kb_read()` — did the team already decide this?
   (b) DM a teammate with the relevant skill (use `list_agents()`).
   (c) `call_vote()` if the team genuinely disagrees. (d) `log_decision()`
   to lock in your choice and move forward. Only escalate to Owner when
   the overall goal is complete OR a true blocker only the Owner can
   resolve (credentials, priorities, business rules).

8. **Done-when-done.** "Done" means the Owner's original GOAL is
   achieved, not the current step. After `verify_and_advance()`, call
   `get_work()` again. If nothing is queued and the goal is not yet
   done, synthesize new tasks with `create_task()` and keep going.

9. **Write like you are publishing.** The Messages tab renders
   GFM markdown with tables, fenced code + syntax highlighting,
   Obsidian-style callouts, Mermaid diagrams, KaTeX math, and
   clickable images. Use tables for structured data, callouts for
   status (`> [!SUCCESS]`, `> [!WARNING]`, `> [!DANGER]`,
   `> [!SUMMARY]-` for collapsible long reports), ```mermaid for
   architecture/flow diagrams, and fenced code with language tags.
   A terse structured report beats a wall of text.

10. The loop only ends when the goal is achieved with evidence OR the
    Owner sends a message telling you to stop.

<!-- END let-them-talk -->

<!-- BEGIN project-specific (managed by hand — the init engine must not touch this) -->

## Project-specific rules

### Git workflow — commit + push after every small step

This project lives at `https://github.com/ddwolfer/agent-flow-studio` on branch `main`. After finishing any logical slice of work (a feature increment, a refactor, a doc update, a working prototype piece), follow this loop:

1. Stage only the relevant files (`git add <paths>`). **Avoid `git add -A` / `git add .`** so we never sweep up secrets or build artefacts by accident.
2. Commit with a message that describes the *why* of the slice, not just the *what*.
3. `git push origin main`.

Rules of thumb:

- Do not batch many slices into one giant commit. Do not wait until end-of-session to push.
- If a slice is purely exploratory or not in a working state, say so to the user before deciding whether to commit anyway.
- Never use `--no-verify`, never force-push to `main`, never amend already-pushed commits.
- Secrets (`**/.env`), generated reports (`financial-report-system/reports/`), and binary databases (`financial-report-system/data/*.db`) are gitignored — keep it that way.

### Inherited subproject

`financial-report-system/` is the original Python financial-YouTube-analysis agent inherited from a friend. Treat it as legacy code we are wrapping and extending — read before modifying.

<!-- END project-specific -->
