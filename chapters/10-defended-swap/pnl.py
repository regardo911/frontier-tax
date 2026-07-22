#!/usr/bin/env python3
"""pnl.py - one page a skeptic can check. Every number computed, none typed. Chapter 10.

    python3 pnl.py traces_before.jsonl traces_after.jsonl 14 14

It reads routes.json and scorecards/*.json out of the directory you run it in.
If neither is there it falls back to the bundled synthetic sample and says so
on the first line of output.
"""
import json, os, sys, glob
from collections import defaultdict

DAYS = 30

def load(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]

def by_task(rows, days):
    """Monthly cost and call volume per task type, projected from the sample."""
    agg = defaultdict(lambda: {"cost": 0.0, "calls": 0})
    for r in rows:
        if not r.get("ok"):
            continue
        t = r["task"].split(":")[0]          # fold agent roles into one line
        agg[t]["cost"] += r.get("cost_usd") or 0.0
        agg[t]["calls"] += 1
    scale = DAYS / days
    return {t: {"cost": v["cost"] * scale, "calls": round(v["calls"] * scale)}
            for t, v in agg.items()}

def rates(routes, pattern="scorecards/*.json"):
    """Pass rates before/after, straight from the scorecards. Never typed.

    Two traps this has to avoid, and both of them lie in your favour or
    against you at random:
      1. A task with THREE candidates has three scorecards. Pick the one for
         the model you actually routed to, not whichever the glob yields last.
      2. A task that STAYED on the frontier did not change quality. Its
         "after" is its own baseline, not the rate of the candidate you
         rejected.
    """
    cards = defaultdict(list)
    for p in glob.glob(pattern):
        with open(p) as f:
            c = json.load(f)
        cards[c["task"]].append(c)

    out = {}
    for task, cs in cards.items():
        base = cs[0]["baseline"]
        chosen = routes.get(task, {}).get("chosen")
        out[task] = {"before": (base["rate"], base["n"])}
        if chosen is None or chosen == base["model"]:
            out[task]["after"] = (base["rate"], base["n"])      # stayed put
            continue
        match = next((c for c in cs if c["candidate"]["model"] == chosen), None)
        if match is None:
            out[task]["after"] = None                           # say so, don't guess
        else:
            out[task]["after"] = (match["candidate"]["rate"], match["candidate"]["n"])
    return out

def report(before, after, pr, routes, days_before, days_after):
    print(f"\nSWAP DECISION{'':>36}before: {days_before}d   after: {days_after}d\n")
    print("CURRENT vs ROUTED, BY TASK TYPE")
    hdr = (f"{'task':<14}{'calls/mo':>10}{'before':>10}{'after':>10}{'saved':>9}"
           f"{'pass before':>14}{'pass after':>13}")
    print(hdr)
    tb = ta = 0.0
    for t in sorted(before, key=lambda k: -before[k]["cost"]):
        b = before[t]["cost"]
        a = after.get(t, {}).get("cost", b)   # not routed = unchanged
        tb += b; ta += a
        pb, pa = pr.get(t, {}).get("before"), pr.get(t, {}).get("after")
        f = lambda x: f"{x[0]:.0%} (n={x[1]})" if x else "not scored"
        print(f"{t:<14}{before[t]['calls']:>10,}{b:>10.2f}{a:>10.2f}{b-a:>9.2f}"
              f"{f(pb):>14}{f(pa):>13}")
    pct = (ta / tb - 1) if tb else 0
    print(f"{'':14}{'':>10}{'-'*9:>10}{'-'*9:>10}{'-'*8:>9}")
    print(f"{'':14}{'':>10}{tb:>10.2f}{ta:>10.2f}{tb-ta:>9.2f}   ({pct:+.1%})\n")

    print("WHAT MOVED, AND WHY")
    for t in sorted(before, key=lambda k: -before[k]["cost"]):
        r = routes.get(t)
        if not r:
            print(f"{t:<14} -> not routed        no scorecard yet")
        elif r["fallback"] is None:
            print(f"{t:<14} -> STAYED on {r['chosen']:<10} {r['why']}")
        else:
            print(f"{t:<14} -> {r['chosen']:<18} {r['why']}")

    scored = [t for t in pr if pr[t].get("before") and pr[t].get("after")]
    if scored:
        w = lambda k: (sum(pr[t][k][0] * before.get(t, {}).get("calls", 0) for t in scored)
                       / max(sum(before.get(t, {}).get("calls", 0) for t in scored), 1))
        print(f"\nQUALITY\nweighted pass rate before   {w('before'):.1%}"
              f"\nweighted pass rate after    {w('after'):.1%}"
              f"\ndelta                       {(w('after')-w('before'))*100:+.1f} points")

    print(f"\nBREAK-EVEN ON LOCAL\nrouted spend ${ta:.2f}/mo. Hardware quote you supply: $______")
    print("payback_months = capex / (routed_spend - local_running_cost)")
    print("local_running_cost = power x your electricity rate + maintenance"
          " + hours x your rate")
    print("  your electricity rate, your hours, your hourly rate:"
          " unknown, you must observe these")
    print("\nWAS THE SAMPLE PERIOD REPRESENTATIVE?  unknown, you must observe this."
          "\n  If it wasn't, say so on the page before you send it.")

def _fixture(name):
    """The bundled synthetic sample, if this file is still inside the repo."""
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = os.path.join(repo, "fixtures", name)
    return p if os.path.exists(os.path.dirname(p)) else None

if __name__ == "__main__":
    if len(sys.argv) < 5:
        sys.exit("usage: pnl.py <traces_before> <traces_after> <days_before> <days_after>")
    b, a = load(sys.argv[1]), load(sys.argv[2])
    db, da = int(sys.argv[3]), int(sys.argv[4])
    routes_path = os.environ.get("ROUTES", "routes.json")
    cards = "scorecards/*.json"
    if not os.path.exists(routes_path):
        sample_routes = _fixture("routes.sample.json")
        if not sample_routes or not os.path.exists(sample_routes):
            sys.exit(f"no {routes_path} here - generate one with build_table.py first")
        routes_path, cards = sample_routes, _fixture("scorecards.sample/*.json")
        print(f"\nno {os.environ.get('ROUTES', 'routes.json')} in this directory, so this "
              f"page is drawn from the bundled SYNTHETIC sample:"
              f"\n  routes:     {os.path.relpath(routes_path)}"
              f"\n  scorecards: {os.path.relpath(cards)}"
              f"\nThe format is real. The numbers belong to nobody.")
    with open(routes_path) as f:
        routes = json.load(f)
    report(by_task(b, db), by_task(a, da), rates(routes, cards), routes, db, da)
