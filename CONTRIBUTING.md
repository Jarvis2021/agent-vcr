# Contributing to Agent VCR

Thanks for your interest in contributing. Agent VCR is an open-source project and contributions are welcome.

## Getting Started

### Python

```bash
git clone https://github.com/jarvis2021/agent-vcr.git
cd agent-vcr/python

# Setup with uv (recommended — fast, handles venvs automatically)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

> **Why uv?** It's 10-100x faster than pip, creates isolated environments by default, and is the standard Python package manager in 2026. Install it with `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`.

### TypeScript

```bash
cd agent-vcr/typescript

npm install
npm run build
npm test
```

See [typescript/README.md](typescript/README.md) for full TypeScript usage and API docs.

## What We Need Help With

**High-impact areas:**

- **TypeScript tests** — The `typescript/` directory has unit tests (Vitest). Adding integration tests and more coverage is welcome.
- **More matching strategies** — Custom matchers, regex-based param matching, response template interpolation.
- **Transport plugins** — WebSocket transport, HTTP/2, custom protocol adapters.
- **Real-world cassettes** — Example `.vcr` recordings from popular MCP servers (filesystem, GitHub, Slack, etc.) for the test suite.
- **Documentation** — Tutorials, how-to guides, video walkthroughs.

**Good first issues:**

- Add `--timeout` flag to the `record` CLI command
- Implement `VCRRecording.merge()` to combine multiple recordings
- Add YAML output format to `inspect` command
- Write integration tests with a simple echo MCP server

## How to Contribute

### Bug Reports

Open an issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version and OS

### Code Changes

1. Fork the repo and create a branch from `main`
2. Write your code — follow the existing style (type hints, docstrings, Pydantic models)
3. Add tests — we aim for comprehensive coverage. If you add a feature, add tests.
4. Run the test suite: `pytest tests/ -v` (Python) or `npm test` (TypeScript, from `typescript/`)
5. Run the linter: `ruff check src/` (Python) or `npm run lint` (TypeScript)
6. Open a pull request with a clear description of what and why

### Code Style

- Python 3.10+ with type hints on all public functions
- Pydantic v2 for data models (`model_dump()`, `model_validate()`)
- Google-style docstrings with Args/Returns/Raises
- 100 character line length
- Use `ruff` for formatting and linting

See [CLAUDE.md](CLAUDE.md) for the full coding conventions, especially the "Critical API Rules" section — these are the patterns that trip people up most.

### Architecture Decisions

For significant changes (new transport, new matching strategy, file format changes), please open an issue first to discuss the approach. See [docs/architecture.md](docs/architecture.md) for the system design and known limitations.

## Project Structure

```
python/
├── src/agent_vcr/
│   ├── core/          # Data models, session, matcher
│   ├── transport/     # stdio and SSE proxies
│   ├── recorder.py    # Recording engine
│   ├── replayer.py    # Mock server
│   ├── diff.py        # Comparison engine
│   ├── cli.py         # CLI interface
│   └── pytest_plugin.py
└── tests/             # Unit tests (pytest)
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
