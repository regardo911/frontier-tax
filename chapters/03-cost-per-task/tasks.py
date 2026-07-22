"""tasks.py - your recurring work, written so a program can grade it. Chapter 3.

The single most important file here, because everything downstream imports it.
Both predicates below are the book's Task A and Task B: named examples, printed
to be replaced. Replace them with your own two recurring tasks and keep the
signature check(output, trace) -> bool identical.
"""
import re

def _commits_in(trace):
    """Commit sha + subject lines from the prompt we actually sent."""
    return re.findall(r"^([0-9a-f]{7,40})\s+(.+)$", trace["input"], re.M)

def check_changelog(output, trace):
    """Task A. Every commit represented, nothing invented, right format."""
    commits = _commits_in(trace)
    if not commits:
        return False
    for sha, _ in commits:                       # 1. full coverage
        if sha[:7] not in output:
            return False
    for sha in re.findall(r"\b[0-9a-f]{7}\b", output):   # 2. nothing invented
        if not any(real.startswith(sha) for real, _ in commits):
            return False
    if not re.search(r"^#+ ", output, re.M):     # 3. asked for a heading
        return False
    bullets = len(re.findall(r"^\s*[-*] ", output, re.M))
    return bullets >= max(1, len(commits) // 3)

def check_review(output, trace):
    """Task B. Did it name the defect we already know is in this diff?

    trace["defect"] = {"file": "billing/charge.py", "keywords": ["off-by-one", "range"]}
    Weaker than Task A on purpose: it measures recall on known bugs only,
    and says nothing about false positives. See ch05.
    """
    defect = trace.get("defect")
    if not defect:
        raise ValueError(f"{trace['id']}: review traces need a known defect")
    low = output.lower()
    if defect["file"].lower() not in low:
        return False
    return any(k.lower() in low for k in defect["keywords"])

TASKS = {
    "changelog":   {"desc": "week of commits -> release notes", "check": check_changelog},
    "code-review": {"desc": "diff -> list of real bugs",        "check": check_review},
}

if __name__ == "__main__":
    # the ch03 sanity check. run it after you replace a predicate: feed it one
    # output you know is good and one you know is bad. True False means your
    # grader can tell a correct answer from a hallucinated one. True True means
    # the predicate is decoration and every measurement built on it is a lie
    # that looks like data.
    trace = {"input": "a1b2c3d fix retry backoff\ne4f5a6b add cache header"}
    good  = "## Release\n- a1b2c3d fix retry backoff\n- e4f5a6b add cache header"
    bad   = "## Release\n- a1b2c3d fix retry backoff\n- 9999999 add telemetry"
    print(check_changelog(good, trace), check_changelog(bad, trace))   # True False
