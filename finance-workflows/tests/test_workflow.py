import importlib.util, json, pathlib

def _load():
    p = pathlib.Path(__file__).parents[1] / "workflow.py"
    spec = importlib.util.spec_from_file_location("workflow", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

_VALID = {
    "name": "demo",
    "model": "claude-sonnet-4-6",
    "max_turns": 30,
    "sources": [{"kind": "youtube", "handle": "@x", "search_query": "x"}],
    "tools": ["yt-dlp"],
    "prompts": ["prompts/shared/faithfulness.md", "prompts/crypto/main.md"],
    "output": "reports/demo/{date}.html",
    "post": {"pdf": True},
}

def test_load_valid_workflow(tmp_path):
    w = _load()
    p = tmp_path / "wf.json"
    p.write_text(json.dumps(_VALID), "utf-8")
    cfg = w.load_workflow_from_path(p)
    assert cfg.name == "demo"
    assert cfg.model == "claude-sonnet-4-6"
    assert cfg.max_turns == 30
    assert cfg.tools == ["yt-dlp"]
    assert cfg.post.pdf is True
    assert cfg.history is None

def test_load_with_history(tmp_path):
    w = _load()
    payload = {**_VALID, "history": {"format": "jsonl", "summarize_with": "claude-haiku-4-5",
                                     "fields": ["stance", "confidence"]}}
    p = tmp_path / "wf.json"; p.write_text(json.dumps(payload), "utf-8")
    cfg = w.load_workflow_from_path(p)
    assert cfg.history.format == "jsonl"
    assert cfg.history.summarize_with == "claude-haiku-4-5"
    assert cfg.history.fields == ["stance", "confidence"]

def test_missing_required_field_raises(tmp_path):
    w = _load()
    bad = {k: v for k, v in _VALID.items() if k != "tools"}
    p = tmp_path / "wf.json"; p.write_text(json.dumps(bad), "utf-8")
    try:
        w.load_workflow_from_path(p)
    except w.WorkflowError as e:
        assert "tools" in str(e)
        return
    raise AssertionError("expected WorkflowError")

def test_empty_tools_raises(tmp_path):
    w = _load()
    bad = {**_VALID, "tools": []}
    p = tmp_path / "wf.json"; p.write_text(json.dumps(bad), "utf-8")
    try:
        w.load_workflow_from_path(p); raise AssertionError("expected WorkflowError")
    except w.WorkflowError:
        pass

def test_resolve_output_substitutes_date(tmp_path):
    w = _load()
    p = tmp_path / "wf.json"; p.write_text(json.dumps(_VALID), "utf-8")
    cfg = w.load_workflow_from_path(p)
    assert w.resolve_output(cfg, "2026-05-21") == "reports/demo/2026-05-21.html"
