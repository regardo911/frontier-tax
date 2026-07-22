#!/usr/bin/env python3
"""context_profile.py - where are your tokens, per task type? Chapter 9.

    python3 context_profile.py traces.jsonl

Read the IN:OUT column and nothing else. Above 10 you're input-dominated and
your levers are caching and trimming. Near or under 3 you're output-dominated,
caching will do almost nothing, and a cheaper model helps you most. Most people
guess this wrong about their own workload. Four minutes here saves you a
weekend caching a bill that's 80% output.
"""
import json, statistics, sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "traces.jsonl"
with open(path) as f:
    rows = [json.loads(l) for l in f if l.strip()]
by = defaultdict(list)
for r in rows:
    if not r.get("ok"):
        continue
    total_in = (r["input_tokens"] + r["cache_read_input_tokens"]
                + r["cache_creation_input_tokens"])
    by[r["task"]].append((total_in, r["output_tokens"],
                          r["cache_read_input_tokens"]))

print(f"{'TASK':<16}{'CALLS':>6}{'MED IN':>9}{'MED OUT':>9}{'IN:OUT':>8}{'CACHED':>8}")
for task, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
    ins  = statistics.median(x[0] for x in v)
    outs = statistics.median(x[1] for x in v)
    cached = sum(x[2] for x in v) / max(sum(x[0] for x in v), 1)
    print(f"{task:<16}{len(v):>6}{ins:>9,.0f}{outs:>9,.0f}"
          f"{ins/max(outs,1):>8.1f}{cached:>7.0%}")
