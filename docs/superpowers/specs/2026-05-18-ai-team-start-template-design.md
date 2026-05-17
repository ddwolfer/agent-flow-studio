# AI Team Start Template — 設計文件

- 日期：2026-05-18
- 狀態：設計已與使用者逐段確認，待使用者審閱後進入實作計畫

## 1. 目的與問題

使用者每次開小專案都會用到兩個上游工具：

- **knowledgeGraph**（`ChenLiangChong/knowledgeGraph`）：本地 MCP server（Node.js + SQLite + 本地 Qwen3 embedding），給 AI 一個會衰退/成長的長期知識圖譜記憶。位於上游的 `mcp/knowledge-graph/`，需 `npm install`、在 `.mcp.json` 註冊、並在 Claude settings 設 6 個 lifecycle hooks。**未發佈到 npm**。
- **let-them-talk**（`Dekelelz/let-them-talk`）：多 agent 協作的 MCP message broker + dashboard，支援 Claude/Codex/Gemini/Ollama。**是 npm 套件**，以 `npx let-them-talk init [--all|--template team]` 安裝，會寫 `.mcp.json`、`.gemini/settings.json`、`.codex/config.toml`、`AGENTS.md`/`CLAUDE.md` 標記區塊、`.agent-bridge/`。

痛點：每次手動 clone 兩者、刪各自 `.git`、融進專案，再跟 AI 解釋這兩個是什麼。

目標：建立一個可重複使用、**可分享給他人與其他電腦**的起案範本，讓「取得乾淨副本 → 裝好依賴與設定 → 讓 AI 馬上理解兩工具與工作流」一次完成。

## 2. 已確認的決策

| 決策點 | 結論 |
|---|---|
| 上游如何進駐 | **全部 vendor**：KG 原始碼複製進 repo 並 commit；let-them-talk 列為 `package.json` devDependency（鎖版本），由引擎跑其 `init` |
| 起案方式 | `git clone` 本範本成新資料夾 → 刪 `.git` 換新 → 在該目錄開 Claude → 用**專案內 skill** 對話初始化（**就地**，不複製到他處） |
| KG hooks 安裝位置 | 寫進**專案本地** `.claude/settings.json`（隨專案走、不污染全域） |
| 使用型態 | KG **一定裝**；agent team 預設裝、可用 `--no-team` 略過 |
| skill 位置 | **專案內** `.claude/skills/`（跟著 clone 走，非全域） |
| 分享前提的影響 | 「絕對路徑改寫」「跨平台 Node 腳本」「鎖定 let-them-talk 版本」從 nice-to-have 升為**必達需求** |

## 3. 範本 repo 結構

clone 下來、刪 `.git` 後，這個根目錄「就是」新專案：

```
AI_team_start_template/
├── .claude/
│   ├── skills/
│   │   └── init-project/
│   │       └── SKILL.md          # 對話收需求 → 呼叫引擎 → 客製
│   └── settings.json             # KG 6 hooks，專案本地，路徑為佔位符
├── mcp/
│   └── knowledge-graph/          # vendored 上游 KG，.git 已剝除（就地）
├── scripts/
│   ├── initialize.js             # 確定性引擎
│   ├── update-vendor.js          # 之後更新 vendored KG
│   └── smoke-test.js             # 模擬乾淨 clone 的驗證
├── docs/superpowers/specs/       # 設計與計畫文件
├── .mcp.json                     # KG MCP 入口，路徑為佔位符
├── CLAUDE.md                     # 給 AI 的常駐說明（含初始化指引 + 兩工具用途）
├── package.json                  # let-them-talk 鎖版本 devDependency
├── .gitignore
└── README.md
```

設計重點：

- **就地初始化，不複製**。`mcp/knowledge-graph/` 一開始就在最終位置，引擎只負責接線。
- `.mcp.json` 與 `.claude/settings.json` 以 committed 狀態存放時**不含任何真實絕對路徑**，僅含佔位符 `{{PROJECT_ROOT}}`；引擎在初始化當下於該機器替換。這是「可分享」的命脈。
- skill = 對話（容許即興）；引擎 = 機械步驟（不容即興）。兩者嚴格分離以求確定性與可維護。

## 4. 初始化流程

### 4.1 skill 對話收集（`init-project`）

在 clone 下來的目錄開 Claude Code 後叫用 skill，收集：

- 專案名（預設＝資料夾名）
- 是否要 agent team（預設要）→ 要的話選 let-them-talk 模板：`pair`/`team`/`review`/`debate`/`managed`（預設 `team`）
- 接哪些 CLI：`--claude`/`--gemini`/`--codex`/`--all`（預設 `--all`）
- 一句專案描述（烘進 `CLAUDE.md`／`README.md`）
- 是否重置 git

skill 組成單行指令呼叫引擎：

```
node scripts/initialize.js --name "X" --desc "…" --team team --providers all [--no-team] [--reset-git]
```

### 4.2 引擎 `initialize.js` 確定性步驟（就地、依序）

1. **前置檢查**：Node ≥18、npm、git 存在；需 `npx let-them-talk` 時網路或快取可用。缺則明確報錯並中止，不做半套。
2.（選）**重置 git**：`.git` 改名為 `.git.bak-<時間戳>` 再 `git init`（搬移非刪除，可救回）。
3. 根目錄 `npm install`（取得 let-them-talk devDep）。
4. `mcp/knowledge-graph/` 內 `npm install`（KG 自身依賴）。
5. 跑 `npx let-them-talk init --<providers> --template <team>`（除非 `--no-team`）。
6. **合併（易錯點①）**：
   - `.mcp.json`：讀 JSON，將 `knowledge-graph` server 以 key 併入。**順序：先讓 let-them-talk 寫（步驟 5），再併入 KG（本步）**，互不覆蓋、可重跑。
   - `CLAUDE.md`：我方說明置於獨立標記區塊 `<!-- KG-BRIEFING:START -->` … `<!-- KG-BRIEFING:END -->` 以 append/ensure 方式寫入，**永不觸碰** let-them-talk 的區塊。
7. **絕對路徑改寫（易錯點②）**：計算本機 `mcp/knowledge-graph/main.js` 絕對路徑，以及 6 個 hook 腳本絕對路徑，替換 `.mcp.json` 與 `.claude/settings.json` 中的 `{{PROJECT_ROOT}}`。
8. **佔位符替換**：`{{PROJECT_NAME}}`、`{{PROJECT_DESC}}`。
9. **總結輸出**：列出下一步（重啟 Claude Code 載入 MCP/hooks、`node .agent-bridge/launch.js` 開 dashboard）。

### 4.3 冪等性

每個寫入步驟可重跑兩次無副作用：JSON 按 key 併、標記區塊 ensure、佔位符僅在仍為佔位符時替換。half-fail 的復原方式恆為「修好該步後重跑 skill」。

## 5. 錯誤處理

- 失敗要早、清楚、可復原、可重跑（見 4.2 步驟 1、2 與 4.3）。
- 外部步驟（`npm install`、`npx let-them-talk init`）各自檢查 exit code，失敗即停並指出哪步壞、如何接續。
- 合併防呆：`.mcp.json` 非合法 JSON 時中止報錯，**絕不覆蓋寫入**。

## 6. 測試策略

針對核心風險「換台電腦會不會壞」，以 `scripts/smoke-test.js` 模擬一次乾淨 clone：在暫存目錄複製 repo（排除 `.git`）→ 跑 `initialize.js` 測試參數 → 斷言：

1. `.mcp.json` 合法 JSON，且**同時**含 `knowledge-graph` 與 let-them-talk 兩 server。
2. KG server `args` 路徑指向**真實存在**的 `main.js`（絕對路徑可 resolve）—— 專抓分享地雷②。
3. `.claude/settings.json` 合法、6 hooks 在、腳本路徑皆存在。
4. `CLAUDE.md`/`.mcp.json`/`settings.json` **無殘留** `{{佔位符}}`。
5. `CLAUDE.md` 同時含 let-them-talk 區塊與 `KG-BRIEFING` 區塊。
6. 再跑一次 `initialize.js` → 無重複項、檔案不變（冪等性）。

- **跨平台**：至少於 Windows 跑過 smoke-test；純 Node + `path.resolve`，預期 mac/Linux 同樣通過。
- **人工驗收**：init 後在該目錄開 Claude Code，確認 MCP server 載入、let-them-talk dashboard 可開。
- **使用者驗收**：本機完成後，使用者將於另一台 **Mac** 電腦 clone 測試，發現問題回饋後再修。

## 7. 實作期必須驗證的假設（不得當成已知事實）

以下由上游 README 推斷，實作時須對著真實 repo 確認，必要時調整設計：

- KG 內部確切結構：`mcp/knowledge-graph/main.js` 路徑、6 個 hook 腳本的確切檔名與位置、KG 期望的 `.mcp.json` / hooks 設定格式。
- KG vendor 範圍：應 vendor 整個上游 repo 還是僅 `mcp/knowledge-graph/` 子樹。
- `npx let-them-talk init` 的非互動旗標（是否需 `--yes` 等）、其實際寫入哪些檔與 `CLAUDE.md` 標記格式。
- let-them-talk 在 `package.json` 鎖定的確切版本。

## 8. 範圍外（YAGNI）

- 全域 skill / GitHub Template repo / degit：分享前提下已淘汰，不實作。
- 自動更新 vendored KG 的排程：僅提供手動 `update-vendor.js`。
- 非 Claude 平台的 skill 等價物：不在本次範圍。
