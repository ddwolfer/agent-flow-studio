import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "lib" / "gemma_transcribe.py"
    spec = importlib.util.spec_from_file_location("gemma_transcribe", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_chunk_ranges():
    m = _load()
    assert m._chunk_ranges(1000, 300) == [(0,300),(300,600),(600,900),(900,1000)]
    assert m._chunk_ranges(250, 300) == [(0,250)]

def test_chunk_ranges_zero_duration():
    m = _load()
    assert m._chunk_ranges(0, 300) == [(0, 0)]
