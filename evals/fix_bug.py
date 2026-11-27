"""Live eval: can the assembled agent fix one planted bug? Run only inside a disposable container.

The score comes from running the tests afterwards, never from what the model says.
"""
import json
import os
import pathlib
import subprocess
import sys
import time

from harnesskit.assemble import build_agent
from harnesskit.openai_compat import OpenAICompatModel
from harnesskit.verify import is_verifier

SOURCE = 'def average(values):\n    """Return the mean of a non-empty list."""\n    return sum(values) / (len(values) - 1)\n'
TESTS = '''import unittest

from calc import average


class T(unittest.TestCase):
    def test_average(self):
        self.assertEqual(average([2, 4, 6]), 4)


if __name__ == "__main__":
    unittest.main()
'''
TASK = ("The tests in the current folder fail. Find the bug in calc.py, fix it, "
        "run `python3 -m unittest test_calc`, then say what you changed. Do not edit the tests.")


def main(trial: int) -> None:
    root = pathlib.Path(f"/tmp/trial{trial}")
    (root / "skills").mkdir(parents=True)
    (root / "calc.py").write_text(SOURCE)
    (root / "test_calc.py").write_text(TESTS)
    os.chdir(root)
    model = OpenAICompatModel(os.environ["MODEL_URL"])
    agent = build_agent(model, root=root, skills_dir=root / "skills", ask=is_verifier)
    agent.max_turns, agent.max_seconds = 12, 900.0
    started = time.monotonic()
    try:
        final = agent.run(TASK)
    except Exception as error:  # report the crash as the trial result
        final, agent.stop_reason = f"{type(error).__name__}: {error}", "crashed"
    seconds = time.monotonic() - started
    check = subprocess.run([sys.executable, "-m", "unittest", "test_calc"], capture_output=True, text=True)
    calls = [{"tool": c["name"], "args": c["args"]}
             for m in agent.messages if m["role"] == "assistant" for c in m.get("tool_calls") or []]
    results = [m["content"][:300] for m in agent.messages if m["role"] == "tool"]
    print(json.dumps({
        "trial": trial, "passed": check.returncode == 0 and (root / "test_calc.py").read_text() == TESTS,
        "stop_reason": agent.stop_reason, "turns": agent.turns, "seconds": round(seconds, 1),
        "calls": calls, "results": results, "final": final[:600]}))


if __name__ == "__main__":
    main(int(sys.argv[1]))
