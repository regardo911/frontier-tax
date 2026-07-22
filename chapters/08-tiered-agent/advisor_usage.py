"""advisor_usage.py - the advisor's tokens are not in the top-level usage block.
Chapter 8.

A cheap executor calling an expensive advisor once bills at two rates, and only
one of them is where your logger looks. On the book's worked call the logger
reports $0.00640 against a true $0.08890 - seven percent of what the call cost.
The advisor read the whole transcript at the expensive model's input rate, and
that is where the money went.
"""
import os, sys

_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(_CHAPTERS) == "chapters":
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

from tracelog import normalize_usage


def advisor_aware_usage(resp):
    """Top-level usage counts the executor ONLY. Add the advisor iterations."""
    base = normalize_usage(getattr(resp, "usage", None))
    extra = []
    for it in getattr(resp.usage, "iterations", []) or []:
        if getattr(it, "type", "") == "advisor_message":
            extra.append((getattr(it, "model", "unknown"),
                          normalize_usage(getattr(it, "usage", None))))
    return base, extra          # price these SEPARATELY, at different rates
