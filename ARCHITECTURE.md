# Architecture

Agent VCR is a testing framework for the Model Context Protocol (MCP). It transparently records JSON-RPC 2.0 interactions between MCP clients and servers, then replays them deterministically for testing.

This document covers the system design, data flow, design decisions, known limitations, and future direction.

## System Overview

```
                    ┌─────────────────────────────────────┐
                    │           Agent VCR Proxy            │
                    │                                      │
 ┌──────────┐      │  ┌───────────┐    ┌──────────────┐  │      ┌──────────┐
 │          │ JSON  │  │           │    │              │  │ JSON │          │
 │   MCP    │─RPC──▶│  │ Transport │───▶│  MCPRecorder │  │──RPC▶│   MCP    │
 │  Client  │◀──────│  │  (stdio   │◀───│  (captures   │  │◀─────│  Server  │
 │          │       │  │   / SSE)  │    │   to .vcr)   │  │      │          │
 └──────────┘      │  └───────────┘    └──────┬───────┘  │      └──────────┘
                    │                          │           │
                    └──────────────────────────┼───────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  .vcr file   │
                                        │  (JSON)      │
                                        └──────┬──────┘
                                               │
                          ┌────────────────────┼────────────────────┐
                          │                    │                    │
                          ▼                    ▼                    ▼
                   ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
                   │ MCPReplayer │    │   MCPDiff     │    │  CLI inspect │
                   │ (mock       │    │ (regression   │    │  (human-     │
                   │  server)    │    │  detection)   │    │   readable)  │
                   └─────────────┘    └──────────────┘    └──────────────┘
```

## Layer Architecture

The codebase is organized into four layers, each with a clear responsibility:

```
┌──────────────────────────────────────────────────────┐
│  Integration Layer                                    │
│  cli.py  ·  pytest_plugin.py                         │
├──────────────────────────────────────────────────────┤
│  Engine Layer                                         │
│  recorder.py  ·  replayer.py  ·  diff.py             │
├──────────────────────────────────────────────────────┤
│  Core Layer                                           │
│  core/format.py  ·  core/session.py  ·  core/matcher │
├──────────────────────────────────────────────────────┤
│  Transport Layer                                      │
│  transport/base.py  ·  transport/stdio.py  ·  sse.py │
└──────────────────────────────────────────────────────┘
```

**Transport Layer** handles the raw communication protocol. `BaseTransport` defines the abstract interface; `StdioTransport` spawns a subprocess and proxies stdin/stdout; `SSETransport` runs an HTTP server and proxies Server-Sent Events. Each transport accepts message callbacks and forwards JSON-RPC messages bidirectionally.

**Core Layer** provides the data models and utilities that the rest of the system builds on. `format.py` defines the Pydantic models for the `.vcr` file format (VCRRecording, VCRSession, VCRInteraction, JSON-RPC messages). `session.py` manages the recording lifecycle and state transitions (idle → recording → idle). `matcher.py` implements the five request-matching strategies used during replay.

**Engine Layer** contains the three primary operations. `MCPRecorder` orchestrates transparent proxying and recording by wiring a transport to a session manager. `MCPReplayer` loads a `.vcr` file and acts as a mock MCP server, responding to requests with recorded responses. `MCPDiff` compares two recordings and identifies added, removed, modified, and breaking changes.

**Integration Layer** exposes the engines to users. `cli.py` provides the `agent-vcr` command-line tool with record/replay/diff/inspect/convert subcommands. `pytest_plugin.py` provides pytest fixtures (`vcr_recording`, `vcr_replayer`, `vcr_recorder`) and an async context manager (`vcr_cassette`) for seamless test integration.

## Data Flow

### Recording Flow

```
1. User starts recording via CLI or API
2. MCPRecorder creates a Transport (stdio or SSE)
3. Transport.start() is called with two callbacks:
   - on_client_message: invoked for each client → server message
   - on_server_message: invoked for each server → client message
4. Transport spawns the real MCP server and begins proxying

5. For each client message:
   a. Transport receives JSON from client stdin/HTTP
   b. Transport parses JSON, invokes on_client_message callback
   c. MCPRecorder parses into JSONRPCRequest
   d. Request is stored in _pending_requests[msg_id] with timestamp
   e. Transport forwards the original message to the real server

6. For each server message:
   a. Transport receives JSON from server stdout/SSE
   b. Transport parses JSON, invokes on_server_message callback
   c. MCPRecorder parses into JSONRPCResponse
   d. Response is paired with pending request via msg_id
   e. SessionManager.record_interaction() creates a VCRInteraction
   f. Transport forwards the original message to the client

7. User stops recording (Ctrl+C or API call)
8. MCPRecorder.stop() → SessionManager.stop_recording() → VCRRecording
9. VCRRecording.save(path) writes JSON to disk
```

### Replay Flow

```
1. MCPReplayer.from_file() loads .vcr file → VCRRecording
2. Interactions are extracted from recording.session.interactions
3. RequestMatcher is initialized with chosen strategy

4. For each incoming request:
   a. Check response overrides (for test error injection)
   b. Find matching recorded interaction via RequestMatcher
   c. Extract the recorded response
   d. Return response with the incoming request's ID

5. Replayer can serve via:
   - serve_stdio(): reads stdin, writes stdout (pipe-friendly)
   - serve_sse(): HTTP+SSE server on configurable host/port
   - handle_request(): direct programmatic call (for tests)
```

### Diff Flow

```
1. MCPDiff.compare() loads both baseline and current recordings
2. Interactions are indexed by method name
3. For each method in current:
   - If not in baseline → added (potential breaking change)
   - If in baseline → find matching interaction by method+params
     - If match found → deep-diff request and response
     - If no match → added
4. For each method in baseline not in current → removed (breaking)
5. Each modification is checked for backwards compatibility:
   - Success → error transition = breaking
   - Missing required response fields = breaking
6. Result contains: added, removed, modified, breaking_changes
```

## VCR File Format

The `.vcr` format is a JSON file with three top-level sections:

```
VCRRecording
├── format_version: "1.0.0"
├── metadata: VCRMetadata
│   ├── version, recorded_at, transport
│   ├── client_info, server_info
│   ├── server_command, server_args
│   └── tags (arbitrary key-value pairs)
└── session: VCRSession
    ├── initialize_request: JSONRPCRequest
    ├── initialize_response: JSONRPCResponse
    ├── capabilities: dict
    └── interactions: List[VCRInteraction]
        ├── sequence (0-indexed)
        ├── timestamp (ISO 8601)
        ├── direction (client_to_server | server_to_client)
        ├── request: JSONRPCRequest
        ├── response: JSONRPCResponse (optional)
        ├── notifications: List[JSONRPCNotification]
        └── latency_ms
```

The format captures the full MCP session lifecycle: the initialize handshake, server capabilities, and all subsequent request/response interactions with timing data.

## Matching Strategies

The replayer supports five strategies for matching incoming requests to recorded interactions:

| Strategy | How It Matches | Best For |
|----------|----------------|----------|
| `exact` | Full JSON equality of request (excluding `jsonrpc` field) | Strictest regression tests |
| `method` | Method name only | Broad acceptance tests |
| `method_and_params` | Method name + full params equality | Standard testing (default) |
| `fuzzy` | Method name + params subset (dict keys in request must exist in recorded) | Flexible/partial matching |
| `sequential` | Returns interactions in order, ignoring request content | Ordered replay scripts |

## Design Decisions

**Why Pydantic for data models?** Validation at the boundary. MCP interactions are complex nested JSON; Pydantic ensures the `.vcr` files are always structurally valid and provides free serialization/deserialization.

**Why JSON for the `.vcr` format?** Human readability. Developers need to inspect cassettes, diff them with standard tools, and edit them manually. JSON + pretty-print wins over binary or YAML for this use case.

**Why callback-based transport?** Decoupling. The transport layer doesn't know about recording or replaying; it just forwards messages and invokes callbacks. This lets the same transport code serve both MCPRecorder and future use cases.

**Why single-session recordings?** Simplicity. MCP sessions have a clear lifecycle (initialize → interact → close). Multi-session recordings would add complexity without clear benefit for the primary testing use case.

## Known Limitations and Future Work

### Latency Accuracy
The current latency calculation measures time between consecutive `record_interaction()` calls rather than the true round-trip time for each specific request. For interleaved requests (multiple in-flight), latency values will be inaccurate. A future version should use per-request timestamps from the pending requests tracker.

### Notification Handling
The data model supports notifications (VCRInteraction.notifications), but the recorder does not currently capture server-initiated notifications. These are parsed as responses and may be lost. Full notification support is planned.

### Transaction Safety
File writes are not atomic. If the process crashes during `VCRRecording.save()`, the output file may be incomplete. A future version should write to a temporary file and rename atomically.

### Transport Extensibility
Adding new transports requires modifying `MCPRecorder.start()`. A transport factory or registry pattern would allow pluggable transports without modifying core code.

### Thread Safety
Shared state (`_pending_requests`, `_is_recording`) is not synchronized with locks. This is safe under CPython's GIL with single-threaded asyncio, but is not guaranteed by the Python language specification. Production deployments should add `asyncio.Lock` guards.

## Module Reference

| Module | Lines | Responsibility |
|--------|-------|----------------|
| `core/format.py` | 242 | Pydantic models for .vcr format |
| `core/session.py` | 268 | Recording lifecycle management |
| `core/matcher.py` | 226 | Request matching strategies |
| `transport/base.py` | 89 | Abstract transport interface |
| `transport/stdio.py` | 331 | Subprocess stdio proxy |
| `transport/sse.py` | ~418 | HTTP+SSE proxy |
| `recorder.py` | ~388 | Transparent recording proxy |
| `replayer.py` | ~352 | Mock server from recordings |
| `diff.py` | ~554 | Recording comparison engine |
| `cli.py` | ~490 | Command-line interface |
| `pytest_plugin.py` | ~299 | Pytest integration |
