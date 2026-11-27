import tempfile
import unittest
from pathlib import Path

from harnesskit.extend import Hooks, discover_skills, make_skill_tool, make_subagent_tool, parse_skill, skills_index
from harnesskit.loop import Agent
from harnesskit.model import FakeModel, reply


def write_skill(root: Path, folder: str, name: str, desc: str, body: str) -> None:
    d = root / folder
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n{body}\n", encoding="utf-8")


class SkillTests(unittest.TestCase):
    def test_priority_index_and_on_demand_body(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            write_skill(Path(a), "r", "review", "Review a diff", "PROJECT BODY")
            write_skill(Path(b), "r", "review", "Review a diff", "USER BODY")
            write_skill(Path(b), "d", "deploy", "Ship it", "DEPLOY BODY")
            skills = discover_skills([Path(a), Path(b)])
            self.assertEqual(skills["review"].body, "PROJECT BODY")
            index = skills_index(skills)
            self.assertIn("deploy: Ship it", index)
            self.assertNotIn("DEPLOY BODY", index)
            self.assertEqual(make_skill_tool(skills)("deploy"), "DEPLOY BODY")
            self.assertTrue(make_skill_tool(skills)("nope").startswith("ERROR"))

    def test_missing_frontmatter_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "SKILL.md"
            p.write_text("no frontmatter here")
            with self.assertRaises(ValueError):
                parse_skill(p)


class HookTests(unittest.TestCase):
    def test_pre_blocks_and_post_rewrites(self):
        hooks = Hooks()
        hooks.on_pre(lambda name, args: "no secrets" if str(args.get("path", "")).endswith(".env") else None)
        hooks.on_post(lambda name, args, out: out + " [checked]")
        def write_file(path: str, content: str) -> str:
            """Write."""
            return "wrote"
        tools = hooks.wrap({"write_file": write_file})
        self.assertEqual(tools["write_file"](path="a.txt", content="x"), "wrote [checked]")
        self.assertEqual(tools["write_file"](path=".env", content="x"), "BLOCKED by hook: no secrets")
        self.assertEqual(tools["write_file"].__doc__, "Write.")


class SubagentTests(unittest.TestCase):
    def test_parent_sees_one_string(self):
        child_model = FakeModel([reply(calls=[("read_file", {"path": "x"})]), reply("found 3 files")])
        parent_tools = {"read_file": lambda path: "contents", "bash": lambda cmd: "ran"}
        parent_tools["task"] = make_subagent_tool(lambda: child_model, parent_tools, {"read_file"})
        parent = Agent(FakeModel([reply(calls=[("task", {"prompt": "count files"})]), reply("ok")]), parent_tools)
        parent.run("go")
        self.assertEqual([m["content"] for m in parent.messages if m.get("name") == "task"], ["found 3 files"])
        self.assertFalse([m for m in parent.messages if m.get("name") == "read_file"])

    def test_child_cannot_use_tools_outside_the_allow_list(self):
        child_model = FakeModel([reply(calls=[("bash", {"cmd": "ls"})]), reply("done")])
        parent_tools = {"read_file": lambda path: "c", "bash": lambda cmd: "ran"}
        task = make_subagent_tool(lambda: child_model, parent_tools, {"read_file"})
        task("go")
        self.assertTrue(child_model.seen[1][-1]["content"].startswith("ERROR: unknown tool"))


if __name__ == "__main__":
    unittest.main()
