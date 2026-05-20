import importlib.util, pathlib


def _load():
    p = pathlib.Path(__file__).parents[1] / "history_extract.py"
    spec = importlib.util.spec_from_file_location("history_extract", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_bare_json_object():
    m = _load()
    assert m.extract_first_json_object('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}


def test_prose_wrapped_json():
    m = _load()
    s = "Here is the summary:\n\n{\"overall_stance\": \"中性\", \"confidence\": 3.0}\n\nThanks."
    out = m.extract_first_json_object(s)
    assert out == {"overall_stance": "中性", "confidence": 3.0}


def test_markdown_fenced_json():
    m = _load()
    s = "```json\n{\n  \"x\": [1, 2, 3],\n  \"y\": {\"nested\": true}\n}\n```"
    out = m.extract_first_json_object(s)
    assert out == {"x": [1, 2, 3], "y": {"nested": True}}


def test_nested_braces():
    m = _load()
    s = '{"a": {"b": {"c": 1}}, "d": [1, {"e": 2}]}'
    assert m.extract_first_json_object(s) == {"a": {"b": {"c": 1}}, "d": [1, {"e": 2}]}


def test_first_invalid_then_valid():
    m = _load()
    s = '{not really json} but then\n{"good": true}'
    assert m.extract_first_json_object(s) == {"good": True}


def test_no_json_returns_none():
    m = _load()
    assert m.extract_first_json_object("just some text no braces") is None
    assert m.extract_first_json_object("") is None
    assert m.extract_first_json_object(None) is None


def test_string_with_braces_inside():
    """A JSON string that itself contains '{' must not confuse the depth scan."""
    m = _load()
    s = '{"msg": "has { and } inside the string", "n": 1}'
    assert m.extract_first_json_object(s) == {"msg": "has { and } inside the string", "n": 1}


def test_escaped_quote_in_string():
    m = _load()
    s = '{"msg": "an \\"escaped quote\\" plus { brace", "n": 2}'
    assert m.extract_first_json_object(s) == {"msg": 'an "escaped quote" plus { brace', "n": 2}
