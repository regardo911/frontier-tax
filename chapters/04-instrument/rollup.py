#!/usr/bin/env python3
"""rollup.py - what does each kind of work actually cost you? Chapter 4.

    python3 rollup.py traces.jsonl

The escalation block at the bottom is ch11's. It only has something to say
once guard.py has written a :escalated row.
"""
import json, sys
from collections import defaultdict

with open(sys.argv[1] if len(sys.argv) > 1 else "traces.jsonl") as f:
    rows = [json.loads(l) for l in f if l.strip()]
agg = defaultdict(lambda: defaultdict(float))
for r in rows:
    a = agg[r["task"]]
    a["calls"]  += 1
    a["fails"]  += 0 if r["ok"] else 1
    a["tok_in"] += r["input_tokens"] + r["cache_read_input_tokens"] \
                 + r["cache_creation_input_tokens"]
    a["tok_out"] += r["output_tokens"]
    a["cached"]  += r["cache_read_input_tokens"]
    a["cost"]    += r["cost_usd"] or 0.0
    a["ms"]      += r["ms"]

hdr = (f"{'TASK':<14}{'CALLS':>6}{'FAIL':>5}{'TOK IN':>10}{'TOK OUT':>9}"
       f"{'CACHED':>8}{'COST':>9}{'$/CALL':>9}{'MS':>7}")
print(hdr); print("-" * len(hdr))
for task, a in sorted(agg.items(), key=lambda kv: -kv[1]["cost"]):
    n = a["calls"]
    print(f"{task:<14}{int(n):>6}{int(a['fails']):>5}{int(a['tok_in']):>10,}"
          f"{int(a['tok_out']):>9,}{a['cached']/max(a['tok_in'],1):>7.0%}"
          f"{a['cost']:>9.4f}{a['cost']/n:>9.4f}{int(a['ms']/n):>7}")
print(f"\n{len(rows)} traces, ${sum(r['cost_usd'] or 0 for r in rows):.4f} total")

# The denominator is ROUTED ATTEMPTS, not calls. An escalation is a second
# call on the same job; counting it in the denominator halves your rate and
# tells you everything is fine while it is not.
esc = defaultdict(lambda: [0, 0])          # [escalated, routed] per base task
for r in rows:
    base = r["task"].split(":")[0]
    if r["task"].endswith(":escalated"):
        esc[base][0] += 1
    else:
        esc[base][1] += 1
if any(e for e, _ in esc.values()):
    print()
    for task, (e, routed) in sorted(esc.items()):
        if e:
            print(f"{task:<16}{e:>5}/{routed:<6}{e/max(routed,1):>7.1%} escalated")
