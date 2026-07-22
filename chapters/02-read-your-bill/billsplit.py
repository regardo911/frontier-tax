#!/usr/bin/env python3
"""billsplit.py - turn raw usage records into a line-itemized bill. Chapter 2."""
import json, sys
from collections import defaultdict

# Dollars per 1M tokens (input, output). Confirm against the current
# pricing page before trusting any total; these move.
PRICES = {
    "claude-fable-5":   (10.00, 50.00),
    "claude-opus-4-8":  ( 5.00, 25.00),
    "claude-sonnet-5":  ( 2.00, 10.00),
    "claude-haiku-4-5": ( 1.00,  5.00),
}

CACHE_WRITE_5M = 1.25   # multiplier on base input price
CACHE_WRITE_1H = 2.00
CACHE_READ     = 0.10   # a hit costs 10% of standard input

def line_items(row, ttl="5m"):
    """Return this request's cost split into the four billed components."""
    model = row["model"]
    if model not in PRICES:
        raise KeyError(f"no price for {model!r} - add it to PRICES")
    inp, out = PRICES[model]
    per_tok_in, per_tok_out = inp / 1e6, out / 1e6
    write_mult = CACHE_WRITE_1H if ttl == "1h" else CACHE_WRITE_5M
    return {
        "input":       row["input_tokens"]                * per_tok_in,
        "cache_write": row["cache_creation_input_tokens"] * per_tok_in * write_mult,
        "cache_read":  row["cache_read_input_tokens"]     * per_tok_in * CACHE_READ,
        "output":      row["output_tokens"]               * per_tok_out,
    }

def main(path):
    totals, by_task, task_calls, calls = defaultdict(float), defaultdict(float), defaultdict(int), 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            items = line_items(row)
            for k, v in items.items():
                totals[k] += v
            task = row.get("task", "unlabeled")
            by_task[task] += sum(items.values())
            task_calls[task] += 1     # per-TASK count, not the grand total
            calls += 1

    grand = sum(totals.values())
    print(f"\n{calls} calls, ${grand:.4f} total\n")
    print(f"{'LINE ITEM':<14}{'COST':>10}{'SHARE':>9}")
    for k in ("input", "cache_write", "cache_read", "output"):
        share = 100 * totals[k] / grand if grand else 0
        print(f"{k:<14}{totals[k]:>10.4f}{share:>8.1f}%")
    print(f"\n{'TASK':<16}{'CALLS':>7}{'COST':>10}{'PER CALL':>11}")
    for task, cost in sorted(by_task.items(), key=lambda kv: -kv[1]):
        print(f"{task:<16}{task_calls[task]:>7}{cost:>10.4f}{cost/task_calls[task]:>11.4f}")
    # the charges that never arrive as tokens: search fees, container hours,
    # session runtime. this script reads the usage block, so it cannot see them.
    print("\nnon-token charges on this bill: unknown, you must observe this")
    print("  (search fees, container hours, session runtime - read them off your")
    print("   billing dashboard and add them to the total above)")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "usage.jsonl")
