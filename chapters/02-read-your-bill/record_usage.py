"""record_usage.py - append every response's usage block to usage.jsonl. Chapter 2.

Not a program. Three lines you paste at your own call site, right after the
response comes back:

    from record_usage import record_usage
    resp = client.messages.create(...)
    record_usage(resp, model=M, task="changelog")

Come back tomorrow and point billsplit.py at the file.
"""
import json, time


def record_usage(resp, model, task="unlabeled", path="usage.jsonl"):
    u = resp.usage
    row = {
        "ts": time.time(),
        "model": model,
        "task": task,
        "input_tokens": getattr(u, "input_tokens", 0),
        "output_tokens": getattr(u, "output_tokens", 0),
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
    }
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")
