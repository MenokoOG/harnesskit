import unittest

from harnesskit.policy import ALLOW, DEFAULT_RULES, FORBIDDEN, PROMPT, Policy, Rule, gated


def fake_bash(cmd: str, timeout: int = 1) -> str:
    """Pretend shell."""
    return "ran:" + cmd


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.p = Policy(DEFAULT_RULES)

    def test_basic_decisions(self):
        self.assertEqual(self.p.decide("git status"), ALLOW)
        self.assertEqual(self.p.decide("git status --short"), ALLOW)
        self.assertEqual(self.p.decide("git push origin main"), PROMPT)
        self.assertEqual(self.p.decide("some-unknown-tool"), PROMPT)

    def test_floor_survives_yolo(self):
        for mode in ("default", "plan", "yolo"):
            self.assertEqual(self.p.decide("rm -rf /", mode), FORBIDDEN)
            self.assertEqual(self.p.decide("sudo rm -rf /", mode), FORBIDDEN)
        self.assertNotEqual(self.p.decide("rm -rf ./build", "yolo"), FORBIDDEN)

    def test_floor_catches_simple_variants(self):
        for cmd in ("rm -rf /*", "rm -fr /", 'sh -c "rm -rf /"'):
            self.assertEqual(self.p.decide(cmd, "yolo"), FORBIDDEN, cmd)
        # Known gap, left as the stretch exercise: long flags and ~ are not covered.
        self.assertNotEqual(self.p.decide("rm --recursive --force /", "yolo"), FORBIDDEN)

    def test_yolo_turns_prompts_into_allows(self):
        self.assertEqual(self.p.decide("git push", "yolo"), ALLOW)

    def test_plan_mode_is_read_only(self):
        self.assertEqual(self.p.decide("git status", "plan"), ALLOW)
        self.assertEqual(self.p.decide("touch x", "plan"), FORBIDDEN)

    def test_chains_never_auto_allow(self):
        self.assertEqual(self.p.decide("git status && git push"), PROMPT)
        self.assertEqual(self.p.decide("echo hi > out.txt"), PROMPT)

    def test_bad_example_fails_at_load(self):
        with self.assertRaises(ValueError):
            Policy([Rule(("git", "status"), ALLOW, not_match=(("git", "status"),))])

    def test_gate_blocks_denies_and_runs(self):
        ask_log = []
        def ask(cmd):
            ask_log.append(cmd)
            return False
        run = gated(fake_bash, self.p, "default", ask)
        self.assertTrue(run("rm -rf /").startswith("BLOCKED"))
        self.assertTrue(run("git push").startswith("DENIED"))
        self.assertEqual(run("echo hi"), "ran:echo hi")
        self.assertEqual(ask_log, ["git push"])


if __name__ == "__main__":
    unittest.main()
