"""Regression tests for bugs reproduced against the course reference build."""
import pathlib
import tempfile
import unittest

from harnesskit.assemble import no_env_writes
from harnesskit.context import Compactor
from harnesskit.edit import edit
from harnesskit.guards import StuckDetector
from harnesskit.loop import Agent
from harnesskit.model import FakeModel, reply
from harnesskit.policy import ALLOW, DEFAULT_RULES, FORBIDDEN, PROMPT, Policy, gated
from harnesskit.tools import default_tools, search_replace
from harnesskit.verify import VerifyOnStop, is_verifier


class PolicyBypassTests(unittest.TestCase):
    def setUp(self):
        self.p = Policy(DEFAULT_RULES)

    def test_newline_never_auto_allows(self):
        for cmd in ("echo hi\ntouch pwned", "ls\r\nrm -rf ./src"):
            self.assertEqual(self.p.decide(cmd, "default"), PROMPT, cmd)
            self.assertEqual(self.p.decide(cmd, "plan"), FORBIDDEN, cmd)

    def test_floor_catches_rm_spellings(self):
        for cmd in ("rm --recursive --force /", "rm -rf ~", "rm -rf -- /", "/bin/rm -rf '/'",
                    "rm -R $HOME", "true;rm --recursive /", 'bash -c "rm --recursive ~"', "ls\nrm -rf ~"):
            self.assertEqual(self.p.decide(cmd, "yolo"), FORBIDDEN, cmd)

    def test_floor_leaves_project_deletes_alone(self):
        for cmd in ("rm -rf ./build", "rm -r /tmp/hk-scratch", "rm file.txt", "echo 'rm notes'"):
            self.assertNotEqual(self.p.decide(cmd, "yolo"), FORBIDDEN, cmd)

    def test_gate_does_not_run_a_hidden_second_line(self):
        ran = []
        run = gated(lambda cmd: ran.append(cmd) or "exit=0", self.p, "plan", lambda c: True)
        self.assertTrue(run("echo hi\ntouch pwned").startswith("BLOCKED"))
        self.assertEqual(ran, [])
        self.assertEqual(self.p.decide("echo hi", "plan"), ALLOW)

    def test_env_variants_are_blocked(self):
        self.assertIsNotNone(no_env_writes("write_file", {"path": "app/.env.local"}))
        self.assertIsNone(no_env_writes("write_file", {"path": "app/env.py"}))


class LineEndingTests(unittest.TestCase):
    def test_edit_tools_keep_crlf(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "w.txt"
            for tool, old, new in ((edit, "b\nc", "B\nC"), (search_replace, "a", "A"), (edit, "d  ", "D")):
                p.write_bytes(b"a\r\nb\r\nc\r\nd\r\n")
                self.assertTrue(tool(str(p), old, new).startswith("OK"))
                self.assertEqual(p.read_bytes().count(b"\r\n"), 4)
                self.assertNotIn(b"\r\r", p.read_bytes())


class CompactionInteractionTests(unittest.TestCase):
    def test_stuck_detector_still_halts_with_compaction_on(self):
        model = FakeModel([reply(calls=[("bash", {"cmd": "true"})]) for _ in range(20)])
        agent = Agent(model, default_tools(), max_turns=20, middleware=[
            StuckDetector(warn_after=3, halt_after=6), Compactor(lambda p: "s", threshold_tokens=10)])
        self.assertTrue(agent.run("x").startswith("stuck: bash"))

    def test_compaction_cannot_erase_an_unverified_edit(self):
        with tempfile.TemporaryDirectory() as d:
            target = str(pathlib.Path(d) / "a.py")
            filler = [reply(calls=[("bash", {"cmd": f"echo {i}"})]) for i in range(6)]
            model = FakeModel([reply(calls=[("write_file", {"path": target, "content": "x\n"})]),
                               *filler, reply("done"), reply("done again"), reply("final")])
            guard = VerifyOnStop(max_nudges=1)
            agent = Agent(model, default_tools(), stop_guards=[guard],
                          middleware=[Compactor(lambda p: "s", threshold_tokens=10)])
            agent.run("x")
            self.assertEqual(guard.nudges, 1)


class VerifyTests(unittest.TestCase):
    def test_what_counts_as_a_check(self):
        for good in ("pytest -q", "python -m unittest discover -s tests", "cd app && npm test"):
            self.assertTrue(is_verifier(good), good)
        for bad in ("echo pytest", "pytest || true", "pytest; true", "grep unittest a.py", "pytestx"):
            self.assertFalse(is_verifier(bad), bad)

    def test_failing_check_does_not_clear_the_edit(self):
        guard = VerifyOnStop()
        guard.observe({"name": "write_file", "args": {"path": "a.py"}}, "wrote 1 characters to a.py")
        guard.observe({"name": "bash", "args": {"cmd": "pytest"}}, "exit=1\nstdout:")
        self.assertTrue(guard.unverified)
        guard.observe({"name": "bash", "args": {"cmd": "pytest"}}, "exit=0\nstdout:")
        self.assertFalse(guard.unverified)


class SchemaTests(unittest.TestCase):
    def test_real_models_get_argument_names_and_types(self):
        schemas = {s["name"]: s for s in Agent(FakeModel([]), default_tools()).schemas()}
        params = schemas["read_file"]["parameters"]
        self.assertEqual(params["required"], ["path"])
        self.assertEqual(params["properties"]["offset"], {"type": "integer"})


if __name__ == "__main__":
    unittest.main()
