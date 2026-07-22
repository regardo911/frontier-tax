# Chapter 12: re-measure

```
python3 chapters/12-re-measure/remeasure.py traces.jsonl
```

A fresh clone stops immediately with `no rate for ['ds-flash', ...]`. That's the chapter's own
safety net doing its job: the aliases in `CANDIDATES` are the ones *you* decided to route on,
and until they're in `RATES` the run would price them at nothing. Refresh the rate table off the
provider pricing pages first. That step stays manual on purpose, because a scraper that silently
gets a price wrong is worse than a calendar reminder you actually read.

It writes `routes_recommended.json` and never `routes.json`. A scheduled job should not change
what production routes to; a human promotes it.

## One difference from the printed listing

`rescore()` empties `scorecards/` after copying it into `scorecards/prev`, and it returns the
`(task, candidate)` pairs that failed so `main()` can name them. The printed version copies the
directory forward without clearing it, which means a candidate that fails to score this month
leaves last month's card sitting there, still driving the recommendation, while the run prints
its usual `no change`. A task type nothing scored now gets its own block:

```
NOT RE-MEASURED THIS RUN - no candidate scored, so there is no
recommendation for these and last run's is NOT carried forward:
  code-review     ds-flash, ds-pro, glm-4-6, glm-5-2, local-small
```

A silent "no change" about work nobody measured is the condition this book started by
diagnosing. There's a test pinning it.
