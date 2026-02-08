# Scaling Agent VCR: Large-Scale, Multi-MCP, and Agent-to-Agent

This document describes how Agent VCR can evolve to support **large-scale** deployments, **multi-MCP server** flows, and **agent-to-agent** interactions, while staying backward compatible with today’s single-session model.

## Current Scope (v0.1)

- **One recording = one MCP session**: single client ↔ single server, one initialize handshake, one ordered list of interactions.
- **One replayer per file**: each `.vcr` is replayed independently.
- **Diff**: compares two recordings (e.g. baseline vs current server version).
- **Best for**: golden cassette tests, compatibility gates, offline dev, single-agent single-server testing.

Existing `.vcr` files and the CLI remain fully supported as we add scaling features.

---

## Target Capabilities

### 1. Large scale

- **Many cassettes**: thousands of recordings per project; fast load/index; optional SQLite or index file for search.
- **Large sessions**: very long interaction lists without OOM; streaming or chunked read/write; optional `max_interactions` (already present) and rotation.
- **Batch operations**: diff many baseline/current pairs in one run; bulk inspect; CI that touches hundreds of cassettes.

### 2. Multi-MCP

- **Multiple servers in one flow**: e.g. client talks to Server A (filesystem) and Server B (GitHub) in a single logical “run”; record and replay both with correct routing.
- **Session identity**: each recording has an optional `session_id` / `endpoint_id` so tooling can group and route (see Format extensions below).
- **Replay orchestrator**: one process that runs multiple replayers (one per server/endpoint) and routes incoming traffic by endpoint or session.

### 3. Agent-to-agent

- **Multiple agents**: Agent A calls Agent B’s MCP server; both sides can be recorded and replayed so full agent-to-agent flows are testable.
- **Correlation**: optional `agent_id` or tags in metadata to mark “recording from agent X” vs “recording from agent Y”; correlation IDs in tags for tracing across cassettes.
- **Orchestrated replay**: replay both sides from their own cassettes so integration tests don’t need live agents.

---

## Format Extensions (Backward Compatible)

All new fields are **optional**. Existing `.vcr` files remain valid.

### Metadata fields (VCRMetadata)

| Field          | Type   | Purpose |
|----------------|--------|--------|
| `session_id`   | string | Unique id for this session (e.g. UUID). Enables grouping in multi-session tooling. |
| `endpoint_id`  | string | Logical endpoint (e.g. `filesystem`, `github`, `agent-b`). Used by replay orchestrator to route. |
| `agent_id`     | string | Optional identifier for the “agent” or client (e.g. `search-agent`, `writer-agent`). |

These can be set via CLI (`--session-id`, `--endpoint-id`, `--agent-id`) or programmatically when building recordings. Default: omit; single-session behavior unchanged.

### Future: project / manifest (v0.3+)

- **Option A**: Directory with many `.vcr` files plus a manifest (e.g. `project.json`) listing `session_id`, `endpoint_id`, `file`, ordering hints.
- **Option B**: Single “project” file (e.g. `.vcr-project`) that references multiple `.vcr` paths and metadata. Replay orchestrator loads the project and routes by `endpoint_id`.

No change to the core `.vcr` schema is required for multi-session tooling; correlation is done via metadata and external manifest/project files.

---

## Proposed Tooling Evolution

### Phase 1 (v0.2) — Single-session hardening

- Per-request latency (fix interleaved-request inaccuracy).
- Full notification capture in recorder.
- Optional `asyncio.Lock` for shared state (thread-safety).
- CLI: expose `--session-id`, `--endpoint-id`, `--agent-id` for metadata (wired to existing optional fields).

### Phase 2 (v0.3) — Multi-session recording and replay

- **Multi-session recorder**: one process that runs multiple transports (e.g. one stdio + one SSE), each writing its own `.vcr` with `session_id` / `endpoint_id` set. Optional manifest file listing all recordings from the “run.”
- **Replay orchestrator**: CLI or library that loads N recordings (or a project manifest), starts N replayers (stdio/SSE), and routes traffic by `endpoint_id` or port/path. Enables “replay the whole flow” for one client talking to multiple servers.
- **Diff**: extend to compare two “projects” (e.g. two directories or two manifests) session-by-session by `session_id` / `endpoint_id`.

### Phase 3 (v0.4+) — Large-scale and agent-to-agent

- **Indexing**: optional index (e.g. SQLite or JSON index) over many `.vcr` files for fast search (by method, endpoint, agent_id, date).
- **Batch diff**: run many baseline/current pairs (e.g. from a matrix) and report a single compatibility report.
- **Agent-to-agent**: use `agent_id` and `endpoint_id` to record and replay both sides of an agent↔agent MCP flow; document patterns (e.g. “record agent A’s client session and agent B’s server session, then replay both”).

---

## Backward Compatibility

- Existing `.vcr` files load and replay unchanged; new metadata fields are optional and default to absent.
- Single-session CLI and API remain the default; multi-session features are additive (new commands or flags, e.g. `agent-vcr record --multi`, `agent-vcr replay --project`).
- Format version stays `1.0.0` until we introduce a breaking schema change (if ever); extensions are additive only.

---

## Summary

| Goal                | Approach |
|---------------------|----------|
| **Large scale**     | Many files + optional index; batch diff; streaming/chunking for huge sessions. |
| **Multi-MCP**       | Optional `session_id` / `endpoint_id` in metadata; multi-session recorder; replay orchestrator that routes by endpoint. |
| **Agent-to-agent**  | Optional `agent_id` and tags; record/replay both sides; orchestrated replay. |

We can scale the repo to handle large-scale, multi-MCP, and agent-to-agent workloads by adding optional metadata, then multi-session recorder and replay orchestrator, then indexing and batch operations—without breaking current single-session use.
