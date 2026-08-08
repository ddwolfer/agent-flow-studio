"""Tests for scripts/rules_loader.py + rules/ 規則庫本身。

規則庫的價值在於「規則不會靜默消失」,所以測試分兩類:
  1. **規則庫的內容檢查** —— 每個 YAML 都要能解析、必要欄位都在。
     一個壞掉的 YAML 會讓那份規則從 prompt 裡消失,而且沒人會發現。
  2. **loader 的降級行為** —— 單一檔案壞掉不可以讓整批載入失敗,
     但錯誤必須浮出來(不是靜默跳過)。
"""
import pathlib
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import rules_loader as rl                                     # noqa: E402

RULES = ROOT / "rules" / "square"
ALL_YAML = sorted(RULES.rglob("*.yaml")) if RULES.exists() else []


# ── 規則庫內容 ──────────────────────────────────────────────────────────────
def test_rules_directory_exists():
    assert RULES.exists(), "rules/square/ 不存在"


@pytest.mark.parametrize("path", ALL_YAML, ids=lambda p: p.name)
def test_every_yaml_parses(path):
    """壞掉的 YAML = 那份規則從 prompt 裡靜默消失。"""
    data = yaml.safe_load(path.read_text("utf-8"))
    assert isinstance(data, dict), f"{path.name} 不是 mapping"


@pytest.mark.parametrize("path", ALL_YAML, ids=lambda p: p.name)
def test_every_yaml_has_identity(path):
    data = yaml.safe_load(path.read_text("utf-8"))
    for field in ("name", "display_name", "description"):
        assert data.get(field), f"{path.name} 缺 {field}"


def test_expected_rules_are_present():
    """核心規則不可以被誤刪 —— 這是規則庫存在的意義。"""
    loaded = rl.load("square", ROOT / "rules")
    names = {r["name"] for rules in loaded["sections"].values() for r in rules}
    for required in ("a_veteran", "b_detective", "square_format",
                     "square_selection", "short_event", "short_casual"):
        assert required in names, f"缺少核心規則 {required}"


def test_no_load_errors_in_repo():
    loaded = rl.load("square", ROOT / "rules")
    assert loaded["errors"] == [], loaded["errors"]


# ── 關鍵規則內容(防止被改壞)────────────────────────────────────────────────
def test_length_bounds_match_the_published_gate():
    """YAML 的長度規則必須與發文 gate 的 220–350 一致,否則兩邊會漂移。"""
    fmt = yaml.safe_load((RULES / "format.yaml").read_text("utf-8"))
    assert fmt["length"]["min_chars"] == 220
    assert fmt["length"]["max_chars"] == 350


def test_selection_has_all_three_priorities():
    sel = yaml.safe_load((RULES / "selection.yaml").read_text("utf-8"))
    assert set(sel["priority"]) == {"P1", "P2", "P3"}


def test_selection_overrides_include_promise_first():
    """「承諾優先」是連續四天實戰長出來的規則,不可以掉。"""
    sel = yaml.safe_load((RULES / "selection.yaml").read_text("utf-8"))
    names = {o["name"] for o in sel["overrides"]}
    assert "承諾優先" in names and "問責優先" in names


def test_casual_forbids_fabricated_anecdotes():
    c = yaml.safe_load((RULES / "shorts" / "casual.yaml").read_text("utf-8"))
    assert any("編造個人經歷" in r for r in c["hard_rules"])


def test_standby_clarity_forbids_committee_confusion():
    """把「委員會通過」講成「法案通過」是這題最容易犯的錯。"""
    s = yaml.safe_load((RULES / "standby" / "clarity-act.yaml").read_text("utf-8"))
    assert any("委員會通過" in f for f in s["forbidden"])


# ── loader 降級行為 ─────────────────────────────────────────────────────────
def test_broken_yaml_is_isolated_not_fatal(tmp_path):
    ns = tmp_path / "square"
    ns.mkdir(parents=True)
    (ns / "good.yaml").write_text(
        "name: good\ndisplay_name: 好\ndescription: d\n", encoding="utf-8")
    (ns / "bad.yaml").write_text("name: [unclosed\n", encoding="utf-8")
    loaded = rl.load("square", tmp_path)
    names = {r["name"] for rs in loaded["sections"].values() for r in rs}
    assert "good" in names                      # 好的照樣載入
    assert len(loaded["errors"]) == 1           # 壞的被記錄
    assert "bad.yaml" in loaded["errors"][0]


def test_missing_namespace_reports_error(tmp_path):
    loaded = rl.load("nonexistent", tmp_path)
    assert loaded["errors"] and loaded["sections"] == {}


def test_render_surfaces_errors_at_the_top(tmp_path):
    """壞檔必須出現在渲染結果最前面 —— 靜默跳過等於規則消失。"""
    ns = tmp_path / "square"
    ns.mkdir(parents=True)
    (ns / "bad.yaml").write_text("name: [unclosed\n", encoding="utf-8")
    text = rl.render("square", tmp_path)
    assert "載入失敗" in text and "bad.yaml" in text


# ── 渲染輸出 ────────────────────────────────────────────────────────────────
def test_render_contains_each_section():
    text = rl.render("square", ROOT / "rules")
    for section in ("selection", "format", "personas", "shorts", "standby"):
        assert f"## {section}" in text


def test_render_puts_selection_before_format():
    """先講怎麼選,再講怎麼寫 —— 順序會影響 LLM 的注意力分配。"""
    text = rl.render("square", ROOT / "rules")
    assert text.index("## selection") < text.index("## format")


def test_render_includes_hard_rules_and_forbidden():
    text = rl.render("square", ROOT / "rules")
    assert "禁止編造個人經歷" in text
    assert "委員會通過" in text


def test_render_is_reasonably_sized():
    """太大會吃掉 cron prompt 的預算;太小代表規則沒被載進去。"""
    text = rl.render("square", ROOT / "rules")
    assert 1500 < len(text) < 12000, len(text)
