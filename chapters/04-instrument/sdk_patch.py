"""sdk_patch.py - wrap the Anthropic client at import time. Chapter 4.

Option two, for when you cannot edit the call site. Import this module before
the tool builds its client and every Messages.create goes through the logger.

It works and it's fragile. It breaks on the next SDK release, it's invisible to
whoever debugs it next, and monkeypatching somebody else's client to do
accounting is fine in your own tooling and inexcusable in a shared codebase.
Use it to get a day of data, not as infrastructure.
"""
import functools, os, sys

_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(_CHAPTERS) == "chapters":
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

import anthropic, tracelog

_orig = anthropic.resources.Messages.create

@functools.wraps(_orig)
def _patched(self, **kw):
    # kw is bound onto the call; traced() gets `model` only for the price table.
    # Pass kw to both and you get "multiple values for keyword argument 'model'".
    return tracelog.traced(functools.partial(_orig, self, **kw),
                           model=kw.get("model", "unknown"),
                           task=os.environ.get("TASK_HINT", "agent-step"),
                           prompt_text=str(kw.get("messages", ""))[:20000])

anthropic.resources.Messages.create = _patched
