# Chapter 6: the menu

`providers.py` puts a local runtime, a gateway and a hosted open-weight model behind one
`complete()` call. Swapping candidates is one string on the command line.

## The six variables with no defaults, and why

```
OPENROUTER_URL   OPENROUTER_API_KEY
DEEPSEEK_URL     DEEPSEEK_API_KEY
ZAI_URL          ZAI_API_KEY
```

`client_for()` raises a `RuntimeError` naming the missing one rather than guessing. That's
deliberate, and it's the reason this repo ships no `.env.example`. A base URL typed from memory
is a base URL that can be wrong or go stale, and an example file invites you to trust a value
nobody checked. Open the provider's own quickstart page, copy the URL off it, export it.

The local and gateway endpoints *are* hardcoded, because they're fixed and documented:

```
LITELLM_URL   http://0.0.0.0:4000      LITELLM_KEY  sk-anything
VLLM_MODEL    (whatever you served)    VLLM_API_KEY EMPTY
OLLAMA_MODEL  qwen3:8b
```

## Before you debug a client, confirm the server

```
curl http://localhost:11434/v1/models      # ollama
curl http://localhost:8000/v1/models       # vllm
curl http://0.0.0.0:4000/v1/models         # litellm proxy
```

Each returns JSON listing what it can serve. If it doesn't, no amount of client debugging will
help you. **These three commands and the `vllm serve` / `litellm` invocations came out of the
projects' own documentation and were not run here**. No GPU on the machine this was built on.
Treat them as documented, not verified.

For the hosted providers the equivalent check is one cheap completion through `complete()`.

## Add every alias to the rate table

Open `../04-instrument/tracelog.py` and put each alias you plan to route on into `RATES`, the
frontier alias included. The router dispatches on the alias (`ds-flash`), and the logger prices
by looking that same string up. Key `RATES` by the provider's id (`deepseek-v4-flash`) instead
and every routed call logs `cost_usd: null` while appearing to work perfectly. `GOTCHAS.md`
has the one-line check.

Set `DEFAULT_MODEL` to the frontier **alias** from `CATALOG`, not to the provider's model id.
`router.py`, `call_role.py` and `guard.py` all hand it straight to `complete()`.
