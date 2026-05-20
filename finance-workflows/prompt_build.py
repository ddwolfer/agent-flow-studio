"""Concatenate prompt .md files in order, then substitute ${TOKEN} placeholders
with values from a dict. Unknown tokens are left literal (debug visibility)."""
import pathlib


def build_prompt(*, prompt_paths, substitutions):
    parts = []
    for p in prompt_paths:
        parts.append(pathlib.Path(p).read_text("utf-8"))
    text = "\n\n".join(parts)
    for k, v in substitutions.items():
        text = text.replace(f"${{{k}}}", str(v))
    return text
