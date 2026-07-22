# gotchas

things that fail quietly. most of these cost me a day each, in rough order of how long it took me
to work out what was happening.

## `cost_usd` is null on every routed call and the saving vanishes from your accounting

the router dispatches on the alias (`ds-flash`). the logger prices by looking that same string up
in `RATES`. key `RATES` by the provider's own id (`deepseek-v4-flash`) and every routed call
prices at nothing while appearing to work perfectly: right answer, fast, `ok: true`, no cost.
chapter 10's whole page is built off that column.

one routed call, then:

```
tail -1 traces.jsonl | python3 -m json.tool | grep cost_usd
```

a number means you're fine. `null` means your rate table and your catalog disagree about what a
model is called.

## the cache counters come back as None, not zero

when caching is off. `None` propagates happily through a dict and then blows up two functions
later on an arithmetic op with no obvious connection to caching. that's what the `or 0` is doing
in `record_usage.py`, and it looks pointless until the day it isn't.

## TypeError: multiple values for keyword argument 'model'

on your very first traced call. `traced()` takes `model=` for itself, to price the call, and
forwards the rest to the provider. bind the model onto the callable first:

```python
resp = traced(partial(client.messages.create, model=M), model=M, ...)
```

pass `model` to both and you get the TypeError. pass it to neither and the API never receives one.
`complete()` takes it as `alias=` for the same reason.

## a 400 from the provider the moment you add a correlation id

`traced()` forwards every unknown keyword straight to the API, which is right for `max_tokens` and
very wrong for `job=`. trace-only fields go through `meta=`, which lands them on the row instead:

```python
traced(complete, model=m, task=t, prompt_text=p, meta={"job": job}, ...)
```

there's a test pinning that `meta` reaches the row and does *not* reach the provider.

## your escalation rate halves itself and tells you everything is fine

the denominator is routed *attempts*, not calls. an escalation is a second call on the same job,
so counting it in the denominator makes a 20% rate read as 10%. the block at the bottom of
`rollup.py` splits on `:escalated` for exactly this reason.

## you run the harness five times and end up with one scorecard

`--out` defaults to `scorecard.json`. chapter 7 builds the routing table by reading the whole
`scorecards/` directory, so every run needs its own file:

```
--out scorecards/changelog__ds-flash.json
```

## ZeroDivisionError in report() when every token counter came back zero

this one bit me while writing the tests for it:

```
  File "chapters/05-quality-delta/harness.py", line 118, in report
    f"(candidate costs {cand['cpt']/base['cpt']:.1%} of baseline)")
ZeroDivisionError: float division by zero
```

a baseline that cost nothing means your provider names the usage fields something `FIELD_ALIASES`
doesn't know yet, so all four counters normalised to zero. it prints `nan%` now and leaves you
alive to go and add the alias. the line above it already had the guard; the line below didn't.

## clearing the scorecard directory is not enough on its own

`remeasure.py` empties `scorecards/` after rotating it into `prev`, so a candidate that fails to
score can't leave last month's card behind driving this month's answer. but the diff loop iterates
the tasks it *found*, so the first version of that fix printed
`no change. Every task type keeps the model it had.` about a task type where nothing had scored at
all, which is the same lie in a new place. it gets its own `NOT RE-MEASURED THIS RUN` block now,
and the recommendation file leaves it out entirely.

## import router fails with ModuleNotFoundError: No module named 'openai'

even though `route()` is a dictionary lookup with no network in it. `router.py` imports
`providers.py`, which imports the client at module level. same for `guard.py`, `shadow.py` and
`call_role.py`. install `openai` or don't import those four. the other sixteen files are stdlib.

`sdk_patch.py` is worse and deliberately so: it needs `anthropic` at import time, because
monkeypatching a client you haven't got is meaningless. it compiles fine and won't import. don't
put it in a startup path.

## routes.json is not in this repository and never will be

`router.py` raises `FileNotFoundError` on a fresh clone. that's correct. generate the table from
your own scorecards. a router dispatching on somebody else's evidence is worse than no router,
because it looks like it's working.
