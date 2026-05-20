"""Extract the first balanced top-level {...} JSON object from a string.

Tolerates surrounding prose, markdown fences, and multiple candidates — returns
the first one that parses cleanly. Returns None if no parseable object exists.

Used by run-workflow.py to consume Haiku's history-summary output (which usually
has the JSON wrapped in prose like '```json\\n{...}\\n```' or 'Here is the JSON:\\n{...}')."""
import json


def extract_first_json_object(text):
    if not text:
        return None
    start = text.find("{")
    while start >= 0:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break  # try next outer {
        start = text.find("{", start + 1)
    return None
