import pathlib
import tempfile
import unittest

from harnesskit.guards import StuckDetector, drain_inbox
from harnesskit.loop import Agent
from harnesskit.model import FakeModel, reply
from harnesskit.tools import default_tools
from harnesskit.verify import VerifyOnStop

SAME = ("bash", {"cmd": "echo hi"})


class GuardTests(unittest.TestCase):
    def test_stuck_halts(self):
        model = FakeModel([reply(calls=[SAME]) for _ in range(10)])
        agent = Agent(model, default_tools(), middleware=[StuckDetector(warn_after=2, halt_after=3)])
        out = agent.run("x")
        self.assertTrue(out.startswith("stuck: bash"))
        self.assertEqual(agent.turns, 3)

    def test_stuck_warns_without_halting(self):
        model = FakeModel([reply(calls=[SAME]) for _ in range(3)] + [reply("done")])
        agent = Agent(model, default_tools(), middleware=[StuckDetector(warn_after=2, halt_after=0)])
        self.assertEqual(agent.run("x"), "done")
        warns = [m for m in agent.messages if m["role"] == "user" and "identical" in m["content"]]
        self.assertGreaterEqual(len(warns), 1)

    def test_different_args_are_not_stuck(self):
        model = FakeModel([reply(calls=[("bash", {"cmd": f"echo {i}"})]) for i in range(4)] + [reply("done")])
        agent = Agent(model, default_tools(), middleware=[StuckDetector(warn_after=2, halt_after=3)])
        self.assertEqual(agent.run("x"), "done")

    def test_verify_on_stop_vetoes_then_accepts(self):
        with tempfile.TemporaryDirectory() as d:
            p = str(pathlib.Path(d) / "a.py")
            model = FakeModel([
                reply(calls=[("write_file", {"path": p, "content": "x = 1\n"})]),
                reply("done"),
                reply(calls=[("bash", {"cmd": "python -m unittest"})]),
                reply("really done"),
            ])
            tools = default_tools() | {"bash": lambda cmd: "exit=0"}
            agent = Agent(model, tools, stop_guards=[VerifyOnStop()])
            self.assertEqual(agent.run("x"), "really done")

    def test_verify_nudges_are_capped(self):
        with tempfile.TemporaryDirectory() as d:
            p = str(pathlib.Path(d) / "a.py")
            model = FakeModel([reply(calls=[("write_file", {"path": p, "content": "x\n"})])] + [reply("done")] * 5)
            agent = Agent(model, default_tools(), stop_guards=[VerifyOnStop(max_nudges=2)])
            self.assertEqual(agent.run("x"), "done")
            self.assertEqual(agent.turns, 4)

    def test_inbox_reaches_the_model(self):
        model = FakeModel([reply("ok")])
        agent = Agent(model, default_tools(), middleware=[drain_inbox])
        agent.inbox.append("also add tests")
        agent.run("x")
        self.assertEqual(model.seen[0][-1]["content"], "also add tests")


if __name__ == "__main__":
    unittest.main()
