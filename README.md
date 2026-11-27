# harnesskit

A small coding-agent harness in Python, built through a seven-module course on harness engineering. Standard library only, Python 3.10 or newer.

The course follows [Harness Engineering: Anatomy, Architecture, and Evolution of Coding Agents](https://arxiv.org/abs/2609.00006) (Barbaste, Darrigol, Vu and Wiltberger, 2026).

This is a learning project. It is not production software and its command policy is not a security boundary. Don't give it a shell on a machine you care about.

## Provenance

The reference code came from a course Claude generated for me. Fixes, the model adapter, the live eval and these docs were built with Claude. Git history keeps the published reference build as its own commit, so every change on top of it is visible.

## Run the tests

```bash
python3 -m unittest discover -s tests -t .
```

56 tests, offline, no API key.

## Run against a local model

Needs Docker, a llama.cpp server image and a GGUF model that supports tool calls. The agent runs in a throwaway container with no internet and the repo mounted read-only.

```bash
MODEL_DIR=/path/to/models MODEL_FILE=model.gguf LLAMA_IMAGE=your-llama-image evals/run.sh 3
```

## Layout

| Module | Files |
|---|---|
| 1. Agent loop | `model.py`, `loop.py`, `tools.py`, `schema.py` |
| 2. Guards | `guards.py`, `verify.py` |
| 3. Tools and edits | `edit.py`, `textio.py`, `toolsearch.py` |
| 4. Context | `context.py` |
| 5. Safety | `policy.py`, `floor.py` |
| 6. Extension | `extend.py` |
| 7. Prompts | `prompt.py` |
| Capstone | `assemble.py`, `openai_compat.py`, `evals/` |

What broke and what's still open: [LESSONS.md](LESSONS.md).
