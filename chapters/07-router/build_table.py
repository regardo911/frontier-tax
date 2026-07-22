#!/usr/bin/env python3
"""build_table.py - turn scorecards into routing rules. Evidence in, rules out. Chapter 7."""
import json, os, sys, glob

MIN_REL_PASS = 0.95      # candidate must pass >=95% of what the baseline passes
REQUIRE_OVERLAP = True   # ...and the gap must not be statistically established

def rule_from(cards):
    """cards: every scorecard.json for ONE task type."""
    baseline = cards[0]["baseline"]
    ranked = [{"model": baseline["model"], "rel_pass": 1.0,
               "cpt": baseline["cpt"], "n": baseline["n"]}]
    for c in cards:
        cand, base = c["candidate"], c["baseline"]
        rel = cand["passed"] / base["passed"] if base["passed"] else 0.0
        overlap = not (cand["ci"][1] < base["ci"][0] or base["ci"][1] < cand["ci"][0])
        ranked.append({"model": cand["model"], "rel_pass": round(rel, 3),
                       "cpt": cand["cpt"], "n": cand["n"], "ci_overlap": overlap})

    eligible = [r for r in ranked
                if r["rel_pass"] >= MIN_REL_PASS
                and (r.get("ci_overlap", True) or not REQUIRE_OVERLAP)]
    ranked.sort(key=lambda r: r["cpt"])
    chosen = min(eligible, key=lambda r: r["cpt"])
    # ch12's drill: the model you promote if this one's provider disappears.
    # It has to have cleared the same bar, so a task with nothing else eligible
    # gets null - which is the honest answer. That work has no hedge.
    second = next((r for r in sorted(eligible, key=lambda r: r["cpt"])
                   if r["model"] != chosen["model"]), None)
    if chosen["model"] == baseline["model"]:
        # Two different reasons the baseline wins, and a skeptic reads this
        # sentence. A candidate that cleared the bar and lost on cost is the
        # ch03 Sonnet 5 case, and calling that "no candidate cleared the bar"
        # is a false line in the audit trail.
        cleared = [r for r in eligible if r["model"] != baseline["model"]]
        if cleared:
            best = min(cleared, key=lambda r: r["cpt"])
            why = (f"{best['model']} cleared the bar at rel_pass "
                   f"{best['rel_pass']:.2f} but cost "
                   f"{best['cpt']/baseline['cpt']:.1%} of baseline, n={best['n']}")
        else:
            best = max((r for r in ranked if r["model"] != baseline["model"]),
                       key=lambda r: r["rel_pass"], default=None)
            why = (f"no candidate cleared the bar; best was "
                   f"{best['rel_pass']:.2f} of baseline" if best else "no candidates scored")
        fallback = None
        breakeven = None
    else:
        why = (f"rel_pass {chosen['rel_pass']:.2f} of baseline at "
               f"{chosen['cpt']/baseline['cpt']:.1%} of cost, n={chosen['n']}")
        fallback = baseline["model"]
        # ch11: routing wins while the escalation rate stays under this.
        breakeven = round(1 - chosen["cpt"] / baseline["cpt"], 4) if baseline["cpt"] else None
    return {"chosen": chosen["model"], "why": why,
            "fallback": fallback,
            "breakeven_escalation_rate": breakeven,
            "second_choice": second["model"] if second else None,
            "ranked": ranked}

if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "scorecards/*.json"
    if len(sys.argv) == 1 and not glob.glob(pattern):
        # nothing measured in this directory yet - fall back to the bundled
        # synthetic sample so the shape is visible before you have your own.
        _repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sample = os.path.join(_repo, "fixtures", "scorecards.sample", "*.json")
        if glob.glob(sample):
            pattern = sample
            print(f"no scorecards/ here - reading the synthetic sample:\n  {pattern}\n")
    by_task = {}
    for path in glob.glob(pattern):
        with open(path) as f:
            c = json.load(f)
        by_task.setdefault(c["task"], []).append(c)
    if not by_task:
        sys.exit("no scorecards found - run harness.py first")
    table = {task: rule_from(cards) for task, cards in by_task.items()}
    with open("routes.json", "w") as f:
        json.dump(table, f, indent=2)
    for task, rule in table.items():
        print(f"{task:<16} -> {rule['chosen']:<20} ({rule['why']})")
    print("\nwrote routes.json")
