import pathlib
import tempfile
import unittest

from harnesskit.loop import Agent, truncate
from harnesskit.model import FakeModel, reply
from harnesskit.tools import default_tools


class LoopTests(unittest.TestCase):
    def test_write_read_finish(self):
        with tempfile.TemporaryDirectory() as d:
            p = str(pathlib.Path(d) / "a.txt")
            model = FakeModel([
                reply(calls=[("write_file", {"path": p, "content": "hi\n"})]),
                reply(calls=[("read_file", {"path": p})]),
                reply("all done"),
            ])
            agent = Agent(model, default_tools())
            self.assertEqual(agent.run("make a file"), "all done")
            self.assertEqual(agent.stop_reason, "done")
            tool_msgs = [m for m in agent.messages if m["role"] == "tool"]
            self.assertIn("   1: hi", tool_msgs[1]["content"])

    def test_turn_limit_stops_a_runaway(self):
        model = FakeModel([reply(calls=[("bash", {"cmd": "true"})]) for _ in range(10)])
        agent = Agent(model, default_tools(), max_turns=3)
        self.assertEqual(agent.run("loop"), "max_turns=3")
        self.assertEqual(agent.turns, 3)

    def test_cost_and_time_limits(self):
        model = FakeModel([reply(calls=[("bash", {"cmd": "true"})], cost=2.0) for _ in range(5)])
        self.assertEqual(Agent(model, default_tools(), max_cost=3.0).run("x"), "max_cost=3.0")
        self.assertEqual(Agent(FakeModel([]), default_tools(), max_seconds=0.0).run("x"), "max_seconds=0.0")

    def test_errors_reach_the_model(self):
        model = FakeModel([reply(calls=[("nope", {})]), reply("ok")])
        agent = Agent(model, default_tools())
        agent.run("x")
        tool_msg = [m for m in agent.messages if m["role"] == "tool"][0]
        self.assertTrue(tool_msg["content"].startswith("ERROR: unknown tool"))

    def test_tool_exceptions_are_surfaced(self):
        model = FakeModel([reply(calls=[("read_file", {"path": "/no/such/file"})]), reply("ok")])
        agent = Agent(model, default_tools())
        agent.run("x")
        tool_msg = [m for m in agent.messages if m["role"] == "tool"][0]
        self.assertIn("FileNotFoundError", tool_msg["content"])

    def test_truncate(self):
        self.assertEqual(truncate("abc", 10), "abc")
        self.assertTrue(truncate("a" * 50, 10).endswith("...[truncated]"))


if __name__ == "__main__":
    unittest.main()
