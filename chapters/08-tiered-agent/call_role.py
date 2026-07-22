"""call_role.py - per-role model assignment, read from config. Chapter 8.

The tier vocabulary stays small and boring: planner, worker, verifier. If you
find yourself adding a fourth role, ask whether it's really a role or just a
second worker.

Tagging the trace `changelog-agent:worker` means rollup.py breaks the agent
down by tier with no new tooling.
"""
import json, os, sys

_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(_CHAPTERS) == "chapters":
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

from providers import complete
from tracelog import traced

ROLES_PATH = os.environ.get("ROLES", os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "roles.json"))
with open(ROLES_PATH) as _f:
    ROLES = json.load(_f)                  # the file from step 1

def call_role(agent, role, messages, roles=ROLES):
    cfg = roles[agent][role]
    return traced(complete, model=cfg["model"],
                  task=f"{agent}:{role}",          # role-level attribution
                  prompt_text=messages[-1]["content"],
                  alias=cfg["model"], messages=messages,
                  max_tokens=cfg["max_tokens"])
