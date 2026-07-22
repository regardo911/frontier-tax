"""providers.py - every model in this book behind one call. Chapter 6."""
import os
from openai import OpenAI

# Local endpoints are fixed and documented, so they're hardcoded.
# Hosted base URLs come from env vars ON PURPOSE: read the exact URL off
# the provider's own quickstart page and set it there. A base URL I typed
# from memory into a book is a base URL that can be wrong or go stale.
PROVIDERS = {
    "ollama": dict(base_url="http://localhost:11434/v1/",
                   api_key="ollama"),                  # required, ignored
    "vllm":   dict(base_url="http://localhost:8000/v1",
                   api_key=os.environ.get("VLLM_API_KEY", "EMPTY")),
    "litellm": dict(base_url=os.environ.get("LITELLM_URL", "http://0.0.0.0:4000"),
                    api_key=os.environ.get("LITELLM_KEY", "sk-anything")),
    "openrouter": dict(base_url=os.environ.get("OPENROUTER_URL"),
                       api_key=os.environ.get("OPENROUTER_API_KEY")),
    "deepseek":   dict(base_url=os.environ.get("DEEPSEEK_URL"),
                       api_key=os.environ.get("DEEPSEEK_API_KEY")),
    "zai":        dict(base_url=os.environ.get("ZAI_URL"),
                       api_key=os.environ.get("ZAI_API_KEY")),
}

# model string -> (provider key, the id THAT provider expects)
CATALOG = {
    # Your frontier baseline needs a row here too, and it's the one everybody
    # forgets. Chapter 7's router falls back to it, Chapter 8's planner and
    # verifier run on it, and Chapter 11 escalates to it - all three go through
    # complete(), so without these rows every one of them dies on a KeyError the
    # first time it needs the expensive model. This adapter speaks the OpenAI
    # chat-completions shape, so reach the frontier through an OpenAI-compatible
    # surface you already have: the LiteLLM proxy above, or a gateway.
    "claude-opus-4-8":  ("litellm",    "claude-opus-4-8"),
    "claude-sonnet-5":  ("litellm",    "claude-sonnet-5"),
    "claude-haiku-4-5": ("litellm",    "claude-haiku-4-5"),
    "local-small":  ("ollama",     os.environ.get("OLLAMA_MODEL", "qwen3:8b")),
    "local-served": ("vllm",       os.environ.get("VLLM_MODEL", "")),
    "ds-flash":     ("deepseek",   "deepseek-v4-flash"),
    "ds-pro":       ("deepseek",   "deepseek-v4-pro"),
    "glm-4-6":      ("zai",        "GLM-4.6"),
    "glm-5-2":      ("zai",        "GLM-5.2"),
    "or-auto":      ("openrouter", "openrouter/auto"),
}

_clients = {}

def client_for(alias):
    """One OpenAI-compatible client per provider, made once."""
    if alias not in CATALOG:
        raise KeyError(f"unknown alias {alias!r}. known: {sorted(CATALOG)}")
    provider, model_id = CATALOG[alias]
    cfg = PROVIDERS[provider]
    if not cfg.get("base_url"):
        raise RuntimeError(
            f"{provider}: no base_url. Set the env var - get the exact URL "
            f"from {provider}'s quickstart page, don't guess it.")
    if provider not in _clients:
        _clients[provider] = OpenAI(base_url=cfg["base_url"],
                                    api_key=cfg["api_key"] or "EMPTY")
    return _clients[provider], model_id

def complete(alias, messages, max_tokens=2000, **kw):
    """The single call site. Swapping providers is now one string."""
    client, model_id = client_for(alias)
    return client.chat.completions.create(
        model=model_id, messages=messages, max_tokens=max_tokens, **kw)
