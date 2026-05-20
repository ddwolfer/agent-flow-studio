import importlib.util, pathlib

def _load():
    p = pathlib.Path(__file__).parents[1] / "prompt_build.py"
    spec = importlib.util.spec_from_file_location("prompt_build", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_concat_and_substitute(tmp_path):
    pb = _load()
    a = tmp_path / "a.md"; a.write_text("Faithfulness rules.\n", "utf-8")
    b = tmp_path / "b.md"; b.write_text("Write to ${OUTPUT_PATH} on ${DATE}.\nName: ${WORKFLOW_NAME}\n", "utf-8")
    out = pb.build_prompt(
        prompt_paths=[a, b],
        substitutions={
            "DATE": "2026-05-21",
            "OUTPUT_PATH": "/tmp/r.html",
            "WORKFLOW_NAME": "crypto-daily",
            "SOURCES_JSON": '[{"kind":"youtube"}]',
        },
    )
    assert "Faithfulness rules." in out
    assert "Write to /tmp/r.html on 2026-05-21." in out
    assert "Name: crypto-daily" in out

def test_missing_file_raises(tmp_path):
    pb = _load()
    try:
        pb.build_prompt(prompt_paths=[tmp_path / "nope.md"], substitutions={})
        raise AssertionError("expected error")
    except FileNotFoundError:
        pass

def test_unsubstituted_token_kept_as_is(tmp_path):
    pb = _load()
    a = tmp_path / "a.md"; a.write_text("Has ${UNKNOWN} placeholder.\n", "utf-8")
    out = pb.build_prompt(prompt_paths=[a], substitutions={"DATE": "2026-05-21"})
    assert "${UNKNOWN}" in out
