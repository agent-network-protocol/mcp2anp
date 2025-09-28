# Repository Guidelines

## Project Structure & Module Organization
- Place runtime modules in `src/mcp2anp/` with subpackages `adapters/`, `tools/`, and `common/` for shared helpers.
- Mirror that layout inside `tests/`, storing reusable ANP documents and JSON-RPC payloads under `tests/fixtures/`.
- Keep architectural notes in `docs/` (alongside `spec.md`) and diagrams or traces within `assets/`.

## Build, Test, and Development Commands
- `uv venv --python 3.11`: provision the supported virtual environment.
- `uv sync`: install dependencies from `pyproject.toml` and update `uv.lock`; commit both after changes.
- `uv run python -m mcp2anp.server --reload`: launch the bridge locally with hot reload.
- `uv run pytest`: execute the test suite; combine with `-k <pattern>` or `--maxfail=1` while debugging.

## Coding Style & Naming Conventions
- Follow the Google Python Style Guide: four-space indentation, explicit type hints, and English docstrings covering inputs, returns, and errors.
- Use `CamelCase` for classes, `snake_case` for functions and variables, and `UPPER_SNAKE_CASE` for constants; keep module names short.
- Emit diagnostics through `logging` with concise English messages that carry traceable context (session IDs, endpoints).

## Testing Guidelines
- Rely on `pytest`, adding `pytest-asyncio` for asynchronous flows; name files `test_<module>.py` beside the code under test.
- Cover success, failure, and boundary paths for each adapter, targeting ≥90% statement coverage; rely on fixtures or local fakes instead of live calls.
- Attach the latest `uv run pytest` summary to pull requests and add regression cases when new protocol behavior appears.

## Commit & Pull Request Guidelines
- Write commit subjects in imperative mood (e.g., `Add OpenRPC fallback handler`) and ≤72 characters; include body bullets for non-obvious context or validation.
- Link issues with `Fixes:` or `Refs:` trailers and flag incompatible updates under a `BREAKING CHANGE:` heading.
- Open PRs with a concise summary, list of key changes, validation checklist (`uv run pytest`, lint, manual run), and screenshots or logs for user-facing updates.

## Security & Configuration Tips
- Exclude real DID credentials from version control; keep sanitized placeholders in `docs/examples/` when demonstrations are required.
- Load sensitive configuration from environment variables such as `ANP_RPC_ENDPOINT` or `ANP_DID_KEY_PATH`, documenting defaults where appropriate.
- Before updating dependencies, run `uv pip list --outdated`, review advisories, and record major-version risks inside the PR description.
