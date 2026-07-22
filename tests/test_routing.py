"""The routing table, the kill switch, and the three safety mechanisms. ch07 + ch11 + ch12."""
import contextlib, io, json, os, subprocess, sys, tempfile, unittest

import support
from support import CHAPTERS, FIXTURES, ROOT
import build_table
from build_table import MIN_REL_PASS, REQUIRE_OVERLAP, rule_from


def card(model, n, passed, cpt, ci):
    return {"model": model, "n": n, "passed": passed, "errors": 0,
            "rate": passed / n, "cost": cpt * n, "cpt": cpt, "ci": ci, "secs": 1.0}


class RiskAppetite(unittest.TestCase):
    def test_the_two_constants_are_the_books(self):
        self.assertEqual(MIN_REL_PASS, 0.95)
        self.assertTrue(REQUIRE_OVERLAP)


class WhyField(unittest.TestCase):
    """The sentence a skeptic reads six months from now. It has to be true."""

    BASE = card("claude-opus-4-8", 40, 31, 0.0684, [0.62, 0.88])

    def test_a_candidate_that_clears_the_bar_wins_on_cost(self):
        r = rule_from([{"task": "changelog", "baseline": self.BASE,
                        "candidate": card("ds-flash", 40, 30, 0.00041, [0.60, 0.86])}])
        self.assertEqual(r["chosen"], "ds-flash")
        self.assertEqual(r["fallback"], "claude-opus-4-8")
        self.assertIn("rel_pass 0.97 of baseline at 0.6% of cost, n=40", r["why"])

    def test_nothing_cleared_the_bar_reads_exactly_as_the_book_prints_it(self):
        # the book's own routes.json sample: a candidate at 0.71, genuinely under
        r = rule_from([{"task": "code-review", "baseline": self.BASE,
                        "candidate": card("ds-flash", 40, 22, 0.0031, [0.40, 0.69])}])
        self.assertEqual(r["chosen"], "claude-opus-4-8")
        self.assertIsNone(r["fallback"])
        self.assertEqual(r["why"], "no candidate cleared the bar; best was 0.71 of baseline")

    def test_cleared_the_bar_but_cost_more_says_so(self):
        # ch03's Sonnet 5 case: over the quality bar, over the price too.
        r = rule_from([{"task": "code-review", "baseline": self.BASE,
                        "candidate": card("claude-sonnet-5", 40, 30, 0.0736668,
                                          [0.60, 0.86])}])
        self.assertEqual(r["chosen"], "claude-opus-4-8")
        self.assertEqual(
            r["why"],
            "claude-sonnet-5 cleared the bar at rel_pass 0.97 but cost "
            "107.7% of baseline, n=40")

    def test_a_non_overlapping_interval_disqualifies(self):
        r = rule_from([{"task": "t", "baseline": self.BASE,
                        "candidate": card("ds-flash", 40, 30, 0.00041, [0.10, 0.30])}])
        self.assertEqual(r["chosen"], "claude-opus-4-8")

    def test_second_choice_has_to_have_cleared_the_same_bar(self):
        cards = [{"task": "t", "baseline": self.BASE,
                  "candidate": card("ds-flash", 40, 22, 0.0031, [0.40, 0.69])}]
        self.assertIsNone(rule_from(cards)["second_choice"])   # no hedge for this work

    def test_break_even_escalation_rate_is_written_in(self):
        r = rule_from([{"task": "changelog", "baseline": self.BASE,
                        "candidate": card("ds-flash", 40, 30, 0.00684, [0.60, 0.86])}])
        self.assertAlmostEqual(r["breakeven_escalation_rate"], 0.9)


class TableFromTheSampleScorecards(unittest.TestCase):
    def test_build_table_reproduces_the_committed_sample(self):
        d = tempfile.mkdtemp()
        subprocess.run([sys.executable,
                        os.path.join(CHAPTERS, "07-router", "build_table.py"),
                        os.path.join(FIXTURES, "scorecards.sample", "*.json")],
                       cwd=d, check=True, stdout=subprocess.DEVNULL)
        with open(os.path.join(d, "routes.json")) as f:
            built = json.load(f)
        with open(os.path.join(FIXTURES, "routes.sample.json")) as f:
            shipped = json.load(f)
        self.assertEqual(built, shipped)


class Router(unittest.TestCase):
    """route() is a lookup. Three branches, and two of them are safety."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        p = os.path.join(self.d, "routes.json")
        with open(p, "w") as f:
            json.dump({"changelog": {"chosen": "ds-flash"}}, f)
        os.environ["ROUTES"] = p
        os.environ["DEFAULT_MODEL"] = "claude-opus-4-8"
        os.environ.pop("ROUTER_OFF", None)
        for m in ("router",):
            sys.modules.pop(m, None)
        import router
        self.router = router

    def tearDown(self):
        os.environ.pop("ROUTER_OFF", None)

    def test_a_measured_task_goes_where_the_table_says(self):
        self.assertEqual(self.router.route("changelog"), "ds-flash")

    def test_an_unknown_task_goes_to_the_most_capable_model(self):
        # new work is unmeasured work, and unmeasured work has not earned a discount
        self.assertEqual(self.router.route("something-new"), "claude-opus-4-8")

    def test_the_kill_switch_sends_everything_back(self):
        os.environ["ROUTER_OFF"] = "1"
        self.assertEqual(self.router.route("changelog"), "claude-opus-4-8")

    def test_router_off_is_exactly_one_not_truthy(self):
        os.environ["ROUTER_OFF"] = "yes"
        self.assertEqual(self.router.route("changelog"), "ds-flash")


class Remeasure(unittest.TestCase):
    """ch12: it writes a recommendation, and it never claims to have measured
    something it did not."""

    def _load(self):
        for m in ("remeasure",):
            sys.modules.pop(m, None)
        import remeasure
        return remeasure

    def test_it_writes_routes_recommended_and_never_routes_json(self):
        with open(os.path.join(CHAPTERS, "12-re-measure", "remeasure.py")) as f:
            src = f.read()
        self.assertIn('open("routes_recommended.json", "w")', src)
        self.assertNotIn('open("routes.json", "w")', src)

    # A stand-in for harness.py that writes a scorecard for changelog and dies
    # on code-review. It never calls a model; it only produces the two outcomes
    # rescore() has to tell apart.
    STUB_HARNESS = '''
import json, sys
task = sys.argv[sys.argv.index("--task") + 1]
out = sys.argv[sys.argv.index("--out") + 1]
if task == "code-review":
    sys.exit(1)
def card(model, passed, cpt):
    return {"model": model, "n": 40, "passed": passed, "errors": 0,
            "rate": passed / 40.0, "cost": cpt * 40, "cpt": cpt,
            "ci": [0.62, 0.88], "secs": 1.0}
with open(out, "w") as f:
    json.dump({"task": task, "baseline": card("claude-opus-4-8", 31, 0.0684),
               "candidate": card(sys.argv[sys.argv.index("--candidate") + 1],
                                 31, 0.001)}, f)
'''

    def _last_month(self, tasks):
        os.makedirs("scorecards", exist_ok=True)
        for task in tasks:
            with open(f"scorecards/{task}__glm-5-2.json", "w") as f:
                json.dump({"task": task,
                           "baseline": card("claude-opus-4-8", 40, 31, 0.0684,
                                            [0.62, 0.88]),
                           "candidate": card("glm-5-2", 40, 31, 0.001,
                                             [0.62, 0.88])}, f)

    def test_a_task_nothing_scored_is_named_not_reported_as_no_change(self):
        rm = self._load()
        d = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(d)
        try:
            self._last_month(["changelog", "code-review"])
            stub = os.path.join(d, "stub_harness.py")
            with open(stub, "w") as f:
                f.write(self.STUB_HARNESS)
            real_sibling = rm._sibling
            rm._sibling = lambda ch, name: (stub if name == "harness.py"
                                            else real_sibling(ch, name))
            rm.TASKS = ["changelog", "code-review"]
            rm.CANDIDATES = ["glm-5-2"]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rm.main("traces.jsonl")
            out = buf.getvalue()
            self.assertIn("NOT RE-MEASURED THIS RUN", out)
            self.assertIn("code-review", out)
            # the false sentence the printed version would have ended on
            self.assertNotIn("Every task type keeps the model it had", out)
            with open("routes_recommended.json") as f:
                rec = json.load(f)
            self.assertIn("changelog", rec)        # this one really was re-scored
            self.assertNotIn("code-review", rec)   # stale answer not carried forward
        finally:
            rm._sibling = real_sibling
            os.chdir(cwd)

    def test_rescore_clears_the_directory_it_rotated(self):
        rm = self._load()
        d = tempfile.mkdtemp()
        cwd = os.getcwd()
        os.chdir(d)
        try:
            os.makedirs("scorecards")
            with open("scorecards/changelog__old.json", "w") as f:
                f.write("{}")
            rm.TASKS, rm.CANDIDATES = [], []
            rm.rescore("traces.jsonl")
            self.assertEqual(os.listdir("scorecards"), ["prev"])
            self.assertEqual(os.listdir("scorecards/prev"), ["changelog__old.json"])
        finally:
            os.chdir(cwd)


class ShadowMode(unittest.TestCase):
    """Two rules that matter more than the code: its own task tag, and it never
    raises into the request path."""

    def test_the_shadow_call_is_tagged_and_swallows_everything(self):
        with open(os.path.join(CHAPTERS, "07-router", "shadow.py")) as f:
            src = f.read()
        self.assertIn('task=f"shadow:{task}"', src)
        self.assertIn("except Exception:", src)


if __name__ == "__main__":
    unittest.main()
