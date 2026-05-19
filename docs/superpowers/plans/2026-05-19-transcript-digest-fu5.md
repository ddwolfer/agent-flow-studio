# Transcript Digest Pass (FU-5, option C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Eason transcript's *substance* (stance, stock picks, 5-layer logic, risks, verbatim quotes) actually reach the analysis, by adding a dedicated Sonnet "digest pass" that pages the full transcript and writes a small structured digest file the main analysis pass then reads.

**Architecture:** Two-pass orchestration inside `runPipeline`. **Pass 1 (digest):** a dedicated `claude -p` run (model = `claude-sonnet-4-6`, tools reduced to yt-dlp + Write + Read) finds today's video(s), pages the *full untruncated* cleaned transcript via a new `ytdlp_transcript_page` tool (each tool result stays small, defeating the prior oversized-single-result failure), and writes a faithful structured digest to `runs/<id>/transcript-digest.md`. **Pass 2 (analysis):** the existing main run, but `transcript.md` now instructs it to `Read` the small digest file and never call yt-dlp. The huge transcript never has to fit in one tool result that a multi-tasking model must re-consume.

**Tech Stack:** Python FastMCP (yt-dlp server), TypeScript/Next.js runner, Vitest, pytest. ESM. `claude -p` via the single `Spawner`/`runClaude` seam (no new claude-invocation sites).

**Why this design (context for the engineer):** FU-4 returned the cleaned transcript inline; it was 59k chars, exceeded the 48k cap, got head/tail-elided, and the main model — juggling a 9-section report — treated the elided blob as unreadable and fell back to data-only analysis (no picks, no quotes). Root causes: (a) truncation destroyed contiguous quotes, (b) one ~50k-char tool result is past what a multi-tasking model reliably consumes. This plan fixes both: full transcript delivered in small pages to a model whose *sole* job is to digest it, then a tiny faithful digest handed to the analysis.

---

## File Structure

- `studio/mcp/servers/ytdlp_server.py` — **modify**: add in-process per-video cleaned-transcript cache + `ytdlp_transcript_page` tool. `ytdlp_download_transcript` left unchanged (back-compat).
- `studio/mcp/tests/test_ytdlp_server.py` — **modify**: add paging tests.
- `studio/prompts/eason/digest.md` — **create**: Pass-1 instructions + strict faithful digest schema.
- `studio/prompts/eason/transcript.md` — **rewrite**: Pass-2 reads the digest file; must not call yt-dlp.
- `studio/lib/config/schema.ts` — **modify**: optional `digest:{model,prompt}` on `PipelineFile`.
- `studio/lib/config/load.ts` — **modify**: load `digestPrompt` text when configured.
- `studio/config/pipelines/eason.yaml` — **modify**: add `digest:` block.
- `studio/lib/runner/buildPrompt.ts` — **modify**: add `${TRANSCRIPT_DIGEST}` substitution.
- `studio/lib/runner/allowedTools.ts` — **create**: canonical `EASON_ALLOWED_TOOLS` + `digestAllowedTools()` (removes the ad-hoc/uncommitted allowlist drift; digest pass derives its reduced list here).
- `studio/lib/runner/digestPass.ts` — **create**: builds the digest prompt, runs it via `runClaude`, asserts a usable digest file was produced.
- `studio/lib/runner/runPipeline.ts` — **modify**: run the digest pass before the main run (stage `"digest"`), skip it under fake-claude, thread the digest path into the main `buildPrompt`.
- corresponding `.test.ts` files — **create/modify** as listed per task.

---

### Task 1: yt-dlp paged transcript tool

**Files:**
- Modify: `studio/mcp/servers/ytdlp_server.py`
- Test: `studio/mcp/tests/test_ytdlp_server.py`

- [ ] **Step 1: Write the failing tests** — append to `studio/mcp/tests/test_ytdlp_server.py`:

```python
# ── ytdlp_transcript_page paging tests ────────────────────────────────────────

def test_transcript_page_math_and_slicing():
    m = _load()
    original_fetch = m._fetch_captions
    # 5000 unique chars after cleaning (no VTT markup so cleaning is a no-op-ish)
    m._fetch_captions = lambda *a, **kw: "X" * 5000
    m._TRANSCRIPT_CACHE.clear()
    try:
        p0 = m.ytdlp_transcript_page("https://youtu.be/vid1", page=0, page_size=2000)
        assert p0["source"] == "captions"
        assert p0["full_chars"] == 5000
        assert p0["total_pages"] == 3          # ceil(5000/2000)
        assert p0["page"] == 0
        assert len(p0["text"]) == 2000
        p2 = m.ytdlp_transcript_page("https://youtu.be/vid1", page=2, page_size=2000)
        assert len(p2["text"]) == 1000         # remainder
        # out-of-range page → empty text, no crash
        p9 = m.ytdlp_transcript_page("https://youtu.be/vid1", page=9, page_size=2000)
        assert p9["text"] == ""
        assert p9["total_pages"] == 3
    finally:
        m._fetch_captions = original_fetch
        m._TRANSCRIPT_CACHE.clear()

def test_transcript_page_caches_after_first_fetch():
    m = _load()
    calls = {"n": 0}
    def fake_fetch(*a, **kw):
        calls["n"] += 1
        return "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n台股大漲\n"
    m._fetch_captions = fake_fetch
    m._TRANSCRIPT_CACHE.clear()
    try:
        m.ytdlp_transcript_page("https://youtu.be/c1", page=0, page_size=10)
        m.ytdlp_transcript_page("https://youtu.be/c1", page=1, page_size=10)
        assert calls["n"] == 1                 # fetched once, paged from cache
    finally:
        m._TRANSCRIPT_CACHE.clear()

def test_transcript_page_none_source_shape():
    m = _load()
    m._fetch_captions = lambda *a, **kw: None
    g = m._gemma; m._gemma = None
    m._TRANSCRIPT_CACHE.clear()
    try:
        r = m.ytdlp_transcript_page("https://youtu.be/none1", page=0, page_size=100)
        assert r["source"] == "none"
        assert r["text"] == ""
        assert r["full_chars"] == 0
        assert r["total_pages"] == 0
    finally:
        m._gemma = g
        m._TRANSCRIPT_CACHE.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio && .venv/bin/python -m pytest mcp/tests/test_ytdlp_server.py -k transcript_page -v`
Expected: FAIL (`module has no attribute '_TRANSCRIPT_CACHE'` / `ytdlp_transcript_page`).

- [ ] **Step 3: Implement the cache + paged tool** in `studio/mcp/servers/ytdlp_server.py`.

Add the cache near the top (after `_HEAD_RATIO = 0.60`):

```python
# video_url -> {"source": str, "text": str}  (full cleaned text, NOT truncated)
_TRANSCRIPT_CACHE: dict[str, dict] = {}


def _get_full_transcript(video_url: str, language: str = "zh-Hant") -> dict:
    """Fetch + clean the FULL transcript once per video_url (cached). No truncation.

    Returns {"source": "captions"|"gemma4:e4b"|"none", "text": str}.
    """
    cached = _TRANSCRIPT_CACHE.get(video_url)
    if cached is not None:
        return cached
    result = {"source": "none", "text": ""}
    try:
        raw = _fetch_captions(video_url, [language, "zh-TW", "zh-Hant", "zh", "en"])
        if raw:
            result = {"source": "captions", "text": _clean_transcript(raw)}
        elif _gemma is not None:
            t = _gemma.transcribe(video_url)
            if t and t.strip():
                result = {"source": "gemma4:e4b", "text": _clean_transcript(t)}
    except Exception as e:
        result = {"source": "none", "text": "", "error": f"transcript failed: {e}"}
    _TRANSCRIPT_CACHE[video_url] = result
    return result
```

Add the tool (after `ytdlp_download_transcript`, before `if __name__`):

```python
@mcp.tool()
def ytdlp_transcript_page(video_url: str, page: int = 0,
                          page_size: int = 12000, language: str = "zh-Hant"):
    """
    Return ONE page of the FULL cleaned transcript (no head/tail elision).

    The full transcript is fetched+cleaned once per video_url and cached, so
    paging through it is cheap. Each page is small enough for a single MCP
    tool result. Page through 0..total_pages-1 to read the entire transcript.

    Result: {source, page, total_pages, full_chars, text}
      - source: "captions" | "gemma4:e4b" | "none"
      - total_pages: number of pages of size page_size (0 if no transcript)
      - full_chars: length of the full cleaned transcript
      - text: the requested page slice ("" if page is out of range)
    Never raises; on failure returns source="none", text="", total_pages=0.
    """
    info = _get_full_transcript(video_url, language)
    text = info.get("text") or ""
    full = len(text)
    size = max(int(page_size), 1)
    total = (full + size - 1) // size if full else 0
    start = max(int(page), 0) * size
    slice_ = text[start:start + size] if 0 <= start < full else ""
    out = {"source": info.get("source", "none"), "page": int(page),
           "total_pages": total, "full_chars": full, "text": slice_}
    if "error" in info:
        out["error"] = info["error"]
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd studio && .venv/bin/python -m pytest mcp/tests/test_ytdlp_server.py -v`
Expected: PASS (all prior tests + the 3 new paging tests).

- [ ] **Step 5: Commit + push**

```bash
git add studio/mcp/servers/ytdlp_server.py studio/mcp/tests/test_ytdlp_server.py
git commit -m "feat(mcp): ytdlp_transcript_page — full transcript in small cached pages (FU-5)"
git push origin main
```

---

### Task 2: digest + analysis prompts

**Files:**
- Create: `studio/prompts/eason/digest.md`
- Rewrite: `studio/prompts/eason/transcript.md`

No automated test (prompt text). Verification is the FU-5 confirming run (Task 6).

- [ ] **Step 1: Create `studio/prompts/eason/digest.md`** with exactly this content:

```markdown
# 逐字稿濃縮任務（前置步驟，務必完成並寫檔）

你這一輪的**唯一任務**：把 Eason 今日影片的完整逐字稿，濃縮成一份忠實、結構化的摘要，**用 `Write` 工具寫入檔案**：

```
${TRANSCRIPT_DIGEST}
```

## 步驟

1. 用 `mcp__yt-dlp__ytdlp_search_videos(query="{{channel.search_query}}", maxResults=2, uploadDateFilter="today")` 找出今日影片。若今日無新片，改用最近一支。
2. 對每支影片，從 `page=0` 開始呼叫
   `mcp__yt-dlp__ytdlp_transcript_page(video_url="<url>", page=<n>, page_size=12000)`，
   讀取回傳的 `total_pages`，**逐頁呼叫到 `page == total_pages-1`**，把每頁 `text` 在心中**完整串接**成整份逐字稿。不可只看第一頁就下結論。
3. 依下方schema寫出摘要，用 `Write` 寫入 `${TRANSCRIPT_DIGEST}`（單一檔案；多支影片就在同一檔案內分節）。

## 摘要 schema（嚴格照寫）

```
# 逐字稿摘要（{{calendar}}）

## 影片清單
- 標題 ｜ video_id ｜ url ｜ 逐字稿來源(captions/gemma4:e4b/none) ｜ 完整字元數

## Eason 總體市場立場
（看多／看空／中性 + 1–2 句理由，僅依逐字稿）

## 選股清單
| 標的名稱 | 代號 | 方向(看多/看空/觀望) | Eason 理由(濃縮) |
（只列 Eason 在逐字稿中**明確**點到的個股；沒講代號就留空；不確定就不要列）

## 五層邏輯鏈要點
1. 宏觀／資金面：(2–4 條 bullet)
2. 產業／族群：(2–4 條)
3. 個股：(2–4 條)
4. 風險：(2–4 條)
5. 操作／選股方向：(2–4 條)

## 風險提示
- （Eason 實際提到的風險，逐條）

## 關鍵原話逐字引用（供報告「今日語錄」使用）
> 「（從逐字稿原文**逐字複製**，不可改寫、不可翻譯、不可潤飾）」
（5–10 句 Eason 原話）
```

## 忠實度鐵則（違反即任務失敗）

- 只能萃取逐字稿**真實出現**的內容。**嚴禁**臆測、補充、或「合理推論」逐字稿沒講的數字、個股、結論。
- 不確定 → 省略，不要硬填。寧缺勿假。
- 「關鍵原話逐字引用」必須是逐字稿原文的逐字片段，一字不改。
- 即使逐字稿 `source` 為 `none` 或抓不到內容，**仍要 `Write` 出這個檔案**：在「影片清單」標註「逐字稿不可用」，其餘各節寫「（逐字稿不可用）」。

## 限制

- 本輪只允許 `mcp__yt-dlp__*` 與 `Write`、`Read` 工具。**禁止** Bash、其他 MCP、產生報告或 HTML。
- 完成 `Write` 後即結束，不要做任何其他事。
```

- [ ] **Step 2: Rewrite `studio/prompts/eason/transcript.md`** to exactly:

```markdown
# 逐字稿取得規則（重要：請嚴格遵守）

逐字稿的**精華摘要已由前置步驟產生並存檔**。你**不需要也禁止**自己下載逐字稿。

## 唯一正確做法

用 `Read` 工具讀取這個檔案：

```
${TRANSCRIPT_DIGEST}
```

該檔案是一份忠實的結構化摘要，**即為本次分析的逐字稿依據**：

| 摘要區塊 | 用途 |
|----------|------|
| Eason 總體市場立場 | 報告的整體偏多/偏空判斷 |
| 選股清單 | 第五層「選股方向」與 `eason_picks` 寫入來源 |
| 五層邏輯鏈要點 | 五層邏輯鏈分析的骨幹 |
| 風險提示 | 報告「風險提示」段落 |
| 關鍵原話逐字引用 | 報告「今日語錄」段落，**必須逐字使用，不可改寫** |

## 絕對禁止事項

- **禁止**呼叫任何 `mcp__yt-dlp__*` 工具或自行下載逐字稿。
- **禁止**用 Bash／python／shell 讀取任何 `.vtt`/`.srt`/`.txt`。
- **禁止**因「逐字稿無法讀取」而降低信心值——摘要檔案即是全部所需。

## 摘要不可用時

只有當 `${TRANSCRIPT_DIGEST}` 的「影片清單」標註「逐字稿不可用」時，才退回「僅依影片標題＋市場數據」分析，並在報告中明確標示信心值降低。否則必須充分使用摘要內容，產出完整的五層邏輯鏈、選股、今日語錄、風險提示、報告總結。
```

- [ ] **Step 3: Commit + push**

```bash
git add studio/prompts/eason/digest.md studio/prompts/eason/transcript.md
git commit -m "feat(prompts): digest-pass prompt + analysis reads digest file, not yt-dlp (FU-5)"
git push origin main
```

---

### Task 3: config schema + eason.yaml + buildPrompt substitution

**Files:**
- Modify: `studio/lib/config/schema.ts`
- Modify: `studio/lib/config/load.ts`
- Modify: `studio/config/pipelines/eason.yaml`
- Modify: `studio/lib/runner/buildPrompt.ts`
- Test: `studio/lib/config/load.test.ts`, `studio/lib/runner/buildPrompt.test.ts`

- [ ] **Step 1: Write failing tests.**

Append to `studio/lib/runner/buildPrompt.test.ts`:

```ts
it("substitutes ${TRANSCRIPT_DIGEST} with the digest path", () => {
  const out = buildPrompt({
    promptTemplate: "read ${TRANSCRIPT_DIGEST} now",
    references: [], channel: {
      id: "eason", handle: "@x", name: "X", search_query: "q",
      pipeline: "eason", enabled: true,
    },
    calendarText: "CAL", transcriptDigestPath: "/runs/abc/transcript-digest.md",
  });
  expect(out).toContain("read /runs/abc/transcript-digest.md now");
});

it("substitutes ${TRANSCRIPT_DIGEST} with empty string when absent", () => {
  const out = buildPrompt({
    promptTemplate: "x${TRANSCRIPT_DIGEST}y", references: [],
    channel: { id: "eason", handle: "@x", name: "X", search_query: "q",
      pipeline: "eason", enabled: true },
    calendarText: "CAL",
  });
  expect(out).toContain("xy");
});
```

Append to `studio/lib/config/load.test.ts` (follow the file's existing load pattern; this asserts the optional digest prompt is loaded for eason):

```ts
it("loads digestPrompt text when pipeline.digest is configured", async () => {
  const cfg = await loadConfig("eason", STUDIO_ROOT_FOR_TESTS);
  expect(cfg.pipeline.digest?.model).toBe("claude-sonnet-4-6");
  expect(typeof cfg.digestPrompt).toBe("string");
  expect(cfg.digestPrompt!.length).toBeGreaterThan(0);
});
```

> Note: reuse the same `STUDIO_ROOT` constant the other `load.test.ts` cases use (e.g. `new URL("../../", import.meta.url).pathname`). Match the existing test's exact symbol name.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio && npx vitest run lib/runner/buildPrompt.test.ts lib/config/load.test.ts`
Expected: FAIL (`transcriptDigestPath` not a known prop; `digest` not on schema; `digestPrompt` undefined).

- [ ] **Step 3: Implement.**

`schema.ts` — add to the `PipelineFile` object (after `post:` block, before `quality_judge:`):

```ts
  digest: z.object({
    model: z.string().min(1),
    prompt: z.string().min(1),
  }).optional(),
```

`load.ts` — add `digestPrompt?: string;` to the `LoadedConfig` interface, and before the `return`:

```ts
  const digestPrompt = pipeline.digest
    ? await readText(join(studioRoot, pipeline.digest.prompt))
    : undefined;
```

then add `digestPrompt` to the returned object.

`config/pipelines/eason.yaml` — add this block immediately after the `post:` block (sibling key, same indentation as `post:`):

```yaml
digest:
  model: claude-sonnet-4-6
  prompt: prompts/eason/digest.md
```

`buildPrompt.ts` — add `transcriptDigestPath?: string;` to `BuildPromptArgs`, and add one more `.replaceAll` in the chain:

```ts
    .replaceAll("${TRANSCRIPT_DIGEST}", a.transcriptDigestPath ?? "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd studio && npx vitest run lib/runner/buildPrompt.test.ts lib/config/load.test.ts && npx tsc --noEmit`
Expected: PASS, tsc clean.

- [ ] **Step 5: Commit + push**

```bash
git add studio/lib/config/schema.ts studio/lib/config/load.ts studio/config/pipelines/eason.yaml studio/lib/runner/buildPrompt.ts studio/lib/runner/buildPrompt.test.ts studio/lib/config/load.test.ts
git commit -m "feat(config): optional pipeline.digest + \${TRANSCRIPT_DIGEST} substitution (FU-5)"
git push origin main
```

---

### Task 4: allowedTools module + digestPass + two-pass runPipeline

**Files:**
- Create: `studio/lib/runner/allowedTools.ts`
- Create: `studio/lib/runner/digestPass.ts`
- Modify: `studio/lib/runner/runPipeline.ts`
- Test: `studio/lib/runner/allowedTools.test.ts`, `studio/lib/runner/digestPass.test.ts`, `studio/lib/runner/runPipeline.test.ts`

- [ ] **Step 1: Write failing tests.**

Create `studio/lib/runner/allowedTools.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { EASON_ALLOWED_TOOLS, digestAllowedTools } from "./allowedTools";

describe("allowedTools", () => {
  it("EASON_ALLOWED_TOOLS includes the paged transcript tool, Write and Read", () => {
    expect(EASON_ALLOWED_TOOLS).toContain("mcp__yt-dlp__ytdlp_transcript_page");
    expect(EASON_ALLOWED_TOOLS).toContain("Write");
    expect(EASON_ALLOWED_TOOLS).toContain("Read");
  });
  it("digestAllowedTools keeps only yt-dlp tools + Write + Read", () => {
    const r = digestAllowedTools([
      "mcp__yt-dlp__ytdlp_search_videos", "mcp__sqlite__query",
      "mcp__fred__fred_get_series", "Write", "Read", "Bash",
    ]);
    expect(r).toEqual([
      "mcp__yt-dlp__ytdlp_search_videos", "Write", "Read",
    ]);
  });
  it("digestAllowedTools falls back to the yt-dlp subset of EASON_ALLOWED_TOOLS when given nothing", () => {
    const r = digestAllowedTools(undefined);
    expect(r).toContain("mcp__yt-dlp__ytdlp_transcript_page");
    expect(r).toContain("Write");
    expect(r.some((t) => t.startsWith("mcp__sqlite__"))).toBe(false);
  });
});
```

Create `studio/lib/runner/digestPass.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, writeFile, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { digestPass } from "./digestPass";

let runDir: string;
beforeEach(async () => {
  runDir = await mkdtemp(join(tmpdir(), "dp-"));
});

const baseChannel = {
  id: "eason", handle: "@x", name: "X", search_query: "q",
  pipeline: "eason", enabled: true,
};

describe("digestPass", () => {
  it("resolves when the digest file is produced", async () => {
    const digestPath = join(runDir, "transcript-digest.md");
    await digestPass({
      digestPromptTemplate: "make digest at ${TRANSCRIPT_DIGEST}",
      channel: baseChannel, calendarText: "CAL", dateIso: "2026-05-19",
      digestPath, model: "claude-sonnet-4-6", maxTurns: 20,
      cwd: runDir, claudeBin: "claude",
      spawner: async () => {
        await writeFile(digestPath, "# 逐字稿摘要\n".padEnd(400, "x"));
        return { code: 0 };
      },
      logPath: join(runDir, "digest.log"),
    });
  });

  it("throws ClaudeRunError when no usable digest file is produced", async () => {
    const digestPath = join(runDir, "transcript-digest.md");
    await expect(digestPass({
      digestPromptTemplate: "x", channel: baseChannel, calendarText: "C",
      dateIso: "2026-05-19", digestPath, model: "m", maxTurns: 5,
      cwd: runDir, claudeBin: "claude",
      spawner: async () => ({ code: 0 }),    // writes nothing
      logPath: join(runDir, "digest.log"),
    })).rejects.toThrow(/digest/i);
  });

  it("passes a reduced (yt-dlp + Write + Read) allowedTools list to claude", async () => {
    const digestPath = join(runDir, "transcript-digest.md");
    let seenTools = "";
    await digestPass({
      digestPromptTemplate: "d ${TRANSCRIPT_DIGEST}", channel: baseChannel,
      calendarText: "C", dateIso: "2026-05-19", digestPath,
      model: "claude-sonnet-4-6", maxTurns: 10, cwd: runDir, claudeBin: "claude",
      allowedTools: ["mcp__yt-dlp__ytdlp_transcript_page", "mcp__sqlite__query", "Write", "Read"],
      spawner: async (_f, args) => {
        const i = args.indexOf("--allowedTools");
        seenTools = i >= 0 ? args[i + 1]! : "";
        await writeFile(digestPath, "x".padEnd(400, "x"));
        return { code: 0 };
      },
      logPath: join(runDir, "digest.log"),
    });
    expect(seenTools).toContain("mcp__yt-dlp__ytdlp_transcript_page");
    expect(seenTools).not.toContain("mcp__sqlite__query");
  });
});
```

Append to `studio/lib/runner/runPipeline.test.ts`:

```ts
  it("skips the digest pass under the fake CLI and still succeeds", async () => {
    let nonFakeCalls = 0;
    const r = await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) => {
        if (file.endsWith("fake-claude.sh")) return spawnProc(file, args, opts);
        nonFakeCalls++; return { code: 0 };
      },
    });
    expect(r.status).toBe("succeeded");
    // digest pass would have been an extra non-fake claude call; it must be skipped
    const { readdir } = await import("node:fs/promises");
    const runDirs = await readdir(runsRoot);
    expect(runDirs).toHaveLength(1);
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd studio && npx vitest run lib/runner/allowedTools.test.ts lib/runner/digestPass.test.ts`
Expected: FAIL (modules do not exist).

- [ ] **Step 3: Implement `studio/lib/runner/allowedTools.ts`:**

```ts
// Canonical Eason tool allowlist. The real-run launcher and the digest pass
// derive from here so the security-critical list lives in one committed place.
export const EASON_ALLOWED_TOOLS: readonly string[] = [
  "mcp__yt-dlp__ytdlp_search_videos",
  "mcp__yt-dlp__ytdlp_download_transcript",
  "mcp__yt-dlp__ytdlp_transcript_page",
  "mcp__twse__twse_fmtqik",
  "mcp__twse__twse_mi_index",
  "mcp__twse__twse_mi_margn",
  "mcp__twse__twse_stock_day_all",
  "mcp__twse__twse_mi_qfiis_cat",
  "mcp__yahoo-finance__yahoo_quote",
  "mcp__fred__fred_get_series",
  "mcp__sqlite__query",
  "mcp__sqlite__create_record",
  "mcp__sqlite__update_records",
  "Write",
  "Read",
];

/** Reduce a full allowlist to what the digest pass may use:
 *  yt-dlp tools + Write + Read only. Falls back to the yt-dlp subset of
 *  EASON_ALLOWED_TOOLS when no list is supplied. Order is preserved. */
export function digestAllowedTools(all?: readonly string[]): string[] {
  const keep = (t: string) =>
    t.startsWith("mcp__yt-dlp__") || t === "Write" || t === "Read";
  const src = all && all.length ? all : EASON_ALLOWED_TOOLS;
  return src.filter(keep);
}
```

> If the actual MCP tool ids in your real-run launcher differ, treat the launcher as the source of truth and reconcile this constant to it in Task 6 — `digestAllowedTools` is intentionally launcher-agnostic (it filters whatever it's given), so the runtime path is correct regardless.

- [ ] **Step 4: Implement `studio/lib/runner/digestPass.ts`:**

```ts
import { stat } from "node:fs/promises";
import type { Channel } from "../config/schema";
import type { Spawner } from "./spawnProc";
import { buildPrompt } from "./buildPrompt";
import { runClaude } from "./runClaude";
import { digestAllowedTools } from "./allowedTools";
import { ClaudeRunError } from "./errors";

const MIN_DIGEST_BYTES = 200;

export interface DigestPassArgs {
  digestPromptTemplate: string;
  channel: Channel;
  calendarText: string;
  dateIso: string;
  digestPath: string;            // runs/<id>/transcript-digest.md
  model: string;
  maxTurns: number;
  cwd: string;
  claudeBin?: string;
  spawner: Spawner;
  mcpConfigPath?: string;
  allowedTools?: string[];       // full list; reduced to yt-dlp + Write + Read
  logPath: string;               // runs/<id>/digest.log
}

export async function digestPass(a: DigestPassArgs): Promise<void> {
  const prompt = buildPrompt({
    promptTemplate: a.digestPromptTemplate,
    references: [],
    channel: a.channel,
    calendarText: a.calendarText,
    dateIso: a.dateIso,
    transcriptDigestPath: a.digestPath,
  });
  await runClaude({
    prompt,
    model: a.model,
    maxTurns: a.maxTurns,
    cwd: a.cwd,
    htmlOut: a.digestPath,        // unused by digest; runClaude just echoes it back
    claudeBin: a.claudeBin,
    spawner: a.spawner,
    mcpConfigPath: a.mcpConfigPath,
    allowedTools: digestAllowedTools(a.allowedTools),
    logPath: a.logPath,
  });
  let size = 0;
  try { size = (await stat(a.digestPath)).size; } catch { size = 0; }
  if (size < MIN_DIGEST_BYTES) {
    throw new ClaudeRunError(
      `digest pass produced no usable digest (${size} bytes at ${a.digestPath})`);
  }
}
```

- [ ] **Step 5: Wire the two-pass flow into `studio/lib/runner/runPipeline.ts`.**

Add imports:

```ts
import { digestPass } from "./digestPass";
```

Replace the body between `const claudeLogPath = ...` and the `const cr = await runClaude({...})` call so it (a) computes the digest path, (b) tracks the failing stage, (c) runs the digest pass unless under fake-claude or `digest` is unconfigured, (d) threads the digest path into the main prompt. Concretely:

- After `const claudeLogPath = join(o.runsRoot, runId, "claude.log");` add:

```ts
  const digestPath = join(o.runsRoot, runId, "transcript-digest.md");
  const digestLogPath = join(o.runsRoot, runId, "digest.log");
  const isFake = !!o.claudeBin?.endsWith("fake-claude.sh");
  let failStage: "loadConfig" | "digest" | "runClaude" | "postProcess" = "runClaude";
```

- Inside the `try`, after `await updateRun(... status: "running" ...)` and `const cal = calendarFacts(...)`, before `buildPrompt`, insert:

```ts
    if (!isFake && cfg.pipeline.digest && cfg.digestPrompt) {
      failStage = "digest";
      await digestPass({
        digestPromptTemplate: cfg.digestPrompt,
        channel: cfg.channel, calendarText: cal.text, dateIso: cal.iso,
        digestPath, model: cfg.pipeline.digest.model,
        maxTurns: cfg.pipeline.max_turns, cwd: financeRoot,
        claudeBin: o.claudeBin, spawner: o.spawner,
        mcpConfigPath: o.mcpConfigPath, allowedTools: o.allowedTools,
        logPath: digestLogPath,
      });
    }
    failStage = "runClaude";
```

- Add `transcriptDigestPath: digestPath,` to the existing main `buildPrompt({ ... })` call.
- In the `catch (e)`, replace the `const stage = ...` line with:

```ts
    const stage = e instanceof ConfigError ? "loadConfig" : failStage;
```

(Keeps loadConfig detection; otherwise uses the tracked stage so a digest failure is recorded as stage `"digest"` with its `claudeLogPath` — note the error record's `claudeLogPath` still points at `claude.log`; that's fine, `digest.log` lives in the same run dir and is discoverable.)

- [ ] **Step 6: Run the full suites**

Run: `cd studio && npx vitest run && npx tsc --noEmit`
Expected: PASS (all existing + new). The existing fake-CLI e2e tests still pass because the digest pass is skipped under `fake-claude.sh`.

Run: `cd studio && .venv/bin/python -m pytest mcp/tests -q`
Expected: PASS.

- [ ] **Step 7: Commit + push**

```bash
git add studio/lib/runner/allowedTools.ts studio/lib/runner/allowedTools.test.ts studio/lib/runner/digestPass.ts studio/lib/runner/digestPass.test.ts studio/lib/runner/runPipeline.ts studio/lib/runner/runPipeline.test.ts
git commit -m "feat(runner): two-pass pipeline — Sonnet digest pass before analysis (FU-5)"
git push origin main
```

---

### Task 5: FU-5 confirming real run + honest evidence

**Files:**
- Modify: `docs/superpowers/plans/PHASE2-EVIDENCE.md`

This task is operational (run by the controller, not a code subagent), mirroring prior FU confirming runs.

- [ ] **Step 1:** Ensure the real-run launcher passes the `digest`-enabled config and an `allowedTools` list that includes `mcp__yt-dlp__ytdlp_transcript_page` (reconcile with `EASON_ALLOWED_TOOLS`). Confirm `mcp.json.tmpl` already registers the yt-dlp server (it does; the new tool is on the same server, no MCP config change needed).

- [ ] **Step 2:** Launch a real `eason` run in the background (same mechanism as prior confirming runs — long-lived background Bash, not a subagent).

- [ ] **Step 3:** When it finishes, verify against ground truth (do NOT gloss):
  - `runs/<id>/transcript-digest.md` exists, is non-trivial, contains a real 選股清單 + 關鍵原話逐字引用 (not "逐字稿不可用" unless captions genuinely failed).
  - `runs/<id>/digest.log` shows paging (`ytdlp_transcript_page` called across multiple pages).
  - `eason_picks` row count **> 0** (the key success signal).
  - `report.html` contains 今日語錄 (verbatim quotes) + 報告總結.
  - `qualityOk` true, or `qualityFailures` materially reduced vs FU-4.
  - confidence/信心值 reflects transcript use, not data-only.

- [ ] **Step 4:** Append a dated **"FU-5 confirming run"** section to `docs/superpowers/plans/PHASE2-EVIDENCE.md` with runId, gitSha, the table of before/after (eason_picks, quality), the decisive digest.log evidence, and an honest verdict (partial/failed/succeeded — no varnish). Commit + push. Record a KG observation on whether the two-pass digest resolved the transcript-not-consumed issue.

---

## Self-Review

**1. Spec coverage** — option C requires: (a) full transcript reaches a digester without the oversized-result failure → Task 1 paged tool + Task 4 digest pass; (b) faithful structured digest small enough for the analysis → Task 2 digest.md schema + faithfulness rules; (c) analysis consumes the digest, not raw transcript → Task 2 transcript.md rewrite + Task 3 `${TRANSCRIPT_DIGEST}` substitution; (d) security seam preserved (single `runClaude`) → Task 4 digestPass uses `runClaude`, no new claude sites; (e) committed allowlist (was ad-hoc) → Task 4 `allowedTools.ts`; (f) honest verification → Task 5. All covered.

**2. Placeholder scan** — no TBD/TODO; all code blocks complete; prompts given verbatim.

**3. Type consistency** — `transcriptDigestPath` used identically in `BuildPromptArgs` (Task 3) and `digestPass`/`runPipeline` (Task 4). `digestPrompt` added to `LoadedConfig` (Task 3) and read in `runPipeline` as `cfg.digestPrompt` (Task 4). `cfg.pipeline.digest.{model,prompt}` schema (Task 3) matches usage (Task 4). `digestAllowedTools` signature consistent across `allowedTools.ts`, its test, and `digestPass.ts`. `failStage` union includes `"digest"`. Fake-claude skip guard matches the existing `FAKE_CLAUDE_OUT` branch condition, keeping current e2e tests green.

**Open risk (flagged, not blocking):** Pass-1 must actually page to the last page rather than stopping at page 0. The digest prompt instructs this explicitly; Task 5 verifies via `digest.log`. If a model still under-pages, the mitigation is a prompt tightening (a follow-up), not a design change.
