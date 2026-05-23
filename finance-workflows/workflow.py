"""workflow.json loader + validator. Plain dataclasses, no third-party deps."""
import json, pathlib, sys
from dataclasses import dataclass
from typing import Optional


class WorkflowError(Exception):
    pass


@dataclass
class Source:
    kind: str
    handle: str = ""
    search_query: str = ""
    name: str = ""
    url: str = ""
    rss: str = ""


@dataclass
class Post:
    pdf: bool = False
    # Telegram notify: env-var NAME holding this workflow's forum-topic id within
    # the shared supergroup (e.g. "TELEGRAM_TOPIC_CRYPTO" → 123). None/absent →
    # skip. Empty env value → post to the supergroup's general thread.
    # Shared across workflows via $TELEGRAM_BOT_TOKEN + $TELEGRAM_CHAT_ID.
    telegram: Optional[str] = None


@dataclass
class History:
    format: str
    summarize_with: str
    fields: list


@dataclass
class Workflow:
    name: str
    model: str
    max_turns: int
    sources: list
    tools: list
    prompts: list
    output: str
    post: Post
    description: str = ""
    history: Optional[History] = None


def _require(d: dict, key: str, label: str):
    if key not in d or d[key] in (None, "", []):
        raise WorkflowError(f"workflow missing required field '{key}' in {label}")


def load_workflow_from_path(path) -> Workflow:
    p = pathlib.Path(path)
    try:
        raw = json.loads(p.read_text("utf-8"))
    except FileNotFoundError:
        raise WorkflowError(f"workflow file not found: {p}")
    except json.JSONDecodeError as e:
        raise WorkflowError(f"invalid JSON in {p}: {e}")

    for k in ("name", "model", "max_turns", "sources", "tools", "prompts", "output"):
        _require(raw, k, str(p))
    if not isinstance(raw["tools"], list) or len(raw["tools"]) == 0:
        raise WorkflowError(f"'tools' must be a non-empty list in {p}")
    if not isinstance(raw["prompts"], list) or len(raw["prompts"]) == 0:
        raise WorkflowError(f"'prompts' must be a non-empty list in {p}")

    sources = [Source(**{**{"kind": ""}, **s}) for s in raw["sources"]]
    post = Post(**raw.get("post", {}))
    history = None
    if "history" in raw and raw["history"]:
        h = raw["history"]
        for k in ("format", "summarize_with", "fields"):
            _require(h, k, f"{p} .history")
        history = History(format=h["format"], summarize_with=h["summarize_with"],
                          fields=list(h["fields"]))

    return Workflow(
        name=raw["name"], model=raw["model"], max_turns=int(raw["max_turns"]),
        sources=sources, tools=list(raw["tools"]), prompts=list(raw["prompts"]),
        output=raw["output"], post=post, history=history,
        description=raw.get("description", ""),
    )


def load_workflow(name: str, root) -> Workflow:
    """Convenience: load workflows/<name>.json from a given finance-workflows/ root."""
    return load_workflow_from_path(pathlib.Path(root) / "workflows" / f"{name}.json")


def resolve_output(cfg: Workflow, date_iso: str) -> str:
    """Substitute {date} (and only {date}) in the output template."""
    return cfg.output.replace("{date}", date_iso)
