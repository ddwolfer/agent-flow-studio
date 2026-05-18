import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "servers" / "ytdlp_server.py"
    spec = importlib.util.spec_from_file_location("ytdlp_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_map_search_entries():
    m = _load()
    raw = {"entries": [{"id": "abc", "title": "T1", "upload_date": "20260518",
                        "webpage_url": "https://youtu.be/abc"}]}
    assert m._map_search(raw, 1) == [{"video_id": "abc", "title": "T1",
        "upload_date": "2026-05-18", "url": "https://youtu.be/abc"}]
