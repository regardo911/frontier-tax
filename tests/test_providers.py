"""Alias resolution and the two refusals. ch06.

complete() is NOT tested here. It calls a model, and a test that pretended to
would be producing exactly the fake receipt this book argues against.
"""
import os, unittest

import support
import providers
from providers import CATALOG, PROVIDERS, client_for


class Catalog(unittest.TestCase):
    def test_every_alias_names_a_provider_that_exists(self):
        for alias, (prov, model_id) in CATALOG.items():
            self.assertIn(prov, PROVIDERS, alias)

    def test_the_frontier_aliases_are_present(self):
        # ch07 falls back to them, ch08 plans and verifies on them, ch11
        # escalates to them, and all three go through complete()
        for alias in ("claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"):
            self.assertIn(alias, CATALOG)

    def test_the_catalog_maps_aliases_to_the_providers_own_ids(self):
        self.assertEqual(CATALOG["ds-flash"], ("deepseek", "deepseek-v4-flash"))
        self.assertEqual(CATALOG["ds-pro"], ("deepseek", "deepseek-v4-pro"))
        self.assertEqual(CATALOG["glm-4-6"], ("zai", "GLM-4.6"))
        self.assertEqual(CATALOG["glm-5-2"], ("zai", "GLM-5.2"))
        self.assertEqual(CATALOG["or-auto"], ("openrouter", "openrouter/auto"))

    def test_the_local_endpoints_are_the_documented_ones(self):
        self.assertEqual(PROVIDERS["ollama"]["base_url"], "http://localhost:11434/v1/")
        self.assertEqual(PROVIDERS["vllm"]["base_url"], "http://localhost:8000/v1")


class Refusals(unittest.TestCase):
    def test_an_unknown_alias_lists_the_known_ones(self):
        with self.assertRaises(KeyError) as e:
            client_for("gpt-whatever")
        self.assertIn("ds-flash", str(e.exception))

    def test_a_hosted_provider_with_no_base_url_says_which_one(self):
        saved = {k: os.environ.pop(k, None)
                 for k in ("DEEPSEEK_URL", "ZAI_URL", "OPENROUTER_URL")}
        try:
            providers.PROVIDERS["deepseek"]["base_url"] = os.environ.get("DEEPSEEK_URL")
            with self.assertRaises(RuntimeError) as e:
                client_for("ds-flash")
            self.assertIn("deepseek", str(e.exception))
            self.assertIn("quickstart", str(e.exception))
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
