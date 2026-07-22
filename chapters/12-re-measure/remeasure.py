#!/usr/bin/env python3
"""remeasure.py - re-score every candidate, diff against last time, rebuild routes.
Chapter 12.

  python3 remeasure.py traces.jsonl

Point it at a RECENT slice of your trace file, not the original ch04 capture.
Your work changes shape, and a re-measurement against a stale task distribution
will confidently tell you about a workload you no longer have.

This replays every candidate against every task. It spends money.
"""
import json, os, subprocess, sys, glob, shutil
from collections import defaultdict

CANDIDATES = ["ds-flash", "ds-pro", "glm-4-6", "glm-5-2", "local-small"]
BASELINE   = os.environ.get("DEFAULT_MODEL", "claude-opus-4-8")
TASKS      = ["changelog", "code-review", "classify"]
PREV, CUR  = "scorecards/prev", "scorecards"

_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IN_REPO = os.path.basename(_CHAPTERS) == "chapters"
if _IN_REPO:
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

from tracelog import RATES

def _sibling(chapter, name):
    """The book runs from one flat directory; this repo lays files out by
    chapter. Resolve the repo path if there is one, else the bare name."""
    p = os.path.join(_CHAPTERS, chapter, name)
    return p if _IN_REPO and os.path.exists(p) else name

def rescore(traces, limit=40):
    """Re-score every candidate. Returns the (task, candidate) pairs that failed.

    CUR is emptied after it rotates into PREV. Copy it forward without
    clearing it and last month's scorecard survives into this month's
    directory, where it still drives the recommendation - so a run in which
    every candidate for a task failed to score prints its usual "no change"
    and hands you a route nobody re-measured. That is the silent decay this
    whole chapter exists to catch.
    """
    failed = []
    if os.path.isdir(CUR):
        shutil.rmtree(PREV, ignore_errors=True)
        shutil.copytree(CUR, PREV, ignore=shutil.ignore_patterns("prev"))
        for stale in glob.glob(os.path.join(CUR, "*.json")):
            os.remove(stale)
    os.makedirs(CUR, exist_ok=True)
    for task in TASKS:
        for cand in CANDIDATES:
            out = f"{CUR}/{task}__{cand}.json"
            try:
                subprocess.run([sys.executable,
                                _sibling("05-quality-delta", "harness.py"), traces,
                                "--task", task, "--baseline", BASELINE,
                                "--candidate", cand, "--limit", str(limit),
                                "--out", out], check=True,
                               stdout=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                print(f"  ! {task}/{cand} failed to score; leaving it out")
                failed.append((task, cand))
    return failed

def chosen(dirname):
    """Read a routes.json-shaped answer out of a scorecard directory.

    build_table.py always writes routes.json, and routes.json is the file your
    router loads. So snapshot the live one and put it back. Skip this and a
    scheduled run silently re-promotes every task type at 3am, which is the one
    thing this script exists not to do.
    """
    if not os.path.isdir(dirname) or not glob.glob(os.path.join(dirname, "*.json")):
        return {}
    live = "routes.json"
    backup = shutil.copy(live, live + ".live") if os.path.exists(live) else None
    try:
        subprocess.run([sys.executable, _sibling("07-router", "build_table.py"),
                        f"{dirname}/*.json"],
                       check=True, stdout=subprocess.DEVNULL)
        with open(live) as f:
            table = {t: r["chosen"] for t, r in json.load(f).items()}
    finally:
        if backup:
            shutil.move(backup, live)
        elif os.path.exists(live):
            os.remove(live)
    return table

def main(traces):
    # Read LAST run's answer out of CUR before rescore() overwrites it.
    # Reading it from PREV instead looks equivalent and is not: rescore()
    # rotates CUR into PREV, so you would be comparing against the run
    # before last and every change would be reported a month late.
    before = chosen(CUR) if glob.glob(f"{CUR}/*.json") else {}
    failed = rescore(traces)
    after = chosen(CUR)

    lost = defaultdict(list)
    for task, cand in failed:
        lost[task].append(cand)
    unmeasured = [t for t in TASKS if t not in after]
    partial = [t for t in after if t in lost]

    changes = [(t, before.get(t), after[t]) for t in after
               if before.get(t) != after[t]]
    if not before:
        print("first run - nothing to diff against. Baseline recorded.")
    elif changes:
        print(f"{len(changes)} routing change(s):\n")
        for task, was, now in changes:
            print(f"  {task:<16}{was or '(new)':<20} -> {now}")
        print("\nreview these before deploying: is the delta worth the migration,")
        print("does the guardrail still catch this model, is it on the keep-list?")
    elif unmeasured:
        # "every task type keeps the model it had" would be a lie here.
        print(f"no change across the {len(after)} task type(s) that were re-measured.")
    else:
        print("no change. Every task type keeps the model it had.")

    if unmeasured:
        print("\nNOT RE-MEASURED THIS RUN - no candidate scored, so there is no")
        print("recommendation for these and last run's is NOT carried forward:")
        for t in unmeasured:
            print(f"  {t:<16}{', '.join(lost.get(t)) or 'no scorecards'}")
    if partial:
        print("\nscored on a partial candidate list:")
        for t in partial:
            print(f"  {t:<16}failed: {', '.join(lost[t])}")

    with open("routes_recommended.json", "w") as f:
        json.dump(after, f, indent=2)
    print(f"\nwrote routes_recommended.json ({len(after)} task types)")

if __name__ == "__main__":
    # ch12's safety net: fail loudly on anything unpriced rather than guessing.
    # A fresh clone stops here, and that is right - the aliases in CANDIDATES
    # are the ones you decided to route on, and only you know what they cost.
    missing = [m for m in CANDIDATES + [BASELINE] if m not in RATES]
    if missing:
        sys.exit(f"no rate for {missing}. Update RATES before scoring.")
    main(sys.argv[1] if len(sys.argv) > 1 else "traces.jsonl")
