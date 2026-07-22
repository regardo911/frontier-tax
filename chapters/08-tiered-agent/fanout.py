"""fanout.py - workers return a status, and the join refuses to proceed on
silence. Chapter 8.

The failure this exists for: worker three times out, the other three succeed,
the verifier gets three good summaries and one empty string, and it writes
clean confident release notes covering three repositories out of four. Nothing
errors. The output is wrong in a way that looks exactly like the output being
right.
"""
import os, sys

_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(_CHAPTERS) == "chapters":
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

from tracelog import text_of


def run_worker(agent, slice_id, messages):
    """A worker result is never a bare string. It is a labelled outcome."""
    from call_role import call_role
    try:
        resp = call_role(agent, "worker", messages)
        text = text_of(resp)
    except Exception as e:
        return {"slice": slice_id, "status": "error",
                "detail": f"{type(e).__name__}: {e}", "text": ""}
    if not text.strip():
        return {"slice": slice_id, "status": "empty", "detail": "", "text": ""}
    return {"slice": slice_id, "status": "ok", "detail": "", "text": text}

class IncompleteFanOut(RuntimeError):
    def __init__(self, missing, absent):
        super().__init__(f"{len(missing)} failed, {len(absent)} never returned")
        self.missing, self.absent = missing, absent

def join(results, plan):
    """Never hand the verifier a hole it cannot see."""
    missing = [r for r in results if r["status"] != "ok"]
    got = {r["slice"] for r in results}
    absent = [s for s in plan["slices"] if s not in got]   # never returned at all
    if missing or absent:
        raise IncompleteFanOut(missing=missing, absent=absent)
    return "\n\n".join(r["text"] for r in sorted(results, key=lambda r: r["slice"]))
