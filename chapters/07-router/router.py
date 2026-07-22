"""router.py - read the table, pick the model, log the call. Chapter 7."""
import json, os, sys

_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(_CHAPTERS) == "chapters":
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

from providers import complete
from tracelog import traced

with open(os.environ.get("ROUTES", "routes.json")) as _f:
    TABLE = json.load(_f)

def route(task):
    if os.environ.get("ROUTER_OFF") == "1":   # the kill switch. see above.
        return os.environ["DEFAULT_MODEL"]
    rule = TABLE.get(task)
    if rule is None:                       # unknown task = most capable model
        return os.environ["DEFAULT_MODEL"] # never silently route the unknown cheap
    return rule["chosen"]

def run(task, messages, **kw):
    model = route(task)
    return traced(complete, model=model, task=task,
                  prompt_text=messages[-1]["content"],
                  alias=model, messages=messages, **kw)
