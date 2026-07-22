"""wilson(), load()'s model filter, and scoring the baseline off its own log. ch05."""
import contextlib, io, json, os, tempfile, unittest

import support
from harness import load, report, score_model, wilson
from tasks import check_changelog, check_review

ROWS = [
    # two the frontier produced, three the router later sent to a cheap model
    {"id": "a", "task": "changelog", "ok": True, "model": "claude-opus-4-8",
     "input": "a1b2c3d fix retry backoff", "output": "## R\n- a1b2c3d fix retry backoff",
     "input_tokens": 1000, "output_tokens": 100,
     "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "ms": 900},
    {"id": "b", "task": "changelog", "ok": True, "model": "claude-opus-4-8",
     "input": "e4f5a6b add cache header", "output": "## R\n- 9999999 add telemetry",
     "input_tokens": 1000, "output_tokens": 100,
     "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "ms": 900},
    {"id": "c", "task": "changelog", "ok": True, "model": "deepseek-v4-flash",
     "input": "1111111 x", "output": "## R\n- 1111111 x",
     "input_tokens": 1000, "output_tokens": 100,
     "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "ms": 400},
    {"id": "d", "task": "changelog", "ok": True, "model": "deepseek-v4-flash",
     "input": "2222222 y", "output": "## R\n- 2222222 y",
     "input_tokens": 1000, "output_tokens": 100,
     "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "ms": 400},
    {"id": "e", "task": "changelog", "ok": True, "model": "deepseek-v4-flash",
     "input": "3333333 z", "output": "## R\n- 3333333 z",
     "input_tokens": 1000, "output_tokens": 100,
     "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "ms": 400},
    {"id": "f", "task": "code-review", "ok": True, "model": "claude-opus-4-8",
     "input": "diff", "output": "fine", "input_tokens": 1, "output_tokens": 1,
     "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "ms": 1},
    {"id": "g", "task": "changelog", "ok": False, "model": "claude-opus-4-8",
     "input": "x", "output": "", "input_tokens": 0, "output_tokens": 0,
     "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0, "ms": 1},
]


def _file():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "traces.jsonl")
    with open(p, "w") as f:
        for r in ROWS:
            f.write(json.dumps(r) + "\n")
        f.write("\n")          # blank lines are skipped, not fatal
    return p


class Wilson(unittest.TestCase):
    def test_the_ch03_interval_table(self):
        # tasks, passed, low%, high%
        for n, k, lo, hi in [(10, 8, 49, 94), (20, 16, 58, 92), (50, 40, 67, 89),
                             (100, 80, 71, 87), (200, 160, 74, 85), (500, 400, 76, 83)]:
            g_lo, g_hi = wilson(k, n)
            self.assertEqual(round(g_lo * 100), lo, f"n={n} low")
            self.assertEqual(round(g_hi * 100), hi, f"n={n} high")

    def test_the_interval_narrows_as_n_grows(self):
        widths = [wilson(int(0.8 * n), n)[1] - wilson(int(0.8 * n), n)[0]
                  for n in (10, 50, 200, 500)]
        self.assertEqual(widths, sorted(widths, reverse=True))

    def test_no_samples_is_not_a_division_error(self):
        self.assertEqual(wilson(0, 0), (0.0, 0.0))


class Load(unittest.TestCase):
    def test_task_ok_and_input_are_all_required(self):
        got = load(_file(), "changelog", 40)
        self.assertEqual([r["id"] for r in got], ["a", "b", "c", "d", "e"])

    def test_the_model_filter_keeps_only_that_models_rows(self):
        got = load(_file(), "changelog", 40, model="claude-opus-4-8")
        self.assertEqual([r["id"] for r in got], ["a", "b"])

    def test_limit_applies(self):
        self.assertEqual(len(load(_file(), "changelog", 2)), 2)

    def test_no_usable_traces_exits(self):
        with self.assertRaises(SystemExit):
            load(_file(), "changelog", 40, model="claude-fable-5")


class BaselineFromItsOwnLog(unittest.TestCase):
    """The offline half of the harness: no key, no network, no replay."""

    def test_scores_and_prices_the_logged_output(self):
        traces = load(_file(), "changelog", 40, model="claude-opus-4-8")
        r = score_model(None, "claude-opus-4-8", traces, check_changelog, 2000,
                        reuse_baseline=True)
        self.assertEqual((r["n"], r["passed"]), (2, 1))     # row b invents a sha
        self.assertAlmostEqual(r["cpt"], 1000 * 5 / 1e6 + 100 * 25 / 1e6)

    def test_without_the_filter_cheap_rows_get_billed_at_the_frontier_rate(self):
        """This is why load() takes model=."""
        unfiltered = load(_file(), "changelog", 40)
        filtered = load(_file(), "changelog", 40, model="claude-opus-4-8")
        self.assertEqual(len(unfiltered) - len(filtered), 3)   # three cheap rows

        wrong = score_model(None, "claude-opus-4-8", unfiltered, check_changelog,
                            2000, reuse_baseline=True)
        right = score_model(None, "claude-opus-4-8", filtered, check_changelog,
                            2000, reuse_baseline=True)
        rebilled = wrong["cost"] - right["cost"]        # what the 3 rows "cost"
        truly_cost = 3 * (1000 * 0.14 / 1e6 + 100 * 0.28 / 1e6)
        self.assertGreater(rebilled / truly_cost, 40)   # 44.6x on this pair

    def test_a_predicate_that_throws_stops_the_run(self):
        traces = load(_file(), "code-review", 40)       # these rows carry no defect
        with self.assertRaises(SystemExit):
            score_model(None, "claude-opus-4-8", traces, check_review, 2000,
                        reuse_baseline=True)


class Report(unittest.TestCase):
    def test_a_zero_cost_baseline_prints_nan_rather_than_dividing_by_zero(self):
        # every token counter came back zero: the provider names them something
        # FIELD_ALIASES doesn't know yet. Say so, don't crash.
        base = {"model": "b", "n": 2, "passed": 0, "errors": 0, "rate": 0.0,
                "cost": 0.0, "cpt": 0.0, "ci": (0.0, 0.0), "secs": 0.0}
        cand = dict(base, model="c")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            report("changelog", base, cand)
        self.assertIn("nan", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
