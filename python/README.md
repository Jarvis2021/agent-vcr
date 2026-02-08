# Agent VCR

**Record, replay, and diff MCP interactions — like VCR for AI agents.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Agent VCR is a testing framework for the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). It transparently records all JSON-RPC 2.0 interactions between an MCP client and server, then replays them deterministically for testing — no real server needed.

## The Problem

If you're building MCP servers or clients, you've hit these walls:

**"My tests are flaky because they depend on a live server."** External MCP servers go down, rate-limit, or return different results each run. Your CI pipeline fails for reasons that have nothing to do with your code.

**"I can't test error handling without breaking the server."** How do you verify your client handles a timeout, a malformed response, or a server crash? You'd need to modify the server itself — or just hope for the best.

**"I shipped a breaking change and didn't catch it."** You updated your MCP server and a downstream client broke. There was no way to detect that `tools/call` started returning a different schema until a user filed a bug.

**"Testing against real APIs is slow and expensive."** Each test run hits the real server, waits for real responses, and burns through API quotas. A test suite that should take seconds takes minutes.

## How Agent VCR Solves This

Record your MCP interactions once against the real server, save them as `.vcr` cassettes, and replay them forever:

```
                Record (once)              Replay (every test run)
                ─────────────              ─────────────────────────
Client ←→ Agent VCR ←→ Real Server    Client ←→ Agent VCR (mock)
                │                                    │
                └──→ session.vcr ────────────────────┘
```

- **Deterministic**: Same input, same output, every time
- **Fast**: No network calls, instant responses
- **Offline**: Tests run without server access
- **Safe**: Inject errors without modifying the real server
- **Visible**: Diff two recordings to catch regressions before they ship

## Real-World Use Cases

### 1. Golden Cassette Testing
Record a "known good" session, commit the `.vcr` file to your repo, and replay it in CI. If your code changes break the interaction pattern, the test fails immediately.

```bash
# Record the golden cassette (once)
agent-vcr record --transport stdio --server-command "node my-server.js" -o cassettes/golden.vcr

# Every CI run replays it
pytest tests/ --vcr-dir=cassettes
```

### 2. MCP Server Compatibility Gates
Before deploying a new server version, record both old and new, then diff:

```bash
agent-vcr record --transport stdio --server-command "./server-v1" -o v1.vcr
agent-vcr record --transport stdio --server-command "./server-v2" -o v2.vcr
agent-vcr diff v1.vcr v2.vcr --fail-on-breaking
```

If `tools/call` changed its response schema, or a method was removed, the diff catches it and exits with code 1 — blocking the deploy.

### 3. Error Injection for Resilience Testing
Use response overrides to simulate failures without modifying the server:

```python
replayer = MCPReplayer(recording)

# Inject a server error for request id=3
replayer.set_response_override(3, {
    "jsonrpc": "2.0",
    "id": 3,
    "error": {"code": -32603, "message": "Internal server error"}
})

# Your client code should handle this gracefully
response = replayer.handle_request(request)
assert handle_error(response) == expected_fallback
```

### 4. Offline Development
Working on a plane? At a coffee shop with bad WiFi? Record your MCP server interactions beforehand and develop against the replay:

```bash
# Before going offline
agent-vcr record --transport sse --server-url http://localhost:3000/sse -o dev-session.vcr

# While offline — full mock server on port 3100
agent-vcr replay --file dev-session.vcr --transport sse --port 3100
```

### 5. Multi-Agent Regression Testing
When multiple AI agents share MCP infrastructure, one agent's server change can break another. Agent VCR lets each team maintain their own cassettes and run compatibility checks independently.

### 6. Protocol Evolution Tracking
As the MCP spec evolves, use diffs to track how your server's behavior changes across protocol versions:

```python
result = MCPDiff.compare("mcp-2024-11.vcr", "mcp-2025-03.vcr")
print(f"Added methods: {len(result.added_interactions)}")
print(f"Breaking changes: {len(result.breaking_changes)}")
```

## Quick Start

```bash
pip install agent-vcr
```

### Record a session

```bash
# Record stdio-based MCP server
agent-vcr record --transport stdio --server-command "node my-server.js" -o session.vcr

# Record SSE-based MCP server
agent-vcr record --transport sse --server-url http://localhost:3000/sse -o session.vcr
```

### Replay as a mock server

```bash
# Replay via stdio (pipe to your client)
agent-vcr replay --file session.vcr --transport stdio

# Replay via HTTP+SSE
agent-vcr replay --file session.vcr --transport sse --port 3100
```

### Diff two recordings

```bash
agent-vcr diff baseline.vcr current.vcr
agent-vcr diff baseline.vcr current.vcr --format json --fail-on-breaking
```

### Inspect a recording

```bash
agent-vcr inspect session.vcr
agent-vcr inspect session.vcr --format table
```

## Programmatic Usage

### Creating recordings manually

```python
from datetime import datetime
from agent_vcr.core.format import (
    JSONRPCRequest, JSONRPCResponse, VCRInteraction,
    VCRMetadata, VCRRecording, VCRSession,
)

# Build the initialize handshake
init_req = JSONRPCRequest(id=0, method="initialize", params={
    "protocolVersion": "2024-11-05",
    "clientInfo": {"name": "my-client", "version": "1.0.0"},
})
init_resp = JSONRPCResponse(id=0, result={
    "protocolVersion": "2024-11-05",
    "serverInfo": {"name": "my-server", "version": "1.0.0"},
    "capabilities": {"tools": {}},
})

# Build an interaction
interaction = VCRInteraction(
    sequence=0,
    timestamp=datetime.now(),
    direction="client_to_server",
    request=JSONRPCRequest(id=1, method="tools/list", params={}),
    response=JSONRPCResponse(id=1, result={
        "tools": [{"name": "echo", "description": "Echo a message"}]
    }),
    latency_ms=12.5,
)

# Assemble and save
recording = VCRRecording(
    metadata=VCRMetadata(
        version="1.0.0",
        recorded_at=datetime.now(),
        transport="stdio",
    ),
    session=VCRSession(
        initialize_request=init_req,
        initialize_response=init_resp,
        interactions=[interaction],
    ),
)
recording.save("session.vcr")
```

### Replaying in code

```python
from agent_vcr.core.format import VCRRecording
from agent_vcr.replayer import MCPReplayer

recording = VCRRecording.load("session.vcr")
replayer = MCPReplayer(recording, match_strategy="method_and_params")

response = replayer.handle_request({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
})
print(response)  # Returns the recorded response
```

### Diffing recordings

```python
from agent_vcr.diff import MCPDiff

result = MCPDiff.compare("baseline.vcr", "current.vcr")

if result.is_identical:
    print("No changes!")
elif result.is_compatible:
    print(f"Compatible changes: {len(result.modified_interactions)} modified")
else:
    print("Breaking changes detected!")
    for change in result.breaking_changes:
        print(f"  - {change}")
```

## Pytest Integration

Agent VCR includes a pytest plugin for seamless test integration.

### Using fixtures

```python
import pytest

@pytest.mark.vcr("cassettes/test_tools_list.vcr")
def test_tools_list(vcr_replayer):
    """Test that tools/list returns expected tools."""
    response = vcr_replayer.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })
    assert "result" in response
    assert len(response["result"]["tools"]) > 0
```

### Using the async context manager

```python
from agent_vcr.pytest_plugin import vcr_cassette

async def test_with_cassette():
    async with vcr_cassette("my_test.vcr") as cassette:
        response = cassette.replayer.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"message": "hello"}}
        })
        assert response["result"]["content"][0]["text"] == "hello"
```

### CLI options

```bash
pytest --vcr-record            # Record new cassettes
pytest --vcr-dir=my_cassettes  # Custom cassette directory
```

## Match Strategies

The replayer supports 5 matching strategies for finding recorded responses:

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `exact` | Full JSON match (excluding jsonrpc field) | Strictest testing |
| `method` | Match by method name only | Broad matching |
| `method_and_params` | Match method + full params *(default)* | Standard testing |
| `fuzzy` | Match method + partial params (subset) | Flexible testing |
| `sequential` | Return interactions in order | Ordered replay |

## VCR File Format

Recordings use a JSON-based `.vcr` format:

```json
{
  "format_version": "1.0.0",
  "metadata": {
    "version": "1.0.0",
    "recorded_at": "2026-02-07T10:30:00",
    "transport": "stdio",
    "client_info": {"name": "claude-desktop"},
    "server_info": {"name": "my-mcp-server"},
    "tags": {"env": "staging"}
  },
  "session": {
    "initialize_request": { "jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {} },
    "initialize_response": { "jsonrpc": "2.0", "id": 0, "result": { "capabilities": {} } },
    "capabilities": {},
    "interactions": [
      {
        "sequence": 0,
        "timestamp": "2026-02-07T10:30:05",
        "direction": "client_to_server",
        "request": { "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {} },
        "response": { "jsonrpc": "2.0", "id": 1, "result": { "tools": [] } },
        "latency_ms": 12.5
      }
    ]
  }
}
```

## Architecture

See [ARCHITECTURE.md](../ARCHITECTURE.md) for the full system design, data flow diagrams, and design decisions.

```
agent_vcr/
├── core/
│   ├── format.py      # Pydantic models for .vcr format
│   ├── matcher.py     # Request matching strategies
│   └── session.py     # Session lifecycle management
├── transport/
│   ├── base.py        # Abstract transport interface
│   ├── stdio.py       # Subprocess stdio proxy
│   └── sse.py         # HTTP+SSE proxy
├── recorder.py        # Transparent recording proxy
├── replayer.py        # Mock server from recordings
├── diff.py            # Recording comparison engine
├── cli.py             # Command-line interface
└── pytest_plugin.py   # Pytest integration
```

## Development

```bash
# Clone and install
git clone https://github.com/pvoola/agent-vcr.git
cd agent-vcr/python
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/agent_vcr --cov-report=html

# Lint
ruff check src/

# Type check
mypy src/
```

## Contributing

Contributions are welcome! Please see the [ARCHITECTURE.md](../ARCHITECTURE.md) for system design context and the [CLAUDE.md](../CLAUDE.md) for coding conventions.

## License

[MIT](../LICENSE)
