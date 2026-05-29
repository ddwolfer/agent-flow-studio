"""Smoke test that workflows/serenity-digest.json parses correctly via the
shared loader, and that its declared tools are all in the MCP template +
TOOL_MAP. Catches typos in the JSON or unregistered MCPs early."""
import importlib.util, json, pathlib


HERE = pathlib.Path(__file__).resolve().parents[1]


def _load(modname, relpath):
    p = HERE / relpath
    spec = importlib.util.spec_from_file_location(modname, p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_serenity_workflow_json_loads():
    workflow = _load("workflow", "workflow.py")
    cfg = workflow.load_workflow("serenity-digest", HERE)
    assert cfg.name == "serenity-digest"
    assert cfg.tools == ["web-fetch", "knowledge-graph"]
    assert cfg.post.telegram == "TELEGRAM_TOPIC_SERENITY"
    assert cfg.post.pdf is False
    assert cfg.output == "reports/serenity-digest/{date}.html"


def test_serenity_tools_are_in_template():
    """Every tool the workflow declares must exist in the MCP template,
    otherwise render_mcp would raise at runtime."""
    tmpl = json.loads((HERE / "mcp" / "mcp.json.tmpl").read_text("utf-8"))
    available = set(tmpl["mcpServers"].keys())
    workflow_json = json.loads(
        (HERE / "workflows" / "serenity-digest.json").read_text("utf-8"))
    for t in workflow_json["tools"]:
        assert t in available, f"workflow tool {t!r} not in mcp.json.tmpl"


def test_serenity_tools_are_in_tool_map():
    """run-workflow's TOOL_MAP must know how to expand every tool the
    workflow uses, otherwise --allowedTools would miss MCP tool ids."""
    text = (HERE / "run-workflow.py").read_text("utf-8")
    assert '"web-fetch"' in text
    assert '"knowledge-graph"' in text
    assert "store_knowledge" in text
    assert "search_memory" in text
