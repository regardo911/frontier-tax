#!/usr/bin/env python3
"""subs_vs_api.py - subscription or metered API, from your own traces. Chapter 10.

    python3 subs_vs_api.py traces.jsonl

Measure at least two weeks. One unusual week will lie to you in either
direction, and the weekly limits mean a single week isn't a representative
cycle anyway.
"""
import collections, json, os, sys

# Published plan prices. They move - check the pricing page. Override with
# PLANS="Pro:20,Max 5x:100,Max 20x:200" if yours differ.
PLANS = [(t.split(":")[0], float(t.split(":")[1]))
         for t in os.environ["PLANS"].split(",")] if os.environ.get("PLANS") else [
    ("Pro", 20), ("Max 5x", 100), ("Max 20x", 200)]

path = sys.argv[1] if len(sys.argv) > 1 else "traces.jsonl"
with open(path) as f:
    rows = [json.loads(l) for l in f if l.strip()]
days = collections.defaultdict(float)
for r in rows:
    if r.get("cost_usd"):
        days[int(r["ts"] // 86400)] += r["cost_usd"]

n = len(days)
if not n:
    sys.exit(f"{path}: no priced rows. If cost_usd is null everywhere, your "
             f"model strings aren't in RATES.")
total = sum(days.values())
proj = total / n * 30
top = max(PLANS, key=lambda p: p[1])[1]
print(f"{n} days measured, ${total:.2f} at API rates -> ${proj:.2f}/month projected")
print(f"days over ${top/30:.2f} (the ${top:.0f} plan's daily share): "
      f"{sum(1 for v in days.values() if v > top/30)} of {n}")
for tier, price in PLANS:
    print(f"  {tier:<8} ${price:<4.0f} -> {'API is cheaper' if proj < price else 'plan is cheaper'}"
          f"  (ratio {proj/price:.2f}x)")

if n < 14:
    print(f"\n{n} days is not enough. Come back at 14.")
print("\nwhether a plan's session and weekly caps would absorb your busiest days:"
      "\n  unknown, you must observe this. A monthly average can recommend a plan"
      "\n  that fails you on exactly the days you need it.")
