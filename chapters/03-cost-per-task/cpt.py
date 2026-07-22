#!/usr/bin/env python3
"""cpt.py - dollars per finished task, from numbers you measured. Chapter 3.

    python3 cpt.py --from-rollup rollup.json        # your ch04 numbers
    python3 cpt.py --model opus 5 25 18000 3000 1.05 \\
                   --model cheap 2 10 34000 5700 1.30
    python3 cpt.py --demo                           # the book's illustrative pair

The default is your numbers. --demo exists so you can watch the ordering flip
before you have any; it prints two made-up rows and says so.
"""
import argparse, json, sys


def cost_per_task(in_rate, out_rate, tok_in, tok_out, attempts=1.0):
    """in_rate/out_rate are $ per 1M tokens. attempts includes retries."""
    per_attempt = (tok_in * in_rate + tok_out * out_rate) / 1_000_000
    return per_attempt * attempts

def compare(rows):
    hdr = f"{'MODEL':<18}{'$/1M in':>9}{'TOK/TASK':>10}{'TRIES':>7}{'$/TASK':>9}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        r["cpt"] = cost_per_task(r["in_rate"], r["out_rate"],
                                 r["tok_in"], r["tok_out"], r["attempts"])
        print(f"{r['model']:<18}{r['in_rate']:>9.2f}"
              f"{r['tok_in'] + r['tok_out']:>10,}{r['attempts']:>7.2f}{r['cpt']:>9.4f}")

    by_token = sorted(rows, key=lambda r: r["in_rate"])[0]["model"]
    by_task  = sorted(rows, key=lambda r: r["cpt"])[0]["model"]
    print(f"\ncheapest per token: {by_token}")
    print(f"cheapest per task:  {by_task}")
    print("SAME" if by_token == by_task
          else ">>> THE ORDERING FLIPS. per-token price would have picked wrong.")

# The book's two rows. Illustrative, and reachable only behind --demo.
DEMO = [
    {"model": "expensive", "in_rate": 5.00, "out_rate": 25.00,
     "tok_in": 18_000, "tok_out": 3_000, "attempts": 1.05},
    {"model": "cheaper",   "in_rate": 2.00, "out_rate": 10.00,
     "tok_in": 34_000, "tok_out": 5_700, "attempts": 1.30},
]

def _from_rollup(path):
    """Rows out of a rollup you produced. One row per model in the file.

    Expects a list of objects carrying model, in_rate, out_rate, tok_in,
    tok_out and attempts - the shape rollup.py prints, written down.
    """
    with open(path) as f:
        raw = json.load(f)
    rows = raw["rows"] if isinstance(raw, dict) else raw
    out = []
    for r in rows:
        try:
            out.append({"model": r["model"], "in_rate": float(r["in_rate"]),
                        "out_rate": float(r["out_rate"]), "tok_in": int(r["tok_in"]),
                        "tok_out": int(r["tok_out"]),
                        "attempts": float(r.get("attempts", 1.0))})
        except KeyError as e:
            sys.exit(f"{path}: a row is missing {e}. Every row needs model, "
                     f"in_rate, out_rate, tok_in, tok_out (attempts defaults to 1.0).")
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="dollars per finished task")
    ap.add_argument("--model", nargs=6, action="append", metavar=
                    ("NAME", "IN_RATE", "OUT_RATE", "TOK_IN", "TOK_OUT", "ATTEMPTS"),
                    help="one measured model. repeat it.")
    ap.add_argument("--from-rollup", metavar="FILE",
                    help="JSON list of measured rows")
    ap.add_argument("--demo", action="store_true",
                    help="the book's two illustrative rows")
    a = ap.parse_args()

    if a.model:
        rows = [{"model": m[0], "in_rate": float(m[1]), "out_rate": float(m[2]),
                 "tok_in": int(m[3]), "tok_out": int(m[4]), "attempts": float(m[5])}
                for m in a.model]
    elif a.from_rollup:
        rows = _from_rollup(a.from_rollup)
    elif a.demo:
        rows = [dict(r) for r in DEMO]
        print("ILLUSTRATIVE ROWS - these are the book's, not a measurement.")
        print("Replace them with YOUR numbers from ch04: --model or --from-rollup.\n")
    else:
        sys.exit(__doc__.strip() + "\n\nGive it --model, --from-rollup or --demo.")

    if len(rows) < 2:
        sys.exit("give it at least two models - one row cannot flip an ordering.")
    compare(rows)
