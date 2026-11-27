import pathlib
import tempfile
import unittest

from harnesskit.edit import edit
from harnesskit.loop import Agent
from harnesskit.model import FakeModel, reply
from harnesskit.toolsearch import ToolIndex, make_tool_search


def git_log() -> str:
    """Show recent git commit history for a repository."""
    return "abc123 first commit"


def csv_stats(path: str) -> str:
    """Compute column statistics for a CSV file."""
    return "stats"


def http_get(url: str) -> str:
    """Fetch a URL over HTTP and return the body."""
    return "body"


DEFERRED = {f.__name__: f for f in (git_log, csv_stats, http_get)}


class EditTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.p = pathlib.Path(self.dir.name) / "f.txt"

    def tearDown(self):
        self.dir.cleanup()

    def test_exact_unique(self):
        self.p.write_text("a = 1\nb = 2\n")
        self.assertEqual(edit(str(self.p), "b = 2", "b = 3"), "OK")
        self.assertEqual(self.p.read_text(), "a = 1\nb = 3\n")

    def test_ambiguous_is_refused(self):
        self.p.write_text("a\na\n")
        self.assertIn("occurs 2 times", edit(str(self.p), "a", "b"))
        self.assertEqual(self.p.read_text(), "a\na\n")

    def test_missing_is_refused(self):
        self.p.write_text("a\n")
        self.assertIn("not found", edit(str(self.p), "zzz", "b"))

    def test_smart_quotes_and_trailing_space(self):
        self.p.write_text("print(“hi”)  \n")
        out = edit(str(self.p), 'print("hi")', 'print("bye")')
        self.assertTrue(out.startswith("OK (matched after"))
        self.assertEqual(self.p.read_text(), 'print("bye")\n')


class ToolSearchTests(unittest.TestCase):
    def test_ranking(self):
        idx = ToolIndex({n: f.__doc__ for n, f in DEFERRED.items()})
        self.assertEqual(idx.search("git commit history"), ["git_log"])
        self.assertEqual(idx.search("csv"), ["csv_stats"])
        self.assertEqual(idx.search("quantum"), [])

    def test_found_tools_become_callable_next_turn(self):
        tools = {}
        tools["tool_search"] = make_tool_search(tools, DEFERRED)
        model = FakeModel([
            reply(calls=[("tool_search", {"query": "git commit history"})]),
            reply(calls=[("git_log", {})]),
            reply("ok"),
        ])
        agent = Agent(model, tools)
        agent.run("what changed?")
        self.assertEqual(len(agent.schemas()), 2)
        self.assertIn("abc123", [m for m in agent.messages if m.get("name") == "git_log"][0]["content"])


if __name__ == "__main__":
    unittest.main()
