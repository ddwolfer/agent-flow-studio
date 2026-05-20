import importlib.util, json, pathlib

def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp_render.py"
    spec = importlib.util.spec_from_file_location("mcp_render", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

_TMPL = """{
  "mcpServers": {
    "yt-dlp":    { "command": "@PY@", "args": ["@MCPDIR@/servers/ytdlp_server.py"] },
    "rss":       { "command": "@PY@", "args": ["@MCPDIR@/servers/rss_server.py"] },
    "web-fetch": { "command": "@PY@", "args": ["@MCPDIR@/servers/web_fetch_server.py"] }
  }
}"""

def test_render_keeps_only_requested_servers(tmp_path):
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"; tmpl.write_text(_TMPL, "utf-8")
    out = tmp_path / "mcp.json"
    m.render_mcp(tools=["rss", "web-fetch"], mcp_dir=str(tmp_path / "mcp"),
                 python_bin="/x/py", tmpl_path=tmpl, out_path=out)
    cfg = json.loads(out.read_text("utf-8"))
    assert set(cfg["mcpServers"].keys()) == {"rss", "web-fetch"}
    assert cfg["mcpServers"]["rss"]["command"] == "/x/py"
    assert cfg["mcpServers"]["rss"]["args"][0] == f"{tmp_path / 'mcp'}/servers/rss_server.py"

def test_render_rejects_unknown_tool(tmp_path):
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"; tmpl.write_text(_TMPL, "utf-8")
    try:
        m.render_mcp(tools=["coingecko"], mcp_dir=str(tmp_path / "mcp"),
                     python_bin="/x/py", tmpl_path=tmpl, out_path=tmp_path / "mcp.json")
        raise AssertionError("expected error")
    except m.McpRenderError as e:
        assert "coingecko" in str(e)

def test_derive_allowed_tools_from_servers():
    m = _load()
    out = m.derive_allowed_tools(["rss", "yt-dlp"], {
        "rss": ["rss_fetch"],
        "yt-dlp": ["ytdlp_search_videos", "ytdlp_transcript_page"],
        "web-fetch": ["web_fetch", "web_extract_article"],
    })
    assert out == [
        "mcp__rss__rss_fetch",
        "mcp__yt-dlp__ytdlp_search_videos",
        "mcp__yt-dlp__ytdlp_transcript_page",
        "Write", "Read",
    ]
