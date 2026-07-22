#!/usr/bin/env python3
"""diet.py - apply one cut, score it, keep it or kill it. Chapter 9.

One cut at a time. Two changes at once and you learn nothing about either.

    # capture traces, apply the cut, capture again, then:
    python3 diet.py --name "four-layer prompt" --task changelog \
        --model claude-opus-4-8 \
        --before traces_before.jsonl --after traces_after.jsonl

score() shells out to harness.py, which replays against a model. This spends
your money - a 40-trace run twice, so budget two of them per cut.
"""
import argparse, json, os, subprocess, sys

_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_IN_REPO = os.path.basename(_CHAPTERS) == "chapters"

def _sibling(chapter, name):
    """The book runs from one flat directory; this repo lays files out by
    chapter. Resolve the repo path if there is one, else the bare name."""
    p = os.path.join(_CHAPTERS, chapter, name)
    return p if _IN_REPO and os.path.exists(p) else name

def score(task, model, traces, limit=40):
    """Run the ch05 harness and read its scorecard back."""
    out = f"diet_{task}.json"
    # No --rescore-baseline here. score() reads the candidate row only, so
    # re-running the baseline live would double the spend of every cut you
    # test and then discard the answer.
    subprocess.run([sys.executable, _sibling("05-quality-delta", "harness.py"),
                    traces, "--task", task,
                    "--baseline", model, "--candidate", model,
                    "--limit", str(limit), "--out", out], check=True)
    with open(out) as f:
        c = json.load(f)["candidate"]
    return {"rate": c["rate"], "cpt": c["cpt"], "n": c["n"]}

def verdict(before, after, tol=0.02):
    """Keep only if tokens/dollars fell AND pass rate held within tolerance."""
    cheaper = after["cpt"] < before["cpt"]
    held    = after["rate"] >= before["rate"] - tol
    return ("KEEP" if cheaper and held else
            "REJECT: quality" if cheaper else
            "REJECT: no saving")

def log(name, task, before, after, path="diet-changelog.md"):
    v = verdict(before, after)
    # NEGATIVE means cheaper. Get this sign backwards and your changelog
    # cheerfully records every saving as a cost increase.
    delta = after["cpt"] / before["cpt"] - 1 if before["cpt"] else 0
    with open(path, "a") as f:
        f.write(f"- **{name}** on `{task}` -> **{v}** "
                f"(cost {delta:+.1%}, pass {before['rate']:.0%} -> "
                f"{after['rate']:.0%}, n={after['n']})\n")
    print(f"{name:<28}{task:<14}{v}")
    return v

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="score one cut, keep it or kill it")
    ap.add_argument("--name", required=True, help="what you changed, in your words")
    ap.add_argument("--task", required=True, help="the task type to score it on")
    ap.add_argument("--model", required=True, help="the model you're running today")
    ap.add_argument("--before", required=True, help="traces captured before the cut")
    ap.add_argument("--after", required=True, help="traces captured after it")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--out", default="diet-changelog.md")
    a = ap.parse_args()

    before = score(a.task, a.model, a.before, a.limit)
    after  = score(a.task, a.model, a.after, a.limit)
    log(a.name, a.task, before, after, a.out)
    print(f"appended to {a.out}")
