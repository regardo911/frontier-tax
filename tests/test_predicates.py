"""tasks.py - the predicates everything downstream grades with."""
import unittest

import support  # noqa: F401  (import path + openai stand-in)
from tasks import TASKS, check_changelog, check_review, _commits_in


TRACE = {"input": "a1b2c3d fix retry backoff\ne4f5a6b add cache header"}


class Changelog(unittest.TestCase):
    def test_the_book_sanity_pair(self):
        good = "## Release\n- a1b2c3d fix retry backoff\n- e4f5a6b add cache header"
        bad = "## Release\n- a1b2c3d fix retry backoff\n- 9999999 add telemetry"
        self.assertTrue(check_changelog(good, TRACE))
        self.assertFalse(check_changelog(bad, TRACE))

    def test_a_dropped_commit_fails(self):
        self.assertFalse(check_changelog("## Release\n- a1b2c3d fix retry backoff", TRACE))

    def test_no_heading_fails(self):
        self.assertFalse(check_changelog(
            "- a1b2c3d fix retry backoff\n- e4f5a6b add cache header", TRACE))

    def test_no_commits_in_the_prompt_fails(self):
        self.assertFalse(check_changelog("## Release\n- nothing", {"input": "hello"}))

    def test_commit_parse(self):
        self.assertEqual(_commits_in(TRACE),
                         [("a1b2c3d", "fix retry backoff"),
                          ("e4f5a6b", "add cache header")])


class Review(unittest.TestCase):
    TR = {"id": "t1", "input": "diff",
          "defect": {"file": "billing/charge.py", "keywords": ["off-by-one", "range"]}}

    def test_names_the_defect(self):
        self.assertTrue(check_review(
            "billing/charge.py has an off-by-one in the loop bound", self.TR))

    def test_right_file_wrong_finding(self):
        self.assertFalse(check_review("billing/charge.py looks fine", self.TR))

    def test_right_finding_wrong_file(self):
        self.assertFalse(check_review("there is an off-by-one somewhere", self.TR))

    def test_a_trace_with_no_known_defect_is_a_bug_not_a_fail(self):
        with self.assertRaises(ValueError):
            check_review("anything", {"id": "t2", "input": "diff"})


class Registry(unittest.TestCase):
    def test_both_tasks_registered_with_the_documented_signature(self):
        self.assertEqual(sorted(TASKS), ["changelog", "code-review"])
        for name, spec in TASKS.items():
            self.assertIn("desc", spec)
            self.assertTrue(callable(spec["check"]), name)


if __name__ == "__main__":
    unittest.main()
