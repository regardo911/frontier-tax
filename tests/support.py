"""Shared test setup: put every chapter folder on the import path.

`openai` is only needed to REACH a model. Nothing in this suite calls one, so
when the package isn't installed we satisfy the import and carry on testing the
pure lookup code. The stand-in is not a model and answers nothing - build a
client out of it and it raises.
"""
import importlib.util, os, sys, types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAPTERS = os.path.join(ROOT, "chapters")
FIXTURES = os.path.join(ROOT, "fixtures")
sys.path[:0] = [os.path.join(CHAPTERS, d) for d in sorted(os.listdir(CHAPTERS))
                if os.path.isdir(os.path.join(CHAPTERS, d))]

if importlib.util.find_spec("openai") is None:
    _m = types.ModuleType("openai")

    def _no_client(**kw):
        raise RuntimeError("no openai package here; this suite never calls a model")

    _m.OpenAI = _no_client
    sys.modules["openai"] = _m


class FakeUsage:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class FakeResponse:
    """A provider response shape. Carries usage and text, nothing else."""

    def __init__(self, text="", usage=None):
        self.content = [FakeUsage(text=text)]
        self.usage = usage
