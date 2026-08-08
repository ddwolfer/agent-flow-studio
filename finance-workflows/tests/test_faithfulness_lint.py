"""Tests for scripts/faithfulness_lint.py。

這個檢查器的設計取捨是「**寧可漏抓,不可誤擋**」—— 誤擋會讓當天發不出
文,而規則本身已有 prompt 那一層。所以下面的「不該擋」測試比「該擋」
測試更重要,而且直接取自 51 篇真實已發布貼文的句型。
"""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import faithfulness_lint as fl                                # noqa: E402


def _rules(text):
    return {v.rule for v in fl.lint(text)}


# ── 該擋:絕對禁語 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "比特幣必漲", "保證獲利的機會", "閉眼買就對了", "無腦買",
    "梭哈了", "抄作業就好", "這波穩了", "躺賺",
])
def test_banned_phrases_blocked(text):
    assert "banned_phrase" in _rules(text), text


# ── 該擋:喊單 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "建議買入 BTC", "現在可以進場了", "快買", "上車吧", "跟單就對了",
])
def test_call_to_action_blocked(text):
    assert "call_to_action" in _rules(text), text


# ── 該擋:價格預測 ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "比特幣會漲到 8 萬", "ETH 將跌到 1500", "目標價 90000", "看漲到兩萬",
])
def test_price_prediction_blocked(text):
    assert "price_prediction" in _rules(text), text


# ── 該擋:風險不對稱(本模組的核心)─────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "跌破 62,715 就是很好的買點",
    "失效位附近可以加碼",
    "停損掃完之後就是抄底時機",
    "破位就進場點",
])
def test_risk_framed_as_entry_blocked(text):
    assert "risk_framed_as_entry" in _rules(text), text


def test_risk_and_bullish_in_separate_sentences_is_fine():
    """分屬兩句就不算把風險寫成買點 —— 這是我們貼文的正常寫法。"""
    text = "跌破 62,715,上升結構失效。若收盤站回,劇本還在。"
    assert "risk_framed_as_entry" not in _rules(text)


# ── 不該擋:真實貼文用過的合規句型 ──────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "⚠️ 個人結構解讀,非投資建議。",
    "⚠️ 結構解讀,非投資建議,價位來自程式化計算。",
    "收盤守住 64,341 → 我的目標還是 70,270,這波獨立性就成立",
    "若跟著外圍跌破 64,341 → 那「脫鉤」是假象,認錯出場",
    "ETH 守穩 1,875 之上 → 這次收復才有意義,跌破就是假動作",
    "真站穩了,下一個要面對的還是 2,000 那道整數牆",
    "我不建議在這裡追",
    "程式今天把結構底線上移到 63,092,這是新的觀察位",
    "跌破 62,715,七月中以來的整段上升結構就正式失效,得重新看",
    "平盤也能爆三億。你自己的倉位離清算價還有多遠?",
])
def test_legit_sentences_not_flagged(text):
    assert fl.lint(text) == [], f"誤擋:{text}"


# ── 上下文敏感詞 ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,blocked", [
    ("這波穩了", True),
    ("真站穩了", False),
    ("守穩了 1900", False),
    ("踩穩了支撐", False),
])
def test_wen_le_is_context_sensitive(text, blocked):
    assert ("banned_phrase" in _rules(text)) is blocked, text


@pytest.mark.parametrize("text", ["非投資建議買入判斷", "不建議買入"])
def test_negated_advice_not_flagged(text):
    assert "call_to_action" not in _rules(text), text


# ── API 行為 ────────────────────────────────────────────────────────────────
def test_empty_text_is_clean():
    assert fl.lint("") == [] and fl.lint(None) == []


def test_assert_clean_raises_on_violation():
    with pytest.raises(ValueError, match="忠實度檢查未通過"):
        fl.assert_clean("建議買入 BTC", label="test")


def test_assert_clean_passes_on_clean_text():
    fl.assert_clean("⚠️ 個人結構解讀,非投資建議。")


# ── 回歸:全部已發布貼文必須零違規 ──────────────────────────────────────────
def test_all_published_posts_are_clean():
    """真實驗證集。任何一篇被擋,不是檢查器太嚴,就是我們真的發過壞內容。"""
    log = ROOT / "reports" / "binance-square" / "_published.jsonl"
    if not log.exists():
        pytest.skip("發文日誌不存在(乾淨 checkout)")
    bad = []
    for line in log.read_text("utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        for v in fl.lint(rec.get("text", "")):
            bad.append(f"{rec.get('date')} {rec.get('variant')}: {v}")
    assert not bad, "已發布貼文出現違規:\n" + "\n".join(bad)
