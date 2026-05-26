# finance-workflows

Daily financial reports (crypto / TW stock / US macro / deep stock research)
produced by a lean Python workflow runner that orchestrates `claude -p` + a
small set of MCP servers. See `finance-workflows/CLAUDE.md` for the runner-level
rules.

<!-- KG-BRIEFING:START -->
## Knowledge Graph

`mcp/knowledge-graph` (MCP server `knowledge-graph`) is a local long-term
memory. Before acting on domain knowledge, search it (`search_memory`); record
durable lessons (`store_knowledge`, `record_experience`). Lifecycle hooks in
`.claude/settings.json` auto-recall on prompt, auto-capture on stop, and
self-maintain on session start.
<!-- KG-BRIEFING:END -->

## Project-specific rules

### Git workflow — commit + push after every small step

This project lives at `https://github.com/ddwolfer/agent-flow-studio` on branch
`main`. After finishing any logical slice of work, follow this loop:

1. Stage only the relevant files (`git add <paths>`). **Avoid `git add -A` /
   `git add .`** so we never sweep up secrets or build artefacts by accident.
2. Commit with a message that describes the *why* of the slice, not just the
   *what*.
3. `git push origin main`.

Rules of thumb:

- Do not batch many slices into one giant commit. Do not wait until
  end-of-session to push.
- If a slice is purely exploratory or not in a working state, say so to the
  user before deciding whether to commit anyway.
- Never use `--no-verify`, never force-push to `main`, never amend
  already-pushed commits.
- Secrets (`**/.env`, `**/*cookies*.txt`) and generated reports
  (`finance-workflows/reports/`) are gitignored — keep it that way.
