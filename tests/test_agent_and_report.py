"""The fan-out join, the advisor split, the diet verdict, and the P&L page.
ch08 + ch09 + ch10."""
import io, contextlib, json, os, subprocess, sys, tempfile, unittest

import support
from support import CHAPTERS, FIXTURES, FakeUsage, ROOT
from advisor_usage import advisor_aware_usage
from diet import log, verdict
from fanout import IncompleteFanOut, join
from pnl import by_task, rates
from tracelog import price


class Join(unittest.TestCase):
    PLAN = {"slices": [1, 2, 3]}

    def ok(self, i):
        return {"slice": i, "status": "ok", "detail": "", "text": f"slice {i}"}

    def test_all_present_joins_in_slice_order(self):
        got = join([self.ok(3), self.ok(1), self.ok(2)], self.PLAN)
        self.assertEqual(got, "slice 1\n\nslice 2\n\nslice 3")

    def test_an_empty_worker_is_a_failure_not_an_empty_answer(self):
        with self.assertRaises(IncompleteFanOut) as e:
            join([self.ok(1), self.ok(2),
                  {"slice": 3, "status": "empty", "detail": "", "text": ""}], self.PLAN)
        self.assertEqual([r["slice"] for r in e.exception.missing], [3])

    def test_an_errored_worker_raises(self):
        with self.assertRaises(IncompleteFanOut):
            join([self.ok(1), self.ok(2),
                  {"slice": 3, "status": "error", "detail": "boom", "text": ""}],
                 self.PLAN)

    def test_a_slice_that_never_came_back_at_all_raises(self):
        with self.assertRaises(IncompleteFanOut) as e:
            join([self.ok(1), self.ok(2)], self.PLAN)
        self.assertEqual(e.exception.absent, [3])
        self.assertEqual(e.exception.missing, [])


class Advisor(unittest.TestCase):
    """Top-level usage counts the executor only. The book's worked call."""

    def _resp(self):
        adv = FakeUsage(type="advisor_message", model="claude-opus-4-8",
                        usage=FakeUsage(input_tokens=9000, output_tokens=1500))
        return FakeUsage(usage=FakeUsage(input_tokens=1200, output_tokens=400,
                                         iterations=[adv]))

    def test_the_split_billing_arithmetic(self):
        base, extra = advisor_aware_usage(self._resp())
        executor = price("claude-sonnet-5", base)
        self.assertAlmostEqual(executor, 0.00640, places=6)
        self.assertEqual(len(extra), 1)
        model, u = extra[0]
        advisor = price(model, u)
        self.assertAlmostEqual(advisor, 0.08250, places=6)
        self.assertAlmostEqual(executor + advisor, 0.08890, places=6)
        # what a logger reading top-level usage would report: 7% of the truth
        self.assertEqual(round(100 * executor / (executor + advisor)), 7)

    def test_no_iterations_is_just_the_executor(self):
        r = FakeUsage(usage=FakeUsage(input_tokens=10, output_tokens=1))
        base, extra = advisor_aware_usage(r)
        self.assertEqual(extra, [])
        self.assertEqual(base["input_tokens"], 10)


class DietVerdict(unittest.TestCase):
    def test_cheaper_and_quality_held(self):
        self.assertEqual(verdict({"cpt": 1.0, "rate": 0.80},
                                 {"cpt": 0.7, "rate": 0.80}), "KEEP")

    def test_inside_the_two_point_tolerance(self):
        self.assertEqual(verdict({"cpt": 1.0, "rate": 0.80},
                                 {"cpt": 0.7, "rate": 0.78}), "KEEP")

    def test_a_saving_that_cost_quality(self):
        self.assertEqual(verdict({"cpt": 1.0, "rate": 0.80},
                                 {"cpt": 0.7, "rate": 0.62}), "REJECT: quality")

    def test_no_saving_at_all(self):
        self.assertEqual(verdict({"cpt": 1.0, "rate": 0.80},
                                 {"cpt": 1.3, "rate": 0.90}), "REJECT: no saving")

    def test_the_changelog_line_records_a_saving_as_negative(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "diet-changelog.md")
        with contextlib.redirect_stdout(io.StringIO()):
            log("four-layer prompt", "changelog",
                {"cpt": 1.0, "rate": 0.78}, {"cpt": 0.776, "rate": 0.80, "n": 40}, p)
        with open(p) as f:
            line = f.read()
        self.assertIn("**KEEP**", line)
        self.assertIn("cost -22.4%", line)
        self.assertIn("pass 78% -> 80%, n=40", line)


class PnL(unittest.TestCase):
    def test_agent_roles_and_escalations_fold_into_one_line(self):
        rows = [
            {"task": "changelog", "ok": True, "cost_usd": 1.0},
            {"task": "changelog:escalated", "ok": True, "cost_usd": 2.0},
            {"task": "changelog-agent:worker", "ok": True, "cost_usd": 4.0},
            {"task": "changelog-agent:planner", "ok": True, "cost_usd": 8.0},
            {"task": "changelog", "ok": False, "cost_usd": 99.0},   # failures excluded
        ]
        got = by_task(rows, 30)
        self.assertEqual(sorted(got), ["changelog", "changelog-agent"])
        self.assertAlmostEqual(got["changelog"]["cost"], 3.0)
        self.assertAlmostEqual(got["changelog-agent"]["cost"], 12.0)

    def test_it_projects_to_thirty_days(self):
        rows = [{"task": "t", "ok": True, "cost_usd": 7.0}]
        self.assertAlmostEqual(by_task(rows, 15)["t"]["cost"], 14.0)

    def test_a_task_that_stayed_keeps_its_own_baseline_rate(self):
        pattern = os.path.join(FIXTURES, "scorecards.sample", "*.json")
        with open(os.path.join(FIXTURES, "routes.sample.json")) as f:
            routes = json.load(f)
        pr = rates(routes, pattern)
        self.assertEqual(pr["code-review"]["before"], pr["code-review"]["after"])

    def test_it_picks_the_scorecard_for_the_model_actually_routed_to(self):
        pattern = os.path.join(FIXTURES, "scorecards.sample", "*.json")
        with open(os.path.join(FIXTURES, "routes.sample.json")) as f:
            routes = json.load(f)
        pr = rates(routes, pattern)
        # changelog has two candidates; the chosen one passed 30 of 40
        self.assertEqual(pr["changelog"]["after"], (30 / 40, 40))

    def test_an_unmatched_scorecard_says_so_rather_than_guessing(self):
        pattern = os.path.join(FIXTURES, "scorecards.sample", "*.json")
        routes = {"changelog": {"chosen": "a-model-nobody-scored"}}
        self.assertIsNone(rates(routes, pattern)["changelog"]["after"])


class TheFirstCommand(unittest.TestCase):
    """The front door. No key, no network, no setup."""

    def test_it_exits_zero_and_prints_the_five_blocks(self):
        env = dict(os.environ)
        env.pop("ROUTES", None)
        env.pop("DEFAULT_MODEL", None)
        traces = os.path.join(FIXTURES, "traces.sample.jsonl")
        # from an empty directory, which is what a fresh clone is: no
        # routes.json, no scorecards/, nothing but the repo and the fixtures
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "chapters", "10-defended-swap",
                                          "pnl.py"), traces, traces, "14", "14"],
            cwd=tempfile.mkdtemp(), capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        for block in ("SWAP DECISION", "CURRENT vs ROUTED, BY TASK TYPE",
                      "WHAT MOVED, AND WHY", "QUALITY", "BREAK-EVEN ON LOCAL"):
            self.assertIn(block, r.stdout)
        self.assertIn("SYNTHETIC", r.stdout)
        self.assertIn("STAYED on claude-opus-4-8", r.stdout)
        self.assertIn("$______", r.stdout)


if __name__ == "__main__":
    unittest.main()
