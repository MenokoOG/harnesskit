import tempfile
import unittest
from pathlib import Path

from harnesskit.context import Compactor, compact, discover_context, estimate_tokens
from harnesskit.loop import Agent
from harnesskit.model import FakeModel, reply


def convo(pairs: int, trailing_note: bool = False) -> list[dict]:
    msgs = [{"role": "system", "content": "sys"}, {"role": "user", "content": "task"}]
    for i in range(pairs):
        msgs.append({"role": "assistant", "content": "", "tool_calls": [{"id": str(i), "name": "bash", "args": {}}]})
        msgs.append({"role": "tool", "tool_call_id": str(i), "name": "bash", "content": f"out {i}"})
    if trailing_note:
        msgs.append({"role": "assistant", "content": "note"})
    return msgs


class ContextTests(unittest.TestCase):
    def test_discovery_order_and_first_name_wins(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "sub").mkdir()
            (root / "AGENTS.md").write_text("ROOT RULES")
            (root / "sub" / "AGENTS.md").write_text("SUB RULES")
            (root / "sub" / "CLAUDE.md").write_text("IGNORED")
            out = discover_context(root / "sub", root)
            self.assertLess(out.index("ROOT RULES"), out.index("SUB RULES"))
            self.assertNotIn("IGNORED", out)

    def test_discovery_rejects_a_path_outside_the_root(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            with self.assertRaises(ValueError):
                discover_context(Path(a), Path(b))

    def test_compact_keeps_system_tail_and_pairs(self):
        msgs = convo(5, trailing_note=True)  # 12 body messages, tail would start on a tool result
        out, summary = compact(msgs, lambda p: "S1")
        self.assertEqual(out[0]["role"], "system")
        self.assertIn("S1", out[1]["content"])
        self.assertNotEqual(out[2]["role"], "tool")
        self.assertEqual(out[-1]["content"], "note")
        self.assertLess(len(out), len(msgs))

    def test_second_compaction_sees_the_first_summary(self):
        prompts = []
        def summarize(p):
            prompts.append(p)
            return "S2"
        compact(convo(6), summarize, previous="S1")
        self.assertIn("S1", prompts[-1])

    def test_nothing_to_compact_returns_input(self):
        msgs = convo(1)
        out, summary = compact(msgs, lambda p: "x")
        self.assertEqual(out, msgs)

    def test_compactor_middleware_fires_over_threshold(self):
        agent = Agent(FakeModel([reply("ok")]), {})
        agent.messages = convo(10)
        c = Compactor(lambda p: "S1", threshold_tokens=10)
        before = estimate_tokens(agent.messages)
        c(agent)
        self.assertLess(estimate_tokens(agent.messages), before)
        self.assertEqual(c.summary, "S1")


if __name__ == "__main__":
    unittest.main()
