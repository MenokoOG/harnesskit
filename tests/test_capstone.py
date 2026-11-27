import tempfile
import unittest
from pathlib import Path

from harnesskit.assemble import build_agent
from harnesskit.model import FakeModel, reply


class CapstoneTests(unittest.TestCase):
    def test_full_flow(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "AGENTS.md").write_text("Use 4 spaces.", encoding="utf-8")
            sk = root / "skills" / "review"
            sk.mkdir(parents=True)
            (sk / "SKILL.md").write_text(
                "---\nname: review\ndescription: How to review a diff\n---\nCheck tests first.\n", encoding="utf-8")
            target = str(root / "a.py")
            ran = []

            def fake_bash(cmd: str, timeout: int = 120) -> str:
                """Pretend shell."""
                ran.append(cmd)
                return "exit=0"

            model = FakeModel([
                reply(calls=[("skill", {"name": "review"})]),
                reply(calls=[("write_file", {"path": target, "content": "x = 1\n"})]),
                reply(calls=[("edit", {"path": target, "old": "x = 1", "new": "x = 2"})]),
                reply(calls=[("write_file", {"path": str(root / ".env"), "content": "KEY=1"})]),
                reply(calls=[("bash", {"cmd": "rm -rf /"})]),
                reply("done"),  # vetoed: code changed, nothing run since
                reply(calls=[("bash", {"cmd": "python -m unittest"})]),
                reply("shipped"),
            ])
            agent = build_agent(model, root=root, skills_dir=root / "skills", bash=fake_bash,
                                ask=lambda cmd: cmd == "python -m unittest")
            self.assertEqual(agent.run("fix x"), "shipped")
            self.assertEqual(Path(target).read_text(), "x = 2\n")
            self.assertFalse((root / ".env").exists())
            self.assertEqual(ran, ["python -m unittest"])
            self.assertIn("Use 4 spaces.", agent.system)
            self.assertIn("review: How to review a diff", agent.system)
            outs = {m["content"] for m in agent.messages if m["role"] == "tool"}
            self.assertTrue(any(o.startswith("BLOCKED by hook") for o in outs))
            self.assertTrue(any(o.startswith("BLOCKED: policy") for o in outs))


if __name__ == "__main__":
    unittest.main()
