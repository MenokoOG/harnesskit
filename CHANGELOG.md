# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Version is in `VERSION`.

## [0.1.0] - 2026-11-26

### Added
- Course reference build: modules 1 to 7 and the capstone, 43 tests.
- Adapter for OpenAI-style chat servers, and a sandboxed live eval.
- Tool parameter schemas built from function signatures.
- `LESSONS.md`.

### Fixed
- A newline in a command no longer auto-allows (CWE-184, incomplete list of disallowed inputs).
- The floor catches more `rm` spellings.
- Verify-on-stop needs a real checker that exited 0.
- Compaction no longer blinds the stuck detector or erases an unverified edit.
- Edit tools keep CRLF line endings.
- The `.env` hook also covers names such as `.env.local`.
