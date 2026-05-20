"""Render finance-workflows/mcp/mcp.json from the template, keeping only the
servers a workflow declares in its `tools` field, with paths/python resolved."""
import json, pathlib


class McpRenderError(Exception):
    pass


def render_mcp(*, tools, mcp_dir, python_bin, tmpl_path, out_path, env_subs=None):
    """Read tmpl, parse JSON, retain only the requested server keys, substitute
    @PY@/@MCPDIR@ in command/args and any `@KEY@` from `env_subs` in env values,
    write to out_path. Returns the absolute out_path as a string.

    Servers whose template has an env entry referencing `@KEY@` but `env_subs`
    does not include that KEY are still rendered — their `@KEY@` placeholder
    remains literal so failures are visible at MCP startup rather than silent.

    Raises McpRenderError if any requested tool isn't in the template.
    """
    tmpl = json.loads(pathlib.Path(tmpl_path).read_text("utf-8"))
    available = set(tmpl.get("mcpServers", {}).keys())
    unknown = [t for t in tools if t not in available]
    if unknown:
        raise McpRenderError(f"unknown MCP server(s) in workflow.tools: {unknown}; "
                             f"template has: {sorted(available)}")
    env_subs = env_subs or {}
    rendered = {"mcpServers": {}}
    for name in tools:
        entry = json.loads(json.dumps(tmpl["mcpServers"][name]))  # deep copy
        entry["command"] = entry["command"].replace("@PY@", python_bin)
        entry["args"] = [a.replace("@MCPDIR@", mcp_dir).replace("@PY@", python_bin)
                         for a in entry.get("args", [])]
        if "env" in entry:
            new_env = {}
            for k, v in entry["env"].items():
                vs = v
                for sk, sv in env_subs.items():
                    vs = vs.replace(f"@{sk}@", sv)
                new_env[k] = vs
            entry["env"] = new_env
        rendered["mcpServers"][name] = entry
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rendered, indent=2, ensure_ascii=False), "utf-8")
    return str(out)


def derive_allowed_tools(servers, tool_map):
    """Given the requested server names and a {server: [tool_ids]} map, return
    the flat allowedTools list claude -p expects, plus Write+Read at the end."""
    out = []
    for s in servers:
        for t in tool_map.get(s, []):
            out.append(f"mcp__{s}__{t}")
    out.extend(["Write", "Read"])
    return out
