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

def test_env_subs_resolves_placeholder(tmp_path):
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"
    tmpl.write_text("""{
      "mcpServers": {
        "fred": {"command": "@PY@", "args": ["@MCPDIR@/servers/fred_server.py"],
                  "env": {"FRED_API_KEY": "@FREDKEY@"}}
      }
    }""", "utf-8")
    out = tmp_path / "mcp.json"
    m.render_mcp(tools=["fred"], mcp_dir=str(tmp_path / "mcp"),
                 python_bin="/x/py", tmpl_path=tmpl, out_path=out,
                 env_subs={"FREDKEY": "secret123"})
    cfg = json.loads(out.read_text("utf-8"))
    assert cfg["mcpServers"]["fred"]["env"]["FRED_API_KEY"] == "secret123"


def test_env_subs_unresolved_left_literal(tmp_path):
    """If a template references @KEY@ we don't supply, leave it literal so the
    failure surfaces at MCP startup rather than being silently masked."""
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"
    tmpl.write_text("""{
      "mcpServers": {
        "fred": {"command": "@PY@", "args": ["@MCPDIR@/servers/fred_server.py"],
                  "env": {"FRED_API_KEY": "@FREDKEY@"}}
      }
    }""", "utf-8")
    out = tmp_path / "mcp.json"
    m.render_mcp(tools=["fred"], mcp_dir=str(tmp_path / "mcp"),
                 python_bin="/x/py", tmpl_path=tmpl, out_path=out, env_subs=None)
    cfg = json.loads(out.read_text("utf-8"))
    assert cfg["mcpServers"]["fred"]["env"]["FRED_API_KEY"] == "@FREDKEY@"


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


def test_render_substitutes_root(tmp_path):
    """@ROOT@ in args resolves to root_dir, distinct from @MCPDIR@."""
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"
    tmpl.write_text("""{
      "mcpServers": {
        "kg": {"command": "node", "args": ["@ROOT@/mcp/knowledge-graph/main.js"]}
      }
    }""", "utf-8")
    out = tmp_path / "mcp.json"
    m.render_mcp(tools=["kg"], mcp_dir=str(tmp_path / "fw" / "mcp"),
                 python_bin="/x/py", tmpl_path=tmpl, out_path=out,
                 root_dir=str(tmp_path / "root"))
    cfg = json.loads(out.read_text("utf-8"))
    assert cfg["mcpServers"]["kg"]["args"][0] == \
        f"{tmp_path / 'root'}/mcp/knowledge-graph/main.js"


def test_render_root_unset_leaves_placeholder_literal(tmp_path):
    """If root_dir is None, @ROOT@ stays literal (parallel to env_subs behaviour)
    so a misconfigured caller fails loud at MCP startup, not silently."""
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"
    tmpl.write_text("""{
      "mcpServers": {
        "kg": {"command": "node", "args": ["@ROOT@/mcp/knowledge-graph/main.js"]}
      }
    }""", "utf-8")
    out = tmp_path / "mcp.json"
    m.render_mcp(tools=["kg"], mcp_dir=str(tmp_path / "fw" / "mcp"),
                 python_bin="/x/py", tmpl_path=tmpl, out_path=out)
    cfg = json.loads(out.read_text("utf-8"))
    assert cfg["mcpServers"]["kg"]["args"][0] == \
        "@ROOT@/mcp/knowledge-graph/main.js"
