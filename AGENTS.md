# Repository Guidelines

## Project Structure & Module Organization
- Source code lives under `mcp2anp/`, arranged into `adapters/`, `tools/`, and `common/`; keep new runtime modules aligned with these boundaries.
- Tests mirror the runtime tree in `tests/` and share fixtures in `tests/fixtures/`; reuse JSON-RPC payloads stored there instead of duplicating literals.
- Store documentation and protocol notes in `docs/` (notably `docs/spec.md`), while diagrams, traces, and reference transcripts belong in `assets/`.
- Example client scripts reside in `examples/`; keep them minimal and cross-reference stable entry points such as `mcp2anp.server`.

## Build, Test, and Development Commands
- `uv venv --python 3.11`: create the canonical virtual environment before installing anything else.
- `uv sync`: install and lock dependencies from `pyproject.toml`; commit updated `uv.lock` and `uv.toml` when they change.
- `uv run python -m mcp2anp.server --reload`: start the local bridge with hot reload for integration testing.
- `uv run pytest [-k expr --maxfail=1]`: run the full suite or narrow to a focused subset during debugging.

## Coding Style & Naming Conventions
- Follow Google Python Style: four-space indentation, type hints on public APIs, English docstrings covering arguments, returns, and raised errors.
- Use `CamelCase` classes, `snake_case` functions and variables, and `UPPER_SNAKE_CASE` constants; keep module names short and descriptive.
- Log through `logging` with explicit context (IDs, endpoints) and keep inline comments in English; avoid stray prints.

## Testing Guidelines
- Write `pytest` modules named `test_<module>.py` alongside the unit under test; place reusable payloads in fixtures.
- Target at least 90% statement coverage, covering success, failure, and boundary scenarios for each adapter.
- Include a fresh `uv run pytest` summary in every PR description; add regression tests when reproducing reported defects.

## Commit & Pull Request Guidelines
- Craft imperative commit subjects under 72 characters; expand on complex changes with bullet points in the body.
- Reference issues with `Fixes:` or `Refs:` trailers and flag breaking updates under `BREAKING CHANGE:`.
- Open PRs with a concise summary, enumerated key changes, validation checklist (`uv run pytest`, lint, manual run), and attach screenshots or logs for user-visible behavior.

## Security & Configuration Tips
- Keep credentials out of the repo; prefer `.env` with documented variables like `ANP_RPC_ENDPOINT` and `ANP_DID_KEY_PATH`.
- Review dependency updates with `uv pip list --outdated`, note advisories, and capture significant risks in the PR discussion.
