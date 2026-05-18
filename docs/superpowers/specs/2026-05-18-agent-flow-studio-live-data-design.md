# agent-flow-studio — Live Data Wiring Design Spec (Phase 2)

- **Date:** 2026-05-18
- **Status:** Draft for user review (self-reviewed)
- **Builds on:** `2026-05-18-agent-flow-studio-v1-design.md` (the verified deterministic skeleton, HEAD `3ed3825`)
- **Goal:** Make a real, **local** end-to-end Eason report producible — by building the 5 data MCP servers the inherited skill needs, adding a local subtitle fallback, and closing the known deterministic gaps. **No messaging** (Discord/LINE/Telegram) in this phase.

## 1. Context & Locked Decisions (from user)

The v1 skeleton is complete and test-verified, but a real run is blocked because the inherited `/eason-analysis` skill calls 5 MCP servers that exist only on the original author's machine. User decisions:

- **Build all 5 MCP servers ourselves** (do not wait for the friend's config).
- **Subtitle strategy:** existing captions first; if none, **local `gemma4:e4b` (Gemma 3n E4B, multimodal/audio) via the already-installed Ollama** transcribes the audio. Fully local, no cloud, no extra keys. faster-whisper is NOT built now (listed only as an optional future safeguard).
- **FRED:** reuse `FRED_API_KEY` from the inherited `financial-report-system/scripts/.env` (user authorized).
- **Messaging deferred:** Discord/LINE/Telegram entirely out of scope now; revisit after local reports look good. Notify keys in `.env` stay untouched/unused.
- **Local-first:** success = a report HTML/PDF saved on this machine.

Authoritative tool contract (extracted from the inherited skill files, file:line verified):

| Server (registered name) | Tools (exact names the prompt calls) | Backend / notes |
|---|---|---|
| `yt-dlp` | `ytdlp_search_videos(query, maxResults, uploadDateFilter)`; `ytdlp_download_transcript(language)` | wraps `yt-dlp`; transcript tool gets the whisper fallback |
| `twse` | `get_daily_market_trading_info`; `get_market_index_info`; `get_margin_trading_info`; `get_stock_daily_trading(stock_code)`; `get_foreign_investment_by_industry` | TWSE Open API `https://openapi.twse.com.tw/` (no key) |
| `yahoo-finance` | `get_stock_info(ticker)`; `get_historical_stock_prices(ticker)` | Yahoo public data via `yfinance` |
| `fred` | `fred_get_series(series_id)` | FRED API, needs `FRED_API_KEY` |
| `sqlite` | `query(sql, params?)` (any SQL, returns rows for SELECT / affected count otherwise); `create_record(table, values)` (INSERT one dict); `update_records(table, values, where)` (UPDATE with a where dict) | local `financial.db` |

`chart` MCP is **NOT** needed — the Eason report is hand-written HTML/CSS with emoji signal blocks (🟢🟡🔴), confirmed by reading the skill. Out of scope.

Tickers/series the prompt actually requests (must work end-to-end): yt search `"張貽程 外資超錢線"`; TWSE stocks `2408,6187,3006,3324,2317`; Yahoo `MU,2330.TW,TSM,BZ=F,GC=F,DX-Y.NYB,^SOX,^IXIC,^TWII`; FRED `FEDFUNDS,CPIAUCSL,T10Y2Y`; sqlite tables `eason_training`, `eason_daily`, `eason_picks` in `financial-report-system/data/financial.db` (schema in `financial-report-system/db/schema.sql`).

## 2. Architecture

```
studio/mcp/                      (NEW — one Python toolchain)
├─ .venv/                        (gitignored; yfinance, yt-dlp, mcp sdk, ollama client)
├─ requirements.txt
├─ mcp.json.tmpl                 (registry template; runner renders mcp.json with resolved paths/keys)
├─ servers/
│  ├─ ytdlp_server.py            (ytdlp_search_videos, ytdlp_download_transcript + gemma fallback)
│  ├─ twse_server.py             (5 tools)
│  ├─ yahoo_server.py            (2 tools, yfinance)
│  ├─ fred_server.py             (fred_get_series; key from env)
│  └─ sqlite_server.py           (query / create_record / update_records on financial.db)
└─ lib/gemma_transcribe.py       (yt-dlp audio → ffmpeg → chunk → local gemma4:e4b via Ollama → stitched transcript)
```

All 5 servers are **Python** (one `.venv`, one `requirements.txt`) using the official MCP Python SDK. Rationale: yt-dlp is Python/CLI-native; yfinance is the most robust Yahoo path; the subtitle fallback calls the already-installed local Ollama model; one runtime beats four. Each server is its own stdio process spawned by Claude Code via `--mcp-config`.

**Runner integration (the only changes to v1 code):**

- New `studio/lib/runner/mcpConfig.ts`: reads `FRED_API_KEY` from `financial-report-system/scripts/.env` at run time (parse `KEY=VALUE`, take only `FRED_API_KEY`; never log it), resolves the `.venv` python + server paths + the `financial.db` path, and renders `studio/mcp/mcp.json` (gitignored — it embeds a secret).
- `runClaude` (the single seam) gains optional `mcpConfigPath` + `allowedTools`. When set, it adds args: `--mcp-config <path>`, `--strict-mcp-config`, and the allowed-tools flag. The arg-array/no-shell invariant is preserved (all still argv elements via the execFile `Spawner`). Exact flag spellings (`--mcp-config`, `--strict-mcp-config`, and `--allowedTools` vs `--allowed-tools`) are verified against the installed `claude` (v2.1.143) `--help` in build step 8 before wiring — this is a verification step, not an assumption.
- **Authoritative allowed-tools set** for the main Eason run (used everywhere this is referenced): exactly the 12 MCP tool ids — `mcp__yt-dlp__ytdlp_search_videos`, `mcp__yt-dlp__ytdlp_download_transcript`, `mcp__twse__get_daily_market_trading_info`, `mcp__twse__get_market_index_info`, `mcp__twse__get_margin_trading_info`, `mcp__twse__get_stock_daily_trading`, `mcp__twse__get_foreign_investment_by_industry`, `mcp__yahoo-finance__get_stock_info`, `mcp__yahoo-finance__get_historical_stock_prices`, `mcp__fred__fred_get_series`, `mcp__sqlite__query`, plus the two sqlite write tools `mcp__sqlite__create_record` and `mcp__sqlite__update_records` — **plus `Write` and `Read`** (so Claude can save the HTML report and read references). NOT `Bash`, NOT `'*'` (the inherited skill used `'*'`; we deliberately scope down). That is 13 MCP tool ids + Write + Read.
- `runPipeline` passes `mcpConfigPath` for the real bin; the fake-CLI path passes nothing (existing tests untouched).

**Secret handling:** `FRED_API_KEY` is read from the inherited `.env` (already gitignored), injected only into the `fred` server's process env via the rendered `mcp.json`; `mcp.json` is added to `.gitignore`; the key is never written to logs, run.json, or commits. Notify secrets in `.env` are never read.

## 3. The Known Deterministic Gaps — fixes (part of this phase)

| Gap | Fix |
|---|---|
| `main.md`/`picks.md` contain literal `${HTML_FILE}` `${DATE}` `${LOG_FILE}` | `buildPrompt` substitutes them: `${HTML_FILE}`→ the run's `report.html` absolute path, `${DATE}`→ `calendarFacts().iso`, `${LOG_FILE}`→ the run's `claude.log` path. Add `htmlPath`/`logPath`/`dateIso` to `BuildPromptArgs`. Golden test updated. |
| `main.md` references WSL path `/mnt/c/FINANCIAL/reports/2026-03-25_*.html` for CSS | Bundle `studio/prompts/eason/report.css` (extracted from `financial-report-system/samples/eason-sample.html`); replace the WSL reference in `main.md` with the literal CSS inlined via a new `{{report_css}}` placeholder `buildPrompt` fills from that file. |
| Claude must be allowed to write the HTML | `--allowed-tools` includes `Write`; prompt already says "儲存到 ${HTML_FILE}" (now a real path). |
| `mechanicalChecks` never invoked | `runPipeline` runs it on the produced HTML after `runClaude`: records `qualityOk: boolean` + `qualityFailures: string[]` on the run record. **It does NOT change `status`** — a produced report with weak quality is still `succeeded` (quality is advisory; LLM-judge + human are the other layers per v1 §5). Fake-CLI e2e test asserts `status==="succeeded"` and `qualityOk===false` (fixture HTML lacks sections) — no test breakage. |
| `postProcess` PDF uses `"google-chrome"` (not on macOS PATH) | `postProcess` resolves a chrome binary: try `google-chrome`, then `google-chrome-stable`, then the macOS app path `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; if none, `pdfOk=false` (non-fatal, already designed). Spawner arg-array unchanged. |
| `STUDIO_ROOT = process.cwd()` fragile | Replace with module-relative resolution: `fileURLToPath(new URL("../../", import.meta.url))` in `paths.ts`. |
| sqlite DB / schema may be absent | `sqlite_server.py` ensures the DB exists; if the 3 eason tables are missing it applies `financial-report-system/db/schema.sql`. DB path defaults to `financial-report-system/data/financial.db`, overridable via env in `mcp.json`. |

## 4. Subtitle Fallback — local `gemma4:e4b` via Ollama

Inside `ytdlp_download_transcript(language)`:

1. Try existing captions via `yt-dlp` (`--write-subs`/`--write-auto-subs`, language order `zh-Hant → zh → en` as the skill specifies; also accept `zh-TW`). If found, return that text (cheapest path, unchanged from inherited behaviour).
2. If none: `yt-dlp -f bestaudio` (audio only, no full video download) → `ffmpeg` normalises to a mono 16 kHz file → **split into ~3–5 minute chunks** (finance videos run 20–60 min; a single blob exceeds practical local-model input) → each chunk sent to local **`gemma4:e4b`** (Gemma 3n E4B, audio-capable) through the already-running **Ollama** with a fixed "transcribe this Mandarin audio verbatim, output plain text only" instruction → chunk texts concatenated in order. Return plain transcript text (same shape as the captions path, so the inherited skill is agnostic to which path produced it).
3. Config: model id default `gemma4:e4b`, chunk length, and Ollama host overridable via env (`STUDIO_TRANSCRIBE_MODEL`, `STUDIO_TRANSCRIBE_CHUNK_SEC`, `OLLAMA_HOST`). Defaults chosen so it works with zero config on this machine.
4. **Verify-before-rely:** the build step does NOT trust this blindly — it runs `gemma4:e4b` on a deliberately caption-less Mandarin short clip and confirms a non-empty, plausibly-correct zh transcript before the fallback is wired into the live path. If `gemma4:e4b` audio output proves unusable, the documented contingency is faster-whisper (NOT built now — see §6/§7).
5. Dependencies: `yt-dlp` (2026.03.17, present), `ffmpeg` (8.0.1, present), Ollama with `gemma4:e4b` (present, 9.6 GB). The user's repo's Gemini-video cloud last-resort is **excluded** (needs a cloud key; out of scope).

## 5. Verification Strategy (self-verified; only subjective quality escalates)

Per project memory `feedback_self_verification_first`. Each piece is self-tested before its commit:

- **Per MCP server smoke tests** (real calls, recorded in the slice's commit): FRED real key → `T10Y2Y` latest value; TWSE → `get_daily_market_trading_info` returns today/last-session data; Yahoo → `get_stock_info("2330.TW")` returns a price + P/E; yt-dlp → `ytdlp_search_videos("張貽程 外資超錢線", 1, "week")` returns a video; transcript on a known-captioned short video; **gemma4:e4b fallback** on a deliberately caption-less Mandarin short clip yields a non-empty, plausibly-correct zh transcript; sqlite → temp DB query/create/update round-trip + schema auto-init.
- **Contract tests:** each tool's name + return keys match what the inherited prompt consumes (table in §1). A TS test asserts the rendered `mcp.json` registers exactly the 5 servers and that the allowed-tools list is exactly the 13 MCP tool ids + `Write` + `Read` (the authoritative set in §2).
- **End-to-end real run:** `runPipeline("eason")` with the real `claude` + real `mcp.json`. Self-checks I run and read myself: report HTML exists at the run path; `mechanicalChecks` result; structural diff vs `financial-report-system/samples/eason-sample.html` (sections, signal blocks, picks table well-formed); calendar facts correct; no >7-day-old or future-dated news.
- **Escalate to user only:** the subjective "is this Eason analysis genuinely insightful / does it match his style" judgment — presented with the rendered report for their call.

## 6. Out of Scope (explicit YAGNI)

Messaging (Discord/LINE/Telegram) and `notify.sh` reuse; the ReactFlow node canvas; the other inherited pipelines (游庭皓 briefing, stock-news); `chart` MCP; multi-tenant/hosted/sellable concerns; auto-scheduling/cron from the UI; perfecting Yahoo/TWSE beyond what the Eason ticker set needs; **faster-whisper** (kept only as a documented contingency if `gemma4:e4b` audio transcription proves unusable in step 7 — not built in this phase).

## 7. Risks

- **Yahoo public endpoints** drift; `yfinance` mitigates but a ticker (e.g. `DX-Y.NYB`, `BZ=F`) may intermittently fail → servers return a structured `{error}` the prompt can tolerate (skill already proceeds data-partial).
- **gemma4:e4b audio quality/latency** on long Mandarin finance monologue is the biggest unknown: mitigated by audio-only extraction + ~3–5 min chunking, and gated by the step-7 verify-before-rely check. If output is poor → faster-whisper contingency (§6). Captioned videos (the common case) never hit this path.
- **TWSE Open API** shapes per-endpoint; we implement exactly the 5 tools' fields the prompt reads, not the whole API.
- **Tool-name fidelity:** the inherited prompt uses bare names (`ytdlp_search_videos`); under MCP these surface as `mcp__yt-dlp__ytdlp_search_videos`. If the skill text's bare names don't auto-resolve, `buildPrompt` will additionally inject an explicit tool-name map note. (Validated during the contract test before the real run.)

## 8. Build Sequence (feeds the implementation plan)

1. `studio/mcp/` Python scaffold (`.venv`, `requirements.txt`, gitignore, `mcp.json.tmpl`).
2. `sqlite_server.py` + schema auto-init + tests.
3. `fred_server.py` (key from `.env`) + real smoke.
4. `twse_server.py` (5 tools) + real smoke.
5. `yahoo_server.py` (2 tools) + real smoke.
6. `ytdlp_server.py` search+transcript (captions only) + real smoke.
7. `gemma_transcribe.py` (yt-dlp audio → ffmpeg → chunk → `gemma4:e4b` via Ollama → stitch) + integrate into the transcript tool + verify-before-rely caption-less Mandarin smoke.
8. `mcpConfig.ts` (render `mcp.json`, read FRED key) + `runClaude` `--mcp-config/--allowed-tools` + contract test.
9. `buildPrompt` placeholder substitution + bundled `report.css` + golden test update.
10. `runPipeline` mechanicalChecks wiring + chrome-path resolution + `STUDIO_ROOT` fix.
11. Real end-to-end Eason run; capture evidence; escalate only the subjective quality call.

Each step is an independently committed/pushed slice with recorded self-verification, on `main`, per the established workflow.
