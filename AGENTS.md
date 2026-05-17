# new_financial-report-system — Agent Instructions

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
