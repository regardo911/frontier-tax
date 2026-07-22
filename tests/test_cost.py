"""Pricing, the four counters, and the loud failure. ch02 + ch04."""
import json, os, tempfile, unittest

import support
from support import FakeResponse, FakeUsage
import billsplit
from cpt import cost_per_task
from tracelog import (CACHE_READ_MULT, CACHE_WRITE_MULT, RATES, normalize_usage,
                      price, traced)

ZERO = {"input_tokens": 0, "output_tokens": 0,
        "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}


class Price(unittest.TestCase):
    def test_plain_input_and_output(self):
        u = dict(ZERO, input_tokens=1_000_000, output_tokens=1_000_000)
        self.assertAlmostEqual(price("claude-opus-4-8", u), 30.00, places=6)

    def test_cache_write_costs_a_quarter_more_than_input(self):
        w = price("claude-opus-4-8", dict(ZERO, cache_creation_input_tokens=1_000_000))
        i = price("claude-opus-4-8", dict(ZERO, input_tokens=1_000_000))
        self.assertAlmostEqual(w / i, CACHE_WRITE_MULT, places=9)
        self.assertAlmostEqual(w, 6.25, places=6)

    def test_a_cache_hit_costs_a_tenth(self):
        r = price("claude-opus-4-8", dict(ZERO, cache_read_input_tokens=1_000_000))
        i = price("claude-opus-4-8", dict(ZERO, input_tokens=1_000_000))
        self.assertAlmostEqual(r / i, CACHE_READ_MULT, places=9)
        self.assertAlmostEqual(r, 0.50, places=6)

    def test_an_unknown_model_is_loud(self):
        with self.assertRaises(KeyError):
            price("claude-opus-4-9", ZERO)

    def test_the_rate_table_matches_the_book(self):
        self.assertEqual(RATES["claude-fable-5"], (10.00, 50.00))
        self.assertEqual(RATES["claude-opus-4-8"], (5.00, 25.00))
        self.assertEqual(RATES["claude-sonnet-5"], (2.00, 10.00))
        self.assertEqual(RATES["claude-haiku-4-5"], (1.00, 5.00))
        self.assertEqual(RATES["deepseek-v4-flash"], (0.14, 0.28))
        self.assertEqual(RATES["GLM-4.6"], (0.60, 2.20))
        # Fable 5 is exactly twice Opus 4.8, both directions.
        self.assertEqual([2 * x for x in RATES["claude-opus-4-8"]],
                         list(RATES["claude-fable-5"]))


class NormalizeUsage(unittest.TestCase):
    def test_openai_field_names(self):
        u = normalize_usage(FakeUsage(prompt_tokens=10, completion_tokens=5,
                                      cached_tokens=3))
        self.assertEqual(u["input_tokens"], 10)
        self.assertEqual(u["output_tokens"], 5)
        self.assertEqual(u["cache_read_input_tokens"], 3)

    def test_a_dict_works_too(self):
        self.assertEqual(normalize_usage({"input_tokens": 7})["input_tokens"], 7)

    def test_no_usage_is_four_zeros_not_a_crash(self):
        self.assertEqual(normalize_usage(None), ZERO)

    def test_a_none_cache_field_lands_as_zero(self):
        # they come back as None, not 0, when caching is off
        u = normalize_usage(FakeUsage(input_tokens=1, cache_read_input_tokens=None))
        self.assertEqual(u["cache_read_input_tokens"], 0)


class Traced(unittest.TestCase):
    def _run(self, **kw):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "traces.jsonl")
        return path, d

    def test_returns_the_response_untouched_and_logs_a_row(self):
        path, _ = self._run()
        resp = FakeResponse("hello", FakeUsage(input_tokens=100, output_tokens=50))
        got = traced(lambda **kw: resp, model="claude-opus-4-8", task="changelog",
                     prompt_text="p", path=path)
        self.assertIs(got, resp)
        with open(path) as f:
            row = json.loads(f.read().strip())
        self.assertEqual(row["task"], "changelog")
        self.assertTrue(row["ok"])
        self.assertEqual(row["output"], "hello")
        self.assertAlmostEqual(row["cost_usd"], 100 * 5 / 1e6 + 50 * 25 / 1e6)

    def test_a_failed_call_is_still_a_row(self):
        path, _ = self._run()

        def boom(**kw):
            raise TimeoutError("gone")

        with self.assertRaises(TimeoutError):
            traced(boom, model="claude-opus-4-8", task="changelog",
                   prompt_text="p", path=path)
        with open(path) as f:
            row = json.loads(f.read().strip())
        self.assertFalse(row["ok"])
        self.assertIn("TimeoutError", row["error"])

    def test_meta_lands_on_the_row_and_kwargs_go_to_the_provider(self):
        path, _ = self._run()
        seen = {}

        def call(**kw):
            seen.update(kw)
            return FakeResponse("x", FakeUsage(input_tokens=1, output_tokens=1))

        traced(call, model="claude-opus-4-8", task="t", prompt_text="p",
               path=path, meta={"job": "abc123"}, max_tokens=2000)
        with open(path) as f:
            row = json.loads(f.read().strip())
        self.assertEqual(row["job"], "abc123")
        self.assertEqual(seen, {"max_tokens": 2000})   # job did NOT reach the API

    def test_an_unpriced_model_records_null_rather_than_zero(self):
        path, _ = self._run()
        traced(lambda **kw: FakeResponse("x", FakeUsage(input_tokens=1)),
               model="ds-flash", task="t", prompt_text="p", path=path)
        with open(path) as f:
            self.assertIsNone(json.loads(f.read().strip())["cost_usd"])


class BillSplit(unittest.TestCase):
    ROW = {"model": "claude-opus-4-8", "input_tokens": 1_000_000,
           "output_tokens": 1_000_000, "cache_creation_input_tokens": 1_000_000,
           "cache_read_input_tokens": 1_000_000}

    def test_four_components(self):
        it = billsplit.line_items(self.ROW)
        self.assertEqual(sorted(it), ["cache_read", "cache_write", "input", "output"])
        self.assertAlmostEqual(it["input"], 5.00)
        self.assertAlmostEqual(it["cache_write"], 6.25)
        self.assertAlmostEqual(it["cache_read"], 0.50)
        self.assertAlmostEqual(it["output"], 25.00)

    def test_the_hour_ttl_doubles_the_write(self):
        self.assertAlmostEqual(
            billsplit.line_items(self.ROW, ttl="1h")["cache_write"], 10.00)

    def test_an_unpriced_model_is_loud(self):
        with self.assertRaises(KeyError):
            billsplit.line_items(dict(self.ROW, model="gpt-nonexistent"))

    def test_the_price_table_matches_the_book(self):
        self.assertEqual(billsplit.PRICES["claude-opus-4-8"], (5.00, 25.00))
        self.assertEqual(billsplit.PRICES["claude-haiku-4-5"], (1.00, 5.00))
        self.assertEqual((billsplit.CACHE_WRITE_5M, billsplit.CACHE_WRITE_1H,
                          billsplit.CACHE_READ), (1.25, 2.00, 0.10))


class CostPerTask(unittest.TestCase):
    def test_retries_multiply(self):
        one = cost_per_task(5, 25, 18_000, 3_000, 1.0)
        self.assertAlmostEqual(one, (18_000 * 5 + 3_000 * 25) / 1e6)
        self.assertAlmostEqual(cost_per_task(5, 25, 18_000, 3_000, 2.0), 2 * one)

    def test_the_ordering_can_flip(self):
        dear = cost_per_task(5.00, 25.00, 18_000, 3_000, 1.05)
        cheap_ok = cost_per_task(2.00, 10.00, 34_000, 5_700, 1.30)
        cheap_retrying = cost_per_task(2.00, 10.00, 34_000, 5_700, 1.60)
        self.assertLess(cheap_ok, dear)         # cheaper per token AND per task
        self.assertGreater(cheap_retrying, dear)  # same discount, more retries


if __name__ == "__main__":
    unittest.main()
