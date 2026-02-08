# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Recorder: optional `pending_timeout_seconds` to evict stale pending requests (avoids unbounded memory growth).
- Recorder: optional `max_interactions` to cap recorded interactions.
- Atomic .vcr writes: save to a temp file then rename (Python `VCRRecording.save()` and recorder stop).
- Replayer (TypeScript): return a JSON-RPC error response when no matching interaction (instead of `null`).
- **Documentation:** demo/README-GIFS.md (how to create GIFs for all 12 labs with asciinema + agg) and demo/make-lab-gifs.sh (per-lab script for asciinema → GIF). Both tracked in repo (removed from .gitignore).
- **Documentation:** README, CONTRIBUTING, ARCHITECTURE, and TUTORIAL updated: TypeScript test suite noted; File Inventory includes README-GIFS.md and make-lab-gifs.sh.
- **Scaling:** [SCALING.md](SCALING.md) added — roadmap for large-scale, multi-MCP, and agent-to-agent. Optional metadata fields `session_id`, `endpoint_id`, `agent_id` (Python + TypeScript format, recorder, CLI `--session-id` / `--endpoint-id` / `--agent-id`).

## [0.1.0] - 2025-02-08

### Added

- Record MCP traffic to `.vcr` files (JSON-RPC 2.0 sessions).
- Replay recordings as deterministic mock servers (stdio and SSE).
- Diff two recordings and detect breaking changes.
- CLI: `record`, `replay`, `diff`, `inspect`, `convert`.
- Pytest plugin: `vcr_recording`, `vcr_replayer`, `vcr_recorder` fixtures and `@pytest.mark.vcr`.
- Five matching strategies: exact, method, method_and_params, fuzzy, sequential.
- Stdio transport with concurrent client/server message loops (client can send first, e.g. initialize).
- `--demo` for record command: pipe-based auto-send of tutorial requests (Lab 1).
- Empty recording on early stop (e.g. Ctrl+C before any client traffic).
- TypeScript implementation with aligned test suite (format, matcher, session, replayer, diff, bugfixes).

### Fixed

- `--server-command` now split with `shlex` so multi-argument commands work.
- Stdio deadlock when client sends before server: refactored to two concurrent read loops.

[Unreleased]: https://github.com/jarvis2021/agent-vcr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jarvis2021/agent-vcr/releases/tag/v0.1.0
