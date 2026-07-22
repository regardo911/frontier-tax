# Chapter 5: the harness

**This one spends money.** Replaying a prompt means paying for it, and the book puts a 40-trace run
at usually under a dollar. There is no offline mode and there will never be a stubbed candidate
here: a scorecard produced against a fake model is the exact artifact this book exists to attack.

```
BASE_URL=https://your-provider/v1 API_KEY=sk-... \
python3 chapters/05-quality-delta/harness.py traces.jsonl --task code-review \
    --baseline claude-opus-4-8 --candidate deepseek-v4-flash --limit 40
```

Leave `BASE_URL` unset and the replay goes through `providers.complete()` instead, resolving an
alias like `ds-flash` to a provider and to that provider's own model id. Both paths are in the
book; this file keeps both.

Read your baseline's own pass rate before you look at the candidate at all.

## One difference from the printed listing

`load()` takes an optional `model=`, and `__main__` sets it to the baseline whenever the baseline
is scored from its own logged output. Without the filter, every matching row is priced at the
baseline's rate no matter which model produced it. Fine on a Chapter 4 capture, where everything
is the frontier, and wrong the moment Chapter 7 promotes a task and the file starts carrying cheap
rows. The pass rate is unaffected either way, so the run reads green while `$/TASK`, `TOTAL` and
the cost-delta line are off by the whole size of the price gap, and the error carries into
`build_table.py` and `pnl.py`. Both branches are pinned by a test.
