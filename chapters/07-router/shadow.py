"""shadow.py - serve the frontier answer, call the routed model too, log it,
discard it. Chapter 7.

Stage one of three. Run this for a week before you promote anything: nobody
downstream is affected by a wrong routing decision, because the routed answer
never leaves the process.
"""
import concurrent.futures as cf
import os, sys

_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(_CHAPTERS) == "chapters":
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

from providers import complete
from tracelog import traced
from router import route, run


def run_shadow(task, messages, primary, **kw):
    """Serve `primary`. Call the routed model too, log it, discard it."""
    shadow_model = route(task)
    if shadow_model == primary:
        return run(task, messages, **kw)          # nothing to compare
    with cf.ThreadPoolExecutor(2) as pool:
        real = pool.submit(traced, complete, model=primary, task=task,
                           prompt_text=messages[-1]["content"],
                           alias=primary, messages=messages, **kw)
        pool.submit(_quiet, shadow_model, task, messages, kw)
    return real.result()

def _quiet(model, task, messages, kw):
    """Shadow calls must never raise into the request path."""
    try:
        traced(complete, model=model, task=f"shadow:{task}",
               prompt_text=messages[-1]["content"],
               alias=model, messages=messages, **kw)
    except Exception:
        pass
