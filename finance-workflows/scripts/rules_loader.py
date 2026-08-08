"""載入 rules/ 底下的 YAML 規則,組成當日可用的 prompt 片段。

為什麼要有:廣場的規則原本散在三個地方 —— cron prompt、spec 文件、
以及我的記憶。in-session cron 每 7 天過期一次,重掛時若沒把這段時間
累積的判準補回去,規則就靜默消失(而且沒有任何東西會提醒)。

把規則變成版控 YAML 之後:
  - cron prompt 只要說「照 rules/square/ 執行」,不必內嵌整套規則
  - 改規則 = 改檔案 + commit,有 diff、有歷史、不會遺失
  - 重掛 cron 不再是「憑記憶重寫 prompt」

設計取自 daily_stock_analysis 的 strategies/*.yaml:自然語言 instructions
+ 少量結構化 metadata 決定何時啟用。他們用 market_regimes,我們用
select_when / triggers。

用法:
    python rules_loader.py --render square          # 印出當日 prompt 片段
    python rules_loader.py --list                   # 列出載到的規則
    python rules_loader.py --check                  # 驗證所有 YAML 可解析
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / "rules"

# 渲染順序 —— 先講怎麼選,再講怎麼寫,最後才是待命素材。
_SECTION_ORDER = ["selection", "format", "personas", "shorts", "standby"]


def _section_for(path: pathlib.Path, base: pathlib.Path) -> str:
    """依相對路徑決定屬於哪一段(子目錄名,或檔名去副檔名)。"""
    rel = path.relative_to(base)
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def load(namespace: str = "square", rules_dir: pathlib.Path | None = None) -> dict:
    """載入一個 namespace 下的所有規則,依 section 分組。

    單一檔案解析失敗不會讓整批掛掉 —— 記進 errors 讓呼叫端決定。規則庫
    壞一個檔不該讓當天發不出文;但也不能靜默,所以錯誤要能被看見。
    """
    base = (rules_dir or RULES_DIR) / namespace
    out: dict = {"namespace": namespace, "sections": {}, "errors": []}
    if not base.exists():
        out["errors"].append(f"規則目錄不存在:{base}")
        return out

    for path in sorted(base.rglob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text("utf-8")) or {}
        except Exception as e:                    # noqa: BLE001 — 外部檔案邊界
            out["errors"].append(f"{path.relative_to(base)}: {type(e).__name__}: {e}")
            continue
        data["_path"] = str(path.relative_to(base))
        out["sections"].setdefault(_section_for(path, base), []).append(data)
    return out


def _render_rule(rule: dict) -> str:
    """把一份規則渲染成人類與 LLM 都讀得懂的段落。"""
    lines = [f"### {rule.get('display_name') or rule.get('name') or rule['_path']}"]
    if rule.get("description"):
        lines.append(rule["description"])

    for key, label in (
        ("select_when", "何時選這篇"),
        ("triggers", "觸發條件"),
        ("material_sources", "素材來源"),
        ("angles", "可寫角度"),
    ):
        items = rule.get(key)
        if not items:
            continue
        lines.append(f"\n**{label}:**")
        for it in items:
            if isinstance(it, dict):
                lines.append(f"- {it.get('name')}:{it.get('note', '')}")
            else:
                lines.append(f"- {it}")

    for key in ("instructions", "structure", "language", "zero_jargon",
                "best_material", "publish_flow", "verified_facts"):
        if rule.get(key):
            lines.append(f"\n{str(rule[key]).rstrip()}")

    if rule.get("priority"):
        lines.append("\n**優先序:**")
        for tag, spec in rule["priority"].items():
            lines.append(f"- {tag}:{spec.get('when')} → 發 {spec.get('pick')}")
    if rule.get("tie_break"):
        lines.append(f"\n**tie-break:** {str(rule['tie_break']).rstrip()}")
    if rule.get("overrides"):
        lines.append("\n**覆寫 tie-break 的硬規則:**")
        for ov in rule["overrides"]:
            lines.append(f"- **{ov.get('name')}** — {str(ov.get('rule', '')).strip()}")

    if rule.get("length"):
        L = rule["length"]
        lines.append(f"\n**長度:** {L.get('min_chars')}–{L.get('max_chars')} 字"
                     f"({L.get('counting')});{L.get('enforcement')}")
    if rule.get("fixed_elements"):
        F = rule["fixed_elements"]
        lines.append(f"**固定元素:** $標籤 ×{F.get('cashtags')}、"
                     f"#話題 ×{F.get('hashtags')}、{F.get('disclaimer')}")

    for key, label in (("hard_rules", "硬規則"), ("forbidden", "禁區"),
                       ("banned_wording", "禁用措辭")):
        if rule.get(key):
            lines.append(f"\n**{label}:**")
            lines.extend(f"- {x}" for x in rule[key])

    return "\n".join(lines)


def render(namespace: str = "square", rules_dir: pathlib.Path | None = None) -> str:
    """組出完整的 prompt 片段。"""
    loaded = load(namespace, rules_dir)
    parts = [f"# 規則庫:{namespace}(來源 rules/{namespace}/,已版控)"]
    if loaded["errors"]:
        parts.append("\n⚠️ **下列規則檔載入失敗,請先修:**")
        parts.extend(f"- {e}" for e in loaded["errors"])

    sections = loaded["sections"]
    ordered = [s for s in _SECTION_ORDER if s in sections]
    ordered += [s for s in sorted(sections) if s not in _SECTION_ORDER]
    for section in ordered:
        parts.append(f"\n## {section}")
        for rule in sections[section]:
            parts.append("\n" + _render_rule(rule))
    return "\n".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", metavar="NAMESPACE", default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--namespace", default="square")
    a = ap.parse_args(argv)

    if a.render:
        print(render(a.render))
        return 0
    loaded = load(a.namespace)
    if a.list or a.check:
        for section, rules in sorted(loaded["sections"].items()):
            for r in rules:
                print(f"  {section:10} {r.get('name','?'):18} {r['_path']}")
        if loaded["errors"]:
            print("\n錯誤:", file=sys.stderr)
            for e in loaded["errors"]:
                print(f"  {e}", file=sys.stderr)
            return 1
        print(f"\n✅ {sum(len(v) for v in loaded['sections'].values())} 份規則,全部可解析")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
