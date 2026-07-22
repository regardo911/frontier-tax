"""guard.py - score every routed output; escalate the failures. Chapter 11.

A gateway's fallback fires on an error, a timeout, a rate limit. It cannot fire
on a fast, well-formed, confident, completely wrong answer, because nothing in
a gateway has ever seen your definition of correct. That gate has to be yours,
because the predicate is yours.
"""
import os, sys, uuid

_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(_CHAPTERS) == "chapters":
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

from tasks import TASKS
from providers import complete
from tracelog import traced, text_of
from router import route

FRONTIER = os.environ["DEFAULT_MODEL"]

def guarded(task, messages, trace_ctx=None, **kw):
    """Route, check, and escalate on a failed check. Returns (text, meta)."""
    job = uuid.uuid4().hex[:12]          # one id across both attempts
    cheap = route(task)
    check = TASKS[task]["check"]
    ctx = dict(trace_ctx or {}, input=messages[-1]["content"], id=job)

    if cheap != FRONTIER:
        resp = traced(complete, model=cheap, task=task,
                      meta={"job": job},
                      prompt_text=messages[-1]["content"],
                      alias=cheap, messages=messages, **kw)
        text = text_of(resp)
        try:
            ok = check(text, ctx)
        except Exception:
            ok = False                    # a predicate that throws is a fail
        if ok:
            return text, {"job": job, "model": cheap, "escalated": False}

    resp = traced(complete, model=FRONTIER, task=f"{task}:escalated",
                  meta={"job": job}, prompt_text=messages[-1]["content"],
                  alias=FRONTIER, messages=messages, **kw)
    return text_of(resp), {"job": job, "model": FRONTIER,
                           "escalated": cheap != FRONTIER}
