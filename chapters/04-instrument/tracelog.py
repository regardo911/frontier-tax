"""tracelog.py - record every model call with its real cost. Local only. Chapter 4."""
import json, os, time, uuid

TRACE_PATH = os.environ.get("TRACE_PATH", "traces.jsonl")

# Dollars per 1M tokens: (input, output). This table is YOURS to maintain.
# ch12 automates checking it. Confirm against current pricing pages.
RATES = {
    "claude-fable-5":    (10.00, 50.00),
    "claude-opus-4-8":   ( 5.00, 25.00),
    "claude-sonnet-5":   ( 2.00, 10.00),
    "claude-haiku-4-5":  ( 1.00,  5.00),
    "deepseek-v4-flash": ( 0.14,  0.28),
    "GLM-4.6":           ( 0.60,  2.20),
}
CACHE_WRITE_MULT = 1.25    # 5-minute TTL. Use 2.00 if you set ttl="1h".
CACHE_READ_MULT  = 0.10

# Providers disagree about what these fields are called. Try each name in
# order; anything absent lands as 0 and shows up as a zero column later,
# which is your signal to come back here and add the right name.
FIELD_ALIASES = {
    "input_tokens":                ("input_tokens", "prompt_tokens"),
    "output_tokens":               ("output_tokens", "completion_tokens"),
    "cache_creation_input_tokens": ("cache_creation_input_tokens",),
    "cache_read_input_tokens":     ("cache_read_input_tokens", "cached_tokens"),
}

def normalize_usage(usage):
    """Pull the four counters out of whatever shape this provider returned."""
    if usage is None:
        return {k: 0 for k in FIELD_ALIASES}
    def get(name):
        for alias in FIELD_ALIASES[name]:
            v = getattr(usage, alias, None)
            if v is None and isinstance(usage, dict):
                v = usage.get(alias)
            if v is not None:
                return int(v)
        return 0
    return {k: get(k) for k in FIELD_ALIASES}

def price(model, u):
    """Dollars for one call, from token counts. Nobody hands you this number."""
    if model not in RATES:
        raise KeyError(f"no rate for {model!r} - add it to RATES in tracelog.py")
    in_rate, out_rate = RATES[model]
    per_in = in_rate / 1_000_000
    return (u["input_tokens"]                * per_in
          + u["cache_creation_input_tokens"] * per_in * CACHE_WRITE_MULT
          + u["cache_read_input_tokens"]     * per_in * CACHE_READ_MULT
          + u["output_tokens"]               * out_rate / 1_000_000)

def traced(call, *, model, task, prompt_text, path=None, meta=None, **kwargs):
    """Run `call`, log a trace row, return the response UNTOUCHED.

    call(**kwargs) -> provider response object.

    meta goes on the ROW. kwargs go to the PROVIDER. Trace-only fields need
    their own door: send job= to a real API and you get a 400 back.
    """
    t0 = time.perf_counter()
    err, resp = None, None
    try:
        resp = call(**kwargs)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        raise
    finally:
        ms = int((time.perf_counter() - t0) * 1000)
        usage = normalize_usage(getattr(resp, "usage", None))
        try:
            cost = price(model, usage) if resp is not None else 0.0
        except KeyError:
            cost = None                      # unknown model: record, don't guess
        row = {
            "id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "model": model,
            "task": task,
            "ms": ms,
            "ok": err is None,
            "error": err,
            "cost_usd": cost,
            "input": prompt_text,
            "output": text_of(resp),
            **usage,
            **(meta or {}),
        }
        with open(path or TRACE_PATH, "a") as f:
            f.write(json.dumps(row, default=str) + "\n")

    return resp

def text_of(resp):
    """Best-effort extraction of the response text across client shapes."""
    if resp is None:
        return ""
    blocks = getattr(resp, "content", None)          # Anthropic-shaped
    if isinstance(blocks, list):
        return "".join(getattr(b, "text", "") for b in blocks)
    choices = getattr(resp, "choices", None)         # OpenAI-shaped
    if choices:
        return getattr(choices[0].message, "content", "") or ""
    return str(resp)
