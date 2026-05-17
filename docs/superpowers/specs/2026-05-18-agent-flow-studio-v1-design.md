# agent-flow-studio v1 — Design Spec

- **Date:** 2026-05-18
- **Status:** Approved (brainstorming complete; ready for implementation planning)
- **Scope:** First usable milestone (v1) of agent-flow-studio, wrapping the inherited `financial-report-system/`.

## 1. Context & Locked Decisions

`financial-report-system/` is not a Python app — it is **Claude Code skills + bash cron + `claude -p` + SQLite + MCP**. The execution engine is the local `claude` CLI in headless mode. The product's eventual goal is an n8n-style visual node editor for multi-source AI agents, not limited to finance.

Decisions locked during brainstorming (see KG node `agent-flow-studio: architecture direction`, id `b1d65cc0-71e4-49ef-a1b3-80a4cdc31f4a`):

- **Route A** — build the data/orchestration layer first; the ReactFlow node canvas comes later on the same model. (Rejected: canvas-first; LangFlow/Dify adaptation — they orchestrate Python/LLM chains, not `claude -p` skill invocations.)
- **Option 1** — the runner keeps invoking the **local `claude -p`** + existing Claude Code skills/MCP. Preserves today's report quality with zero risk; fastest. The "sellable / hosted on Anthropic API" premise was **explicitly dropped** — this is a self-use tool. No API-migration path is pre-built (YAGNI). Sole structural concession: the runner is collapsed into a **single module** with one swap seam.
- **Plan C** — the new runner becomes the entry point and orchestrates source/prompt/analysis (externalized, UI-editable), but **reuses the inherited stable mechanical steps** (Chrome headless HTML→PDF, `notify.sh` Discord/LINE) as callable sub-steps. They are not rewritten; they are not pain points.
- **v1 scope = Option 3** — single **Eason** pipeline externalized + **dynamic add-YouTuber** (any added channel applies the Eason framework prompts in v1) + manual trigger + a simple web UI. The other two cron pipelines (游庭皓 briefing, stock-news) are untouched and keep running on the original cron/bash.
- **Config store = files in git (Option B)** — channel list + pipeline defs as YAML, prompts as `.md`. Execution results still go to the existing SQLite. Directly fixes README pain point #7 (prompts hardcoded in bash heredocs): prompts become diffable / reviewable / revertable.
- **Tech stack = Next.js full-stack (TypeScript)** — one codebase for UI + API(runner) + the future ReactFlow canvas. The runner is an API route that spawns `claude -p`.

The inherited author's README known-issues list is the de facto backlog. v1 directly addresses #1 (date inference), #4 (hardcoded paths), #7 (prompts in heredocs), #10 (hardcoded channels), and partially #5/#6 (error handling, retry/idempotency).

## 2. Config Data Model & File Structure

All new code lives under `studio/` at the repo root. `financial-report-system/` is essentially untouched (read, reused, not modified).

```
studio/
├─ config/
│  ├─ channels.yaml              # YouTuber list — UI add/disable edits this
│  └─ pipelines/eason.yaml       # one pipeline definition
├─ prompts/eason/                # editable prompts extracted from bash heredocs + skill references
│  ├─ main.md                    #   main analysis prompt ({{channel.*}} {{calendar}} placeholders)
│  ├─ framework.md               #   Eason 5-layer framework (was eason-framework.md)
│  ├─ voice.md                   #   Eason tone (was eason-vocabulary.md)
│  ├─ picks.md                   #   stock-picks extraction (was eason-daily.sh heredoc)
│  └─ judge-rubric.md            #   quality self-check rubric (see §5)
├─ runs/                         # per-run records (gitignored — execution output, not config)
│  └─ <runId>/run.json + claude.log
└─ app/                          # Next.js (UI + API/runner)
```

### `config/channels.yaml`

```yaml
channels:
  - id: eason                       # stable slug
    handle: "@m168"
    name: "張貽程 / Eason"
    search_query: "張貽程 外資超錢線"
    pipeline: eason                 # which pipeline; in v1 every channel uses the eason framework
    enabled: true
  - id: yutinghao
    handle: "@yutinghaofinance"
    name: "游庭皓"
    search_query: "游庭皓 早晨財經速解讀"
    pipeline: eason
    enabled: false
```

### `config/pipelines/eason.yaml`

```yaml
name: eason
model: claude-sonnet-4-6
max_turns: 50
prompt:
  template: prompts/eason/main.md
  references: [prompts/eason/framework.md, prompts/eason/voice.md]
post:
  pdf: true                            # reuse inherited Chrome headless step
  notify: false                        # v1 default off; UI can enable
  picks:
    model: claude-haiku-4-5            # picks extraction stays on haiku (cheap, mechanical)
    prompt: prompts/eason/picks.md
quality_judge:
  model: claude-sonnet-4-6            # LLM-as-judge self-check model (user override: Sonnet, not Haiku)
  rubric: prompts/eason/judge-rubric.md
```

### `runs/<runId>/run.json`

`{ runId, channelId, status, startedAt, finishedAt, exitCode, reportHtmlPath, pdfPath, reportOk, pdfOk, notifyOk, notifySent, configSnapshot: { gitSha, promptHashes } }`

Report HTML/PDF continue to be written to the inherited pipeline's `reports/YYYY-MM-DD/`. Execution results still land in `financial.db` (`eason_training`/`eason_daily`/`eason_picks`) exactly as today. The inherited DB schema is **not** modified.

### Calendar-fact injection (fixes README #1)

`buildPrompt` computes today's weekday / holiday facts and injects them into the prompt instead of letting the LLM infer the calendar. Near-zero cost, kills the highest-frequency known bug.

## 3. Runner — Single Module

Location: `studio/app/lib/runner/`. One public entry point; internally split into independently testable stages.

```ts
runPipeline(channelId: string, opts?: { notify?: boolean }): Promise<RunResult>
```

| Stage | Responsibility | Boundary rationale |
|---|---|---|
| `loadConfig(channelId)` | Read channels.yaml + its pipeline.yaml + prompt `.md`; validate channel exists / enabled / files present | Config errors caught once here; throws typed `ConfigError` |
| `buildPrompt(channel, pipeline, calendar)` | Assemble final prompt: template + `{{channel.*}}` interpolation + `{{calendar}}` facts + references appended | **Pure function** — the quality-critical unit to test hardest |
| `runClaude(prompt, {model,maxTurns})` | Spawn `claude -p` with cwd = `financial-report-system/` (so existing skills/MCP resolve); stream stdout/stderr to `runs/<id>/claude.log`; return exitCode + produced HTML path | **The only place that knows `claude -p` exists** — the single swap seam |
| `postProcess(html, post)` | Per pipeline.post: inherited Chrome→PDF, optional `notify.sh`, then the haiku picks-extraction `claude -p` call | Inherited mechanical steps reused as-is (Plan C) |
| `recordRun(...)` | Write `runs/<id>/run.json`; state machine `pending→running→succeeded\|failed` | Execution records kept separate from config |

**Concurrency:** v1 is manual, low-frequency → single run at a time per process + per-channel re-entrancy lock (in-memory). The API route is a thin shell: it calls `runPipeline`, immediately returns a `runId`, and the UI polls run status (long `claude -p` calls never block an HTTP request).

**Prompt source-of-truth (ambiguity resolved):** the externalized files under `studio/prompts/eason/` are the single source of truth. `buildPrompt` produces a self-contained prompt string that **inlines** the framework/voice/reference content directly into the text passed to `claude -p` (rather than depending on the inherited `eason-analysis` skill's own bundled `references/` copies). The inherited skill mechanism may still be invoked for its tool/MCP wiring, but analytical content the user edits in the UI always reaches the model via the assembled prompt — so editing `framework.md`/`voice.md` always takes effect, with no divergence between the skill's bundled copies and the externalized files.

**Key invariant:** `runClaude` is the sole function coupled to the inherited execution mechanism; the other four stages are unaware of `claude -p`. Clean module boundary, testable, future-swappable.

## 4. Error Handling + Idempotency/Retry (README #5, #6)

**Core principle: never silently fall back.** The current bash sends a fake "report produced" message when `claude -p` fails; the new runner always makes failure visible.

| Mechanism | Design |
|---|---|
| Typed errors | Each stage throws a named error: `ConfigError` / `ClaudeRunError` / `PostProcessError`. `runPipeline` catches → records `failed{stage, message, claudeLogPath}` → UI flags it in red with a link to `claude.log`. No success masquerade. |
| Sub-step status | run.json records independent `reportOk / pdfOk / notifyOk`. Analysis+report succeeded but notify failed → run is not marked failed; report is still viewable; notify is independently retryable (fixes #6 "Discord push failed, can't resend"). |
| Idempotency | Every run = a new `runId` (timestamp+channel); nothing is overwritten. Retry = clean re-run as a new record (`claude -p` has no mid-stream resume, so no resume is attempted). `notifySent` flag prevents duplicate sends for the same successful run. |
| Config snapshot | At run start, write repo git short SHA + each prompt file hash into run.json → which prompt produced which report is traceable & reproducible (also the basis for later prompt-quality regression comparison). |
| Crash safety | A process killed mid-run leaves a stuck `running`. On app start, sweep `runs/`; mark stale `running` with no live pid as `failed(interrupted)` so the UI never hangs. |
| Failure notify (optional) | v1 self-use: the UI is the primary alert. An optional `ERROR_WEBHOOK` toggle can push failures to a separate Discord channel via `notify.sh` (README #5 suggestion); default off. |

**Retry flow:** each run in the UI has a "re-run" button → opens a new run with the **same config snapshot** (pure `buildPrompt` guarantees same input → same prompt). A notify-only failure gets a separate "resend notification only" action — no need to re-run the whole pipeline.

## 5. Testing & Self-Verification Strategy

Per project memory `feedback_self_verification_first`: Claude plans and runs its own verification; the user is asked only as a last resort.

**Unit tests (pure, fast, self-run):**

| Target | How |
|---|---|
| `buildPrompt` | Golden tests: fixed channel+pipeline+calendar → assert the assembled prompt byte-for-byte. Quality lifeline; locked hardest. |
| `loadConfig` | Bad YAML / missing prompt file / disabled channel / unknown pipeline → assert the correct typed error. |
| Calendar facts | Fixed dates → assert weekday/holiday output (turns README #1 into a regression test). |
| Run state machine / stale sweep / idempotency flags | Temp `runs/` dir; assert transitions and re-entrancy guard. |

**Integration tests (self-driven, no tokens, no user):**

- `runClaude` seam takes an injectable `CLAUDE_BIN`: tests feed a fake `claude` script emitting fixed HTML → the whole `runPipeline` is verified end-to-end (spawn, cwd, log capture, exit handling, postProcess wiring) without calling the real API.
- `postProcess` takes injectable Chrome/notify commands → assert correct args and that sub-status flags are set correctly on failure.

**Report quality — the only place that may need the user:**

1. **Mechanically verifiable parts are self-owned:** after a real run, extract structured checks — required sections present, calendar facts correct, no future-dated or >7-day-old news (regex+date), picks rows well-formed. README #1/#3 are caught automatically.
2. **LLM-as-judge self-check:** score the new report against the existing `samples/` golden report + a rubric, using **`claude-sonnet-4-6`** (user override; configured in `pipelines/eason.yaml` `quality_judge.model`). Claude runs this and reads the score itself.
3. **Only the subjective "is this analysis genuinely insightful" call escalates to the user**, once, with the diff laid out. This is the documented last resort.

**Per-slice gate (tied to the commit/push + KG ritual):** every slice ships with the command run + actual output recorded in that slice's verification note *before* commit. No "should be done" claims without output evidence.

## 6. Out of Scope for v1 (Explicit YAGNI)

- The ReactFlow visual node canvas (Route A phase 2 — same config model, layered later).
- Anthropic-API orchestrator / hosted multi-tenant / sellable architecture (premise dropped).
- 游庭皓 briefing and stock-news pipelines (keep running on original cron/bash).
- Per-channel distinct analysis frameworks (v1: every added channel uses the Eason framework).
- Automatic scheduling/cron from the UI (v1 is manual-trigger; cron stays as-is externally).
- Modifying the inherited SQLite schema or rewriting `notify.sh` / the Chrome PDF step.

## 7. Verification That This Spec Is Buildable

Build sequence implied: (1) config loader + schema + `buildPrompt` (pure, fully unit-tested) → (2) `runClaude` seam with fake-CLI integration test → (3) `postProcess` reuse wiring → (4) error/idempotency + run records → (5) minimal Next.js UI (channels CRUD, prompt editor, run trigger+poll, report viewer) → (6) quality self-check harness. Each step is independently verifiable without the user; each is a commit/push slice with recorded evidence.
