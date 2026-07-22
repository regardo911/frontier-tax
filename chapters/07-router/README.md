# Chapter 7: the router

Generate `routes.json` from your own scorecards. Don't hand-write it.

```
python3 chapters/07-router/build_table.py            # reads scorecards/*.json
```

With no scorecards of your own it falls back to `fixtures/scorecards.sample/`, says so, and writes
a table you can read but must not route on. `router.py` has no such fallback, on purpose: a router
dispatching on synthetic evidence is the exact failure this chapter exists to prevent.

`fixtures/routes.sample.json` isn't hand-written either. It's exactly what the command above
prints from `fixtures/scorecards.sample/`, and a test fails if the two ever drift.

## One difference from the printed listing

`rule_from()` has a second branch. A candidate can clear `MIN_REL_PASS` and still lose on cost.
That's the Sonnet 5 case from Chapter 3, and when it happens the printed version announces
"no candidate cleared the bar" about a candidate that cleared it. That sentence is the `why`
field, and Chapter 10 prints the `why` field onto the page you hand a skeptic, so it has to be
true. This one says:

```
claude-sonnet-5 cleared the bar at rel_pass 0.97 but cost 107.7% of baseline, n=40
```

On a candidate genuinely under the bar, the output is the printed one, unchanged. A test locks in
both outputs.
