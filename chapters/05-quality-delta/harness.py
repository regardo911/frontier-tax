#!/usr/bin/env python3
"""harness.py - replay YOUR traces against a candidate, score, report. Chapter 5.

  python3 harness.py traces.jsonl --task code-review \
      --baseline claude-opus-4-8 --candidate deepseek-v4-flash --limit 40

Two ways to reach a candidate, both from the book. Set BASE_URL (and API_KEY)
and the replay goes straight to that endpoint with the model string you passed.
Leave BASE_URL unset and it goes through ch06's complete(), which resolves an
alias like "ds-flash" to a provider and to that provider's own model id.

Replaying costs money. A 40-trace run is usually under a dollar.
"""
import argparse, json, math, os, sys, time

# the book runs everything from one flat directory. this repo lays the files
# out by chapter, so put the sibling chapter folders on the path. copy this
# file into a flat directory on its own and you can delete these three lines.
_CHAPTERS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(_CHAPTERS) == "chapters":
    sys.path[:0] = [os.path.join(_CHAPTERS, d) for d in sorted(os.listdir(_CHAPTERS))]

from tasks import TASKS
from tracelog import normalize_usage, price

def wilson(k, n, z=1.96):
    """95% confidence interval for a pass rate. See ch03."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))

def load(path, task, limit, model=None):
    """Your traces. Never mine - this file ships with no data in it.

    `model` restricts the set to rows that model produced, and the caller sets
    it whenever the baseline is scored from its own logged output. Without it,
    every matching row gets priced at the baseline's rate no matter which model
    answered it - which is fine on a ch04 capture, where everything is the
    frontier, and wrong the moment ch07 promotes a task and the file starts
    carrying cheap rows. The pass rate looks the same either way; the $/TASK
    column is off by the whole size of the price gap.
    """
    out = []
    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("task") == task and r.get("ok") and r.get("input"):
                if model is not None and r.get("model") != model:
                    continue
                out.append(r)
    if not out:
        sys.exit(f"no usable traces for task={task!r} in {path}"
                 + (f" from model={model!r}" if model else ""))
    return out[:limit]

def run_one(client, model, trace, max_tokens):
    """One replay. Returns (text, usage_dict, seconds)."""
    t0 = time.perf_counter()
    if client is None:                      # ch06: resolve the alias instead
        from providers import complete
        resp = complete(model, messages=[{"role": "user", "content": trace["input"]}],
                        max_tokens=max_tokens)
    else:
        resp = client.chat.completions.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": trace["input"]}],
        )
    secs = time.perf_counter() - t0
    return resp.choices[0].message.content or "", \
           normalize_usage(resp.usage), secs

def score_model(client, model, traces, check, max_tokens, reuse_baseline=False):
    passed, cost, secs, errors = 0, 0.0, 0.0, 0
    for t in traces:
        if reuse_baseline:                 # score what you already paid for
            text, usage = t["output"], {k: t.get(k, 0) for k in
                ("input_tokens", "output_tokens",
                 "cache_creation_input_tokens", "cache_read_input_tokens")}
            dt = t.get("ms", 0) / 1000
        else:
            try:
                text, usage, dt = run_one(client, model, t, max_tokens)
            except Exception as e:
                errors += 1                # a failure to answer is a failure
                print(f"  [{model}] {type(e).__name__}: {e}", file=sys.stderr)
                continue
        cost += price(model, usage)
        secs += dt
        try:
            if check(text, t):
                passed += 1
        except Exception as e:             # a predicate that throws is a bug
            sys.exit(f"predicate raised on trace {t.get('id')}: {e}")
    n = len(traces)
    return {"model": model, "n": n, "passed": passed, "errors": errors,
            "rate": passed / n, "cost": cost, "cpt": cost / n,
            "ci": wilson(passed, n), "secs": secs / n}

def report(task, base, cand):
    print(f"\ntask: {task:<18} traces: {base['n']:<6} "
          f"candidate: {cand['model']}\n{'':26}baseline:  {base['model']}\n")
    print(f"{'':<22}{'PASSED':>7}{'RATE':>7}{'95% CI':>15}{'$/TASK':>10}{'TOTAL':>9}")
    for r in (base, cand):
        lo, hi = r["ci"]
        print(f"{r['model'][:21]:<22}{r['passed']:>7}{r['rate']:>6.0%}"
              f"{f'{lo:.0%} - {hi:.0%}':>15}{r['cpt']:>10.4f}{r['cost']:>9.3f}")
    pts = (cand["rate"] - base["rate"]) * 100
    rel = cand["passed"] / base["passed"] if base["passed"] else float("nan")
    # a baseline that cost nothing means every token counter came back zero,
    # which means your provider names those fields something this doesn't know.
    # print nan and point at FIELD_ALIASES rather than dying on a divide.
    dcost = (cand["cpt"] / base["cpt"] - 1) * 100 if base["cpt"] else float("nan")
    ratio = cand["cpt"] / base["cpt"] if base["cpt"] else float("nan")
    print(f"\nquality delta  {pts:+.0f} points  "
          f"(candidate passes {rel:.0%} of baseline's tasks)")
    print(f"cost delta     {dcost:+.1f}%      "
          f"(candidate costs {ratio:.1%} of baseline)")
    overlap = not (cand["ci"][1] < base["ci"][0] or base["ci"][1] < cand["ci"][0])
    print(f"CI overlap     {'yes -> at n=%d this gap is suggestive, not established' % base['n'] if overlap else 'no  -> the gap holds at this sample size'}")
    if cand["errors"] or base["errors"]:
        print(f"\nerrors: baseline {base['errors']}, candidate {cand['errors']} "
              f"(counted as failures)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("traces"); ap.add_argument("--task", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--rescore-baseline", action="store_true",
                    help="re-run the baseline instead of scoring its logged output")
    ap.add_argument("--out", default="scorecard.json")
    a = ap.parse_args()

    client = None
    if os.environ.get("BASE_URL"):                 # any OpenAI-compatible provider
        from openai import OpenAI
        client = OpenAI(base_url=os.environ["BASE_URL"],
                        api_key=os.environ.get("API_KEY", "EMPTY"))

    check = TASKS[a.task]["check"]
    reuse = not a.rescore_baseline
    traces = load(a.traces, a.task, a.limit,
                  model=a.baseline if reuse else None)
    base = score_model(client, a.baseline, traces, check, a.max_tokens,
                       reuse_baseline=reuse)
    cand = score_model(client, a.candidate, traces, check, a.max_tokens)
    report(a.task, base, cand)
    with open(a.out, "w") as f:
        json.dump({"task": a.task, "baseline": base, "candidate": cand},
                  f, indent=2, default=str)
    print(f"\nwrote {a.out}")
