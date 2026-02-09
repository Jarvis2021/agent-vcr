# Scaling Agent VCR: Large-Scale, Multi-MCP, and Agent-to-Agent

This document describes the **implemented** scaling features and the design behind them: multi-MCP, agent-to-agent, indexing, and batch diff. It is the design and reference for "how we scale," not a future roadmap — everything below is in the repo today.

Agent VCR supports **multi-MCP** and **agent-to-agent**: record multiple sessions (one `.vcr` per session), tag with `--session-id` / `--endpoint-id` / `--agent-id`, and replay each as needed. Indexing (`agent-vcr index` / `search`) and batch diff (`agent-vcr diff-batch`) work over many cassettes. Backward compatible with one `.vcr` per session.

## Core scope (single session)

- **One recording = one MCP session**: single client ↔ single server, one initialize handshake, one ordered list of interactions.
- **One replayer per file**: each `.vcr` is replayed independently.
- **Diff**: compares two recordings (e.g. baseline vs current server version).
- **Best for**: golden cassette tests, compatibility gates, offline dev, single-agent single-server testing.

Existing `.vcr` files and the CLI remain fully supported.

---

## Target capabilities (what we support today)

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

### Project manifest (implemented)

- Directory with many `.vcr` files plus a manifest (e.g. `project.json`) listing `session_id`, `endpoint_id`, `path`. CLI: `record-project`, `replay --project`, `diff --baseline-project` / `--current-project`.

No change to the core `.vcr` schema; correlation is done via metadata and the manifest.

---

## Implemented tooling

- **Single-session**: Per-request latency, threading.Lock, CLI `--session-id` / `--endpoint-id` / `--agent-id`.
- **Multi-session**: Manifest load/save, `record-project`, `replay --project`, `diff --baseline-project` / `--current-project`.
- **Indexing**: `agent-vcr index <dir> -o index.json`, `agent-vcr search index.json` (by method, endpoint_id, agent_id).
- **Batch diff**: `agent-vcr diff-batch pairs.json` (multiple baseline/current pairs, single report, optional `--fail-on-breaking`).
- **Agent-to-agent patterns**: Documented below (record both sides, replay one or both, use index/search/diff-batch for correlation).

---

## Agent-to-Agent Patterns

When **Agent A** talks to **Agent B** over MCP (A is the client, B exposes an MCP server), you can record and replay both sides so integration tests do not need live agents.

### Recording both sides

1. **Record Agent A client session** (A to B): run the recorder between A and B, tag with `--agent-id agent-a` and `--endpoint-id agent-b`. Save as e.g. `agent-a-to-b.vcr`.
2. **Record Agent B server session** (B view of A requests): same flow from B perspective; tag with `--agent-id agent-b` and `--endpoint-id agent-a`. Save as e.g. `agent-b-from-a.vcr`.

One recorder run captures the single client-server stream; use `--agent-id` and `--endpoint-id` to identify client (agent) and server (endpoint).

### Replaying both sides

- **Replay one side:** Run `agent-vcr replay --file agent-a-to-b.vcr` so your test client (playing A role) talks to the replayer instead of B. No live B needed.
- **Replay both:** Start two replayers (one per cassette), each on a different port or stdio. Connect Agent A to replayer 1 and Agent B to replayer 2. Both sides are deterministic from cassettes.

### Correlation and indexing

- Use `agent-vcr index <dir> -o index.json` then `agent-vcr search index.json --agent-id agent-a` or `--endpoint-id agent-b` to find recordings.
- Use `agent-vcr diff-batch pairs.json --fail-on-breaking` to compare baseline vs current cassettes for multiple pairs in one report.


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
| **Agent-to-agent**  | Optional `agent_id` and tags; record/replay both sides; orchestrated replay (see Agent-to-Agent Patterns above). |

We can scale the repo to handle large-scale, multi-MCP, and agent-to-agent workloads by adding optional metadata, then multi-session recorder and replay orchestrator, then indexing and batch operations—without breaking current single-session use.

