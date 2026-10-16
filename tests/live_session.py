"""
Shared request helpers for the live test scripts, which call the real backend
(test_response_quality.py, test_performance_snapshot.py, test_ciel_master.py).

They make a test request look like a request from the app:

- a fresh Langflow session per request. Without a session_id, Langflow used
  one default session for every test run; its history grew to ~490k
  characters in the research sub-agent and made cases depend on each other.
- the same tweaks the app sends for an anonymous visitor without files.
- the answer the user sees: app.final_answer_text, not data.text (which joins
  every Agent round in Langflow 1.12, so duplicates were judged).
"""

import ast
import uuid
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

# Node IDs in the production flow (same defaults as in app.py).
MEMORY_SEARCH_ID = "CielMemorySearch-BC6pl"
MEMORY_STORE_ID = "CielMemoryStore-uBmzx"
TABLE_ANALYST_ID = "CielTableAnalyst-t4bL3"
ML_ANALYST_ID = "CielMLAnalyst-m7Lq2"


def _load_app_function(name):
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP_PATH), "exec"), namespace)
    return namespace[name]


final_answer_text = _load_app_function("final_answer_text")


def new_session_id(label):
    """One Langflow session per test request, like one chat in the app."""
    return f"livetest-{label}-{uuid.uuid4().hex[:12]}"


def app_tweaks(extra=None):
    """Tweaks the app sends for an anonymous visitor without files, plus `extra`."""
    tweaks = {
        MEMORY_SEARCH_ID: {"memory_owner": ""},
        MEMORY_STORE_ID: {"memory_owner": ""},
        TABLE_ANALYST_ID: {"attached_tables": ""},
        ML_ANALYST_ID: {"attached_tables": ""},
    }

    for node_id, values in (extra or {}).items():
        tweaks.setdefault(node_id, {}).update(values)

    return tweaks


def answer_from(data):
    """The answer shown to the user for a /api/v1/run response."""
    return final_answer_text(data["outputs"][0]["outputs"][0]["results"]["message"])
