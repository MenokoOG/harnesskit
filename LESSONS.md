# Lessons learned

From building the course's seven modules and capstone into one repo, with Claude, on 2026-11-26.

The reference build passed all 43 of its tests. Probing past those tests found the bugs below. Each fix has a regression test in `tests/test_regressions.py`.

## 1. A green suite only covers the questions it asks

All 43 tests passed while plan mode, the read-only mode, could still write files.

## 2. A newline is a command separator

The policy refused to auto-allow `;`, `&`, `|`, backticks, `$`, `<` and `>`. It missed `\n`. `echo hi\ntouch pwned` was allowed in plan mode, and the probe confirmed the file got created. `shlex.split` treats a newline as whitespace, the shell treats it as a new command. The check and the executor have to parse input the same way.

## 3. A pattern floor misses spellings

In yolo mode `rm --recursive --force /`, `rm -rf ~`, `rm -rf -- /` and `/bin/rm -rf '/'` were all allowed. The course names the first two as known gaps. The fix reads tokens, flags and targets. `find / -delete` or a short script still gets past it, so real isolation needs a sandbox (the paper's Recommendation 10).

## 4. "A check ran" and "a check passed" are different claims

The verify-on-stop guard looked for words in the command. `echo pytest` satisfied it, and so did a test run that failed. The capstone test itself passed the guard with `echo unittest ok`. The guard now needs a real checker command and `exit=0`.

## 5. Two correct modules can break each other

Compaction shortens the message list. The stuck detector kept a list index into it, so with both on, 20 identical calls ran to the turn limit instead of halting at 6. The verify guard rebuilt its state from history, so compaction could drop the unverified edit. Track call ids and keep state in the guard. Each module's own tests passed the whole time.

## 6. A fake model hides what a real model needs

Tool schemas carried a name and a description, with no parameters. A scripted fake never has to guess argument names. A real model does. The schema now comes from each function's signature.

## 7. "Edit one line" changed every line

On a file with Windows line endings, `edit` and `search_replace` rewrote every CRLF as LF. Python's text mode does that silently. Both tools now read and write with `newline=""`.

## Still open

These are known and not fixed.

- `cat` and `ls` auto-allow on any path, so plan mode can read `.env` or SSH keys. "Read-only" says nothing about secrets.
- The `.env` hook covers the file tools. A shell redirect goes around it: default mode asks first, yolo does not.
- `read_file` and `write_file` aren't limited to the project folder.
- `max_seconds` is checked between turns, so one long tool call can run past it.
- Compaction doesn't keep the original task word for word.
- A model transport error ends the run. No retry.
- The verify guard doesn't see files changed through the shell.

## What was cut, and what I'd add next

Not built: OS sandbox (R10), ACP server (R13), MCP (part of R14), per-model provider metadata (most of R2), reactive compaction (part of R7).

Suggested order: R10 first, because items 2 and 3 show how far string checks go. Then reactive compaction, because a context overflow currently ends the run.

## Limits on what the paper claims (section 15.6)

- The authors read source code. They didn't run the eleven systems on a shared task set.
- The Claude Code analysis rests on a publicly circulated March 2026 source snapshot, which makes it the hardest to reproduce.

## My notes

What surprised me most is that all 43 tests passed while plan mode could still write files. Plan mode is supposed to be read only. A passing test suite only told me about the things the tests asked.

The next one was the newline. The policy blocked other ways to chain commands, but a new line got through. So, the safety check has to read a command the same way the shell runs it.

My takeaway is that string checks are not a sandbox. The known gaps are still open, and a sandbox is what I would add first. This is a learning project and I would not trust it with a machine I care about.
