"""發文/報告的忠實度檢查 — 把 prompt 規則變成程式擋。

為什麼要有:「不喊單、不預測、不把風險寫成買點」這些規則到目前為止
全靠 prompt 約束模型自制。prompt 是請求,程式是門檻 —— 只要規則重要到
不能破,就該有一道模型繞不過去的檢查。

**核心設計取自 daily_stock_analysis 的 disagreement.py:**
那裡的 `_effective_signal()` 做了一件很聰明的事 —— 風險 agent 若給出
看多訊號,一律強制降級成 hold。**風險只能警告,不能加碼看好。**
這種不對稱寫在程式裡,模型繞不過去。

本模組把同一個不對稱套到文字上:失效位、停損、跌破這類**風險語彙**,
不得與進場、加碼這類**看多行動語彙**出現在同一句。
「跌破 62,715 結構失效」可以;「跌破就是買點」不行。

用法:
    from faithfulness_lint import lint
    violations = lint(text)
    if any(v.severity == "block" for v in violations):
        raise SystemExit("忠實度檢查未通過")

刻意的設計取捨:**寧可漏抓,不可誤擋。** 誤擋會讓當天發不出文,而規則
本身已有 prompt 那一層。所以規則都寫得很窄,並以 reports/binance-square/
_published.jsonl 的歷史貼文當回歸驗證集(全部必須零違規)。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 中文句子切分:句號、驚嘆、問號、分號、換行。逗號不切 —— 不對稱檢查
# 需要看到完整的一句話才有意義。
_SENT_SPLIT = re.compile(r"[。！？!?;；\n]+")


@dataclass(frozen=True)
class Violation:
    rule: str
    severity: str            # "block" | "warn"
    matched: str
    sentence: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.rule}: 「{self.matched}」 — {self.sentence.strip()[:60]}"


# ── 1. 絕對禁語 ─────────────────────────────────────────────────────────────
# 只放沒有任何正當用法的詞。有正當用法的(如「建議」)交給下面的規則處理。
_BANNED = [
    "必漲", "必跌", "保證獲利", "保證賺", "穩賺", "穩賺不賠",
    "閉眼買", "無腦買", "無腦衝", "梭哈", "抄作業", "直接抄",
    "包賺", "躺賺",
]

# 語意隨前綴翻轉的詞,必須用 lookbehind 而非子字串比對。
# 「穩了」= 穩賺的口語(禁);「站穩了 / 守穩了 / 踩穩了」= 守住價位(合規)。
# 這條是拿 51 篇歷史貼文跑回歸時抓出來的唯一誤報,留著當提醒。
_BANNED_CONTEXTUAL = [
    r"(?<!站)(?<!守)(?<!踩)(?<!坐)穩了",
]

# ── 2. 喊單:祈使句式的買賣指令 ──────────────────────────────────────────────
# 用否定前綴排除「非投資建議」「不建議」這類正當用法。
_CALL_TO_ACTION = [
    r"(?<!非投資)(?<!不)建議買入", r"(?<!非投資)(?<!不)建議賣出",
    r"(?<!不)(?<!別)現在就買", r"(?<!不)(?<!別)現在買進",
    r"(?<!不)(?<!別)可以進場", r"(?<!不)(?<!別)快買", r"(?<!不)(?<!別)快賣",
    r"(?<!不)(?<!別)趕快進", r"上車吧", r"跟單",
]

# ── 3. 價格預測 ─────────────────────────────────────────────────────────────
# 「會漲到/看到 X」是預測;「守住 X 才成立」是條件式立場,後者合規。
_PREDICTION = [
    r"(?<!不)(?<!沒)會漲到", r"(?<!不)(?<!沒)會跌到",
    r"(?<!不)(?<!沒)將漲到", r"(?<!不)(?<!沒)將跌到",
    r"目標價\s*[\d,]", r"看漲到", r"直上", r"預計突破",
]

# ── 4. 風險不對稱(本模組的核心)───────────────────────────────────────────
# 風險語彙與看多行動語彙不得同句。這是 disagreement.py 那個不對稱的文字版。
_RISK_WORDS = ["失效", "跌破", "停損", "止損", "破位", "認錯", "出場"]
_BULLISH_ACTION = ["買點", "進場點", "加碼", "抄底", "撿", "接刀", "上車"]


def _sentences(text: str) -> list[str]:
    return [s for s in _SENT_SPLIT.split(text or "") if s.strip()]


def lint(text: str) -> list[Violation]:
    """回傳違規清單(空 list = 通過)。永不拋例外。"""
    out: list[Violation] = []
    if not text:
        return out

    for sentence in _sentences(text):
        for word in _BANNED:
            if word in sentence:
                out.append(Violation("banned_phrase", "block", word, sentence))
        for pat in _BANNED_CONTEXTUAL:
            m = re.search(pat, sentence)
            if m:
                out.append(Violation("banned_phrase", "block", m.group(0), sentence))
        for pat in _CALL_TO_ACTION:
            m = re.search(pat, sentence)
            if m:
                out.append(Violation("call_to_action", "block", m.group(0), sentence))
        for pat in _PREDICTION:
            m = re.search(pat, sentence)
            if m:
                out.append(Violation("price_prediction", "block", m.group(0), sentence))

        # 風險不對稱:同一句裡同時出現風險語彙與看多行動語彙
        risk_hit = next((w for w in _RISK_WORDS if w in sentence), None)
        bull_hit = next((w for w in _BULLISH_ACTION if w in sentence), None)
        if risk_hit and bull_hit:
            out.append(Violation(
                "risk_framed_as_entry", "block", f"{risk_hit}+{bull_hit}", sentence))

    return out


def assert_clean(text: str, *, label: str = "text") -> None:
    """有 block 級違規就拋 —— 給發文前的 gate 用。"""
    blocking = [v for v in lint(text) if v.severity == "block"]
    if blocking:
        detail = "\n".join(f"  {v}" for v in blocking)
        raise ValueError(f"忠實度檢查未通過({label},{len(blocking)} 項):\n{detail}")


def main(argv=None) -> int:                                   # pragma: no cover
    import argparse
    import json
    import pathlib
    import sys

    ap = argparse.ArgumentParser(description="檢查文字或發文日誌的忠實度")
    ap.add_argument("--text", help="直接檢查一段文字")
    ap.add_argument("--jsonl", help="檢查 _published.jsonl 的每一篇 text")
    a = ap.parse_args(argv)

    if a.text:
        vs = lint(a.text)
        for v in vs:
            print(v)
        print("PASS" if not vs else f"{len(vs)} 項違規")
        return 1 if vs else 0

    if a.jsonl:
        total = flagged = 0
        for line in pathlib.Path(a.jsonl).read_text("utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            total += 1
            vs = lint(rec.get("text", ""))
            if vs:
                flagged += 1
                print(f"\n── {rec.get('date')} {rec.get('variant')} ──")
                for v in vs:
                    print(" ", v)
        print(f"\n{total} 篇,{flagged} 篇有違規")
        return 1 if flagged else 0

    print("需要 --text 或 --jsonl", file=sys.stderr)
    return 2


if __name__ == "__main__":                                    # pragma: no cover
    raise SystemExit(main())
