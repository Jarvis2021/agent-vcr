# Introducing Agent VCR: Record, Replay, and Diff MCP Server Interactions

## TL;DR
If you're building with [Model Context Protocol (MCP)](https://modelcontextprotocol.io), your tests probably depend on live servers. They're slow, flaky, and expensive. **Agent VCR** records your MCP interactions once and replays them deterministically — like [VCR](https://github.com/vcr/vcr) / [Polly.JS](https://netflix.github.io/pollyjs/) but purpose-built for the MCP JSON-RPC protocol. Plus it diffs recordings to catch breaking changes before they ship.

Available now: **[PyPI](https://pypi.org/project/agent-vcr/)** | **[npm](https://www.npmjs.com/package/@agent-vcr/core)** | **[GitHub](https://github.com/jarvis2021/agent-vcr)**

---

## The Testing Gap in MCP

The MCP ecosystem has exploded. The official SDK sees tens of millions of monthly downloads, there are thousands of community MCP servers, and every major AI lab is integrating MCP into their agent workflows.

But here's the thing nobody talks about: **testing MCP is still painful.**

If you're building an MCP client — say, an AI agent that calls tools via MCP — your tests look something like this:

```python
# What most MCP tests look like today
def test_my_agent():
    # Start the REAL MCP server
    server = subprocess.Popen(["python", "my_mcp_server.py"])
    # Connect to it
    client = MCPClient("http://localhost:3000/sse")
    # Call the tool
    result = client.call_tool("search", {"query": "test"})
    # Assert something
    assert result is not None
    server.kill()
```

This works until it doesn't. The server goes down. The API behind the server rate-limits you. The response format changes. Your CI pipeline fails for reasons that have nothing to do with *your* code.

The HTTP testing world solved this years ago. VCR (Ruby), Polly.JS (JavaScript), and pytest-recording (Python) all record HTTP interactions and replay them. But MCP isn't HTTP — it's JSON-RPC 2.0 over stdio or SSE, with bidirectional communication, server-initiated notifications, and a specific protocol handshake. Generic HTTP mocking doesn't fit.

## What Agent VCR Does

Agent VCR sits between your MCP client and server as a transparent proxy. It records every JSON-RPC interaction — requests, responses, notifications, latencies — into a `.vcr` cassette file. Then it replays them.

```
Record (once)                    Replay (every test run)
─────────────                    ───────────────────────
Client ←→ Agent VCR ←→ Server   Client ←→ Agent VCR (mock)
              │                               │
              └──→ session.vcr ───────────────┘
```

### Record

```bash
pip install agent-vcr  # or: npm install @agent-vcr/core

# Record a stdio-based MCP server
agent-vcr record \
  --transport stdio \
  --server-command "python my_server.py" \
  -o golden.vcr

# Record an SSE-based MCP server
agent-vcr record \
  --transport sse \
  --server-url http://localhost:3000/sse \
  -o golden.vcr
```

### Replay

```bash
# Replay as a mock stdio server
agent-vcr replay --file golden.vcr --transport stdio

# Replay as a mock SSE server on port 3100
agent-vcr replay --file golden.vcr --transport sse --port 3100
```

Your tests now talk to the replayer instead of the real server. Instant, deterministic, offline.

### Diff

This is where Agent VCR goes beyond simple record/replay. Suppose your team updates the MCP server. Did anything break?

```bash
agent-vcr diff v1.vcr v2.vcr --fail-on-breaking
```

The diff engine compares every interaction between two recordings and classifies changes:

- **Added methods** — new capabilities, non-breaking
- **Removed methods** — breaking
- **Modified responses** — the engine checks field-level compatibility: removed fields are breaking, type changes are breaking, added fields are safe
- **Error code changes** — switching error codes is breaking
- **Latency regressions** — optionally flag responses that got significantly slower

This turns MCP server upgrades from "deploy and pray" into "diff and verify."

## Why Not Just Mock It Yourself?

You could write manual mocks. Many teams do. But there are good reasons to use Agent VCR instead.

**Completeness.** A hand-rolled mock captures whatever you remembered to mock. Agent VCR records *everything* — the initialize handshake, capability negotiation, all tool calls and responses, server notifications, error cases, and exact latencies. You get a complete picture of what the server actually does.

**Maintenance.** When the server changes, hand-rolled mocks require manual updates. With Agent VCR, you re-record one cassette and all tests update automatically. If the new behavior is incompatible, the diff catches it.

**Distribution.** If you maintain an open-source MCP server, you can ship `.vcr` cassettes alongside your server. Users can test their clients without ever installing or running your server. This is a distribution model that doesn't exist anywhere else in the MCP ecosystem.

**Cross-language.** The `.vcr` format is plain JSON. Record in Python, replay in TypeScript — or the reverse. Both implementations are first-class.

## Pytest Integration

For Python teams, Agent VCR ships as a pytest plugin:

```python
@pytest.mark.vcr("cassettes/golden.vcr")
def test_tools_list(vcr_replayer):
    response = vcr_replayer.handle_request({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/list", "params": {}
    })
    assert len(response["result"]["tools"]) > 0
```

For TypeScript, there are Jest and Vitest integrations:

```typescript
import { withVCR } from '@agent-vcr/core/vitest';

test('tools list returns expected tools', withVCR('golden.vcr', async (replayer) => {
  const response = replayer.handleRequest({
    jsonrpc: '2.0', id: 1,
    method: 'tools/list', params: {}
  });
  expect(response.result.tools.length).toBeGreaterThan(0);
}));
```

## Features at a Glance

**Core:** Record, replay, and diff MCP JSON-RPC 2.0 interactions over stdio and SSE transports.

**Matching strategies:** Exact, method-only, method+params, subset (partial parameter matching), and sequential — choose the right tradeoff between strictness and flexibility for your tests.

**Latency simulation:** Replay recorded latencies to test timeout handling and performance-sensitive code paths.

**Notification replay:** MCP servers send notifications (progress updates, resource changes). Agent VCR captures and replays these alongside responses.

**Multi-MCP indexing:** Tag recordings with session/endpoint/agent IDs, index hundreds of cassettes, search across them, and batch-diff entire test suites.

**CLI tools:** `record`, `replay`, `diff`, `inspect`, `validate`, `merge`, `stats`, `index`, `search`, `diff-batch` — everything you need from the command line.

**Cross-language:** Python and TypeScript share the same `.vcr` format. 250+ tests in Python, 72 in TypeScript.

## Who Should Use This

**MCP server authors** — ship cassettes alongside your server so downstream clients can test without running it.

**AI agent teams** — stop your CI from depending on live MCP servers. Record golden cassettes, replay in milliseconds.

**Enterprise platform teams** — gate MCP server deployments on automated compatibility checks. Diff before you ship.

**Anyone paying for API calls behind MCP servers** — record once, never burn quota in tests again.

## Get Started

```bash
# Python
pip install agent-vcr

# TypeScript
npm install @agent-vcr/core
```

Then follow the [tutorial](https://github.com/jarvis2021/agent-vcr/blob/main/docs/tutorial.md) or dive into the [README](https://github.com/jarvis2021/agent-vcr).

---

**Links:**
- GitHub: [github.com/jarvis2021/agent-vcr](https://github.com/jarvis2021/agent-vcr)
- PyPI: [pypi.org/project/agent-vcr](https://pypi.org/project/agent-vcr/)
- npm: [npmjs.com/package/@agent-vcr/core](https://www.npmjs.com/package/@agent-vcr/core)
- Tutorial: [docs/tutorial.md](https://github.com/jarvis2021/agent-vcr/blob/main/docs/tutorial.md)

*Agent VCR is MIT-licensed and open for contributions.*
