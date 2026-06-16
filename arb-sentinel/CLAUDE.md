# arb-sentinel — Claude Code rules

## Core constraint

This package is deterministic Python on launchd. Never invoke `claude -p` from
a scheduled run (avoids the post-2026-06-15 credit pool). The only LLM use is
`llm.py` (M3), which calls Groq/Anthropic API off both Claude pools, at most a
few times/day. Collectors must never raise. Secrets, state, logs are gitignored.

## Git workflow (follow exactly)

- Work on `main`.
- Stage ONLY explicitly named paths — never `git add -A` or `git add .`
  (risk of sweeping in `.env` or large binaries).
- Commit + push after every logical slice of work, not batched at end of session.
- Commit messages should describe the *why*, not just the *what*.
- Never use `--no-verify`, never force-push to `main`, never amend
  already-pushed commits.

## What lives where

| Path | Purpose |
|------|---------|
| `arb_sentinel/collectors/` | Per-exchange public API pullers (must not raise) |
| `arb_sentinel/models.py` | `Opportunity` dataclass + `stable_id()` |
| `arb_sentinel/engine.py` | Net-spread calc, time-window, tier grading |
| `arb_sentinel/config.py` | Loads `config.yaml` + `.env` into a `Cfg` namespace |
| `arb_sentinel/state.py` | JSON dedup store in `state/` |
| `arb_sentinel/notify.py` | Telegram sender (graded alerts) |
| `arb_sentinel/llm.py` | M3: Groq/Anthropic call for announcement parsing |
| `arb_sentinel/run.py` | Orchestrator combining all modules |
| `arb_sentinel/__main__.py` | CLI entry point (`--task test|rates|digest`) |
| `tests/` | pytest fixtures + unit tests |
| `launchd/` | `.plist` files for macOS scheduling |
| `scripts/` | One-off helper scripts |

## Testing

```bash
.venv/bin/pytest tests/ -v
```

All tests must pass before committing. Collectors are tested with fixture JSON
in `tests/fixtures/`.
