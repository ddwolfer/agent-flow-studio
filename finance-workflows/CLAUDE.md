# finance-workflows — instructions for working in this folder

This folder is a lean Python workflow runner for producing daily financial
reports. It is parallel to `../studio/` (which is being archived). Read
`../docs/superpowers/specs/2026-05-21-finance-workflows-design.md` for the
full design.

## Run a workflow manually

```bash
cd finance-workflows
mcp/.venv/bin/python run-workflow.py crypto-daily
```

The HTML lands at `reports/<name>/<YYYY-MM-DD>.html`. Logs are at
`reports/<name>/_logs/<date>-<ts>.log`.

## Add a new workflow

1. Drop `workflows/<new-name>.json` (copy `crypto-daily.json` and edit).
2. Add `prompts/<new-domain>/{framework,voice,main}.md` if it's a new domain.
   For incremental additions reuse existing prompts in `prompts/shared/`.
3. If you need a source kind we don't have yet (e.g. Twitter, Substack), see
   "Add a source kind / MCP server" below.
4. Test: `mcp/.venv/bin/python run-workflow.py <new-name>` — produces HTML;
   inspect, iterate on prompts.

**Adding a workflow MUST be config + prompts only. No edits to `run-workflow.py`
or the existing MCP servers.**

## Add a source kind / MCP server

A "source kind" is wired through an MCP server. To add e.g. CoinGecko:

1. Write `mcp/servers/coingecko_server.py` (FastMCP, follow the patterns in
   `rss_server.py` / `web_fetch_server.py`: tools never raise, return shaped
   dicts on failure).
2. Add tests at `tests/test_coingecko_server.py` (monkeypatch the network
   call, assert returned shape).
3. Add the server to `mcp/mcp.json.tmpl`.
4. Add an entry to `TOOL_MAP` in `run-workflow.py` mapping the server name to
   its tool ids (this is the ONLY edit to runner code per new server).
5. Workflows can now declare `"tools": [..., "coingecko"]` and use
   `mcp__coingecko__<tool>`.

## Trust assumptions

- `web-fetch` makes arbitrary outbound HTTP. This is a local single-user tool;
  we accept this. Don't deploy as a service without adding a URL allow-list.
- `claude` must be authenticated before cron will work — run `claude`
  interactively at least once on this machine.

## Conventions

- All tools must NEVER raise; return shaped failure dicts (status, empty list).
- Prompts use `${TOKEN}` substitution; `{date}` is for the `output:` path
  template only.
- The runner is ≤200 LoC; don't grow it. New capability = new MCP server +
  workflow.json field.
