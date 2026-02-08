# Agent VCR — Hands-On Tutorial

Learn Agent VCR by doing. This tutorial walks you through every use case with real commands you can run on your machine.

**Time:** ~30 minutes
**Prerequisites:** Python 3.10+, [uv](https://docs.astral.sh/uv/) (recommended) or pip

---

## Setup

Before starting, install `uv` (if you haven't already) and set up the project.

### Install uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# or with Homebrew
brew install uv
```

### Clone and install Agent VCR

```bash
# Clone the repo (skip if you already have it)
git clone https://github.com/jarvis2021/agent-vcr.git
cd agent-vcr/python

# Create a virtual environment and install with all dev dependencies
uv venv
source .venv/bin/activate    # macOS/Linux
uv pip install -e ".[dev]"

# Go back to repo root
cd ..

# Verify installation
agent-vcr --help
```

You should see the CLI help showing `record`, `replay`, `diff`, and `inspect` commands.

**TypeScript:** This tutorial uses the Python CLI and pytest. For the TypeScript/Node.js implementation, see [typescript/README.md](typescript/README.md). To run TypeScript tests: `cd typescript && npm install && npm run build && npm test`.

<details>
<summary>Alternative: using pip (not recommended)</summary>

```bash
cd agent-vcr/python
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd ..
agent-vcr --help
```

</details>

**Test the demo servers** (these are included in the repo):

```bash
# Start calculator v1 and send a test request
echo '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"tutorial","version":"1.0.0"}}}' | python demo/servers/calculator_v1.py
```

You should see a JSON response with `serverInfo.name: "calculator-server"` and `version: "1.0.0"`.

---

## Lab 1: Your First Recording

**Goal:** Record a live MCP session and save it as a `.vcr` cassette.

**Easiest option — automatic (no pasting):** From the repo root, run with `--demo`. The same requests are sent for you and the recording is saved. No copy-paste.

```bash
agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v1.py" \
  -o my-first-recording.vcr \
  --demo
```

You should see four JSON response lines in the terminal, then "Demo recording saved." Skip to Step 1.4 to inspect.

---

**Manual option — interactive:** If you don’t use `--demo`, you must send the requests yourself (see below).

### Step 1.1 — Record the session

```bash
agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v1.py" \
  -o my-first-recording.vcr
```

This starts the calculator server and opens an interactive proxy. Agent VCR sits between you (the client) and the server, recording everything. The process will wait for you to type or paste requests.

### Step 1.2 — Send requests through the proxy

**You must paste (or type) the following lines** into the same terminal. After each line you send, **one line of JSON will appear** — that’s the server’s response. Paste these one at a time (or paste the block and send line by line):

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"tutorial","version":"1.0.0"}}}
```

```json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"add","arguments":{"a":15,"b":27}}}
```

```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"multiply","arguments":{"a":6,"b":7}}}
```

Each request gets one JSON response line in the terminal from the real server; Agent VCR records both. If you don’t see any response after pasting, make sure you pressed Enter and that you’re in the same terminal where recording is running.

### Step 1.3 — Stop recording

Press `Ctrl+C` to stop. Your recording is saved to `my-first-recording.vcr`.

### Step 1.4 — Inspect your recording

```bash
# Default view
agent-vcr inspect my-first-recording.vcr

# Table format — nice columns for method, params, status, latency
agent-vcr inspect my-first-recording.vcr --format table

# JSON format — raw data, useful for piping to jq
agent-vcr inspect my-first-recording.vcr --format json
```

Try all three formats. The default and table views are human-friendly; JSON is useful for scripting (`agent-vcr inspect file.vcr --format json | jq '.interactions[].method'`).

**What you learned:** Agent VCR transparently proxies MCP traffic and saves it as a replayable cassette file. Inspect it in multiple formats.

---

## Lab 2: Replaying a Recording

**Goal:** Use a recording as a mock server — no real server needed.

### Step 2.1 — Start the mock server

```bash
agent-vcr replay \
  --file my-first-recording.vcr \
  --transport stdio
```

This starts a mock server that responds from the recorded data (no real calculator server running).

### Step 2.2 — Send the same requests

```json
{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
```

```json
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"add","arguments":{"a":15,"b":27}}}
```

You get the exact same responses as the real server — instantly, deterministically, offline.

### Step 2.3 — Try a request that wasn't recorded

```json
{"jsonrpc":"2.0","id":99,"method":"tools/call","params":{"name":"subtract","arguments":{"a":10,"b":3}}}
```

The replayer has no match for this, so you'll see how it handles unmatched requests.

**What you learned:** Replaying replaces the real server entirely. Tests run fast, offline, and deterministically.

---

## Lab 3: Diffing Two Recordings

**Goal:** Compare v1 and v2 recordings to detect changes before they break clients.

### Step 3.1 — Record against the v2 server

```bash
agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v2.py" \
  -o calculator-v2-live.vcr
```

Send the same requests you used in Lab 1 (initialize, tools/list, tools/call for add and multiply), plus try the new `divide` tool:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"tutorial","version":"1.0.0"}}}
```

```json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

```json
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"add","arguments":{"a":15,"b":27}}}
```

```json
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"multiply","arguments":{"a":6,"b":7}}}
```

```json
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"divide","arguments":{"a":100,"b":3}}}
```

Press `Ctrl+C` to stop.

### Step 3.2 — Diff v1 vs v2

```bash
agent-vcr diff my-first-recording.vcr calculator-v2-live.vcr
```

You should see:
- **Server version changed:** 1.0.0 → 2.0.0
- **New capability:** resources
- **New tool:** divide
- **Modified responses:** add and multiply now return metadata
- **Verdict:** COMPATIBLE (no breaking changes — additions only)

### Step 3.3 — Try the pre-built sample recordings

If you skipped the recording steps, use the included samples:

```bash
agent-vcr diff examples/recordings/calculator-v1.vcr examples/recordings/calculator-v2.vcr
```

**What you learned:** Diffs catch schema changes, added/removed tools, and response differences between server versions.

---

## Lab 4: Golden Cassette Testing (Use Case #1)

**Goal:** Commit a "known good" recording to your repo and replay it in CI.

### Step 4.1 — Create the golden cassette

```bash
mkdir -p cassettes

agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v1.py" \
  -o cassettes/golden.vcr
```

Send requests that cover your critical path (initialize → tools/list → tools/call), then `Ctrl+C`.

### Step 4.2 — Write a test that uses the cassette

Create a file `tests/test_golden.py`:

```python
import pytest


@pytest.mark.vcr("cassettes/golden.vcr")
def test_tools_list_returns_tools(vcr_replayer):
    """Golden test: tools/list must return add and multiply."""
    response = vcr_replayer.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })
    tools = response["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "add" in tool_names
    assert "multiply" in tool_names


@pytest.mark.vcr("cassettes/golden.vcr")
def test_add_returns_correct_result(vcr_replayer):
    """Golden test: add(15, 27) must return 42."""
    response = vcr_replayer.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "add", "arguments": {"a": 15, "b": 27}}
    })
    assert response["result"]["content"][0]["text"] == "42"
```

### Step 4.3 — Run the test

```bash
cd python
pytest tests/test_golden.py -v
cd ..
```

The test runs against the recorded data — no live server needed. Commit `cassettes/golden.vcr` to your repo so CI replays it on every push.

### Step 4.4 — What happens when code breaks?

Edit `test_golden.py` to expect a different result (e.g., change `"42"` to `"43"`). Run `pytest` again — it fails immediately, catching the regression.

**What you learned:** Golden cassettes let you freeze a known-good interaction and replay it in CI forever.

---

## Lab 5: MCP Server Compatibility Gates (Use Case #2)

**Goal:** Block deploys when a server update introduces breaking changes.

### Step 5.1 — Record both versions

```bash
# Record v1 baseline
agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v1.py" \
  -o v1-baseline.vcr
# Send: initialize, tools/list, tools/call(add), tools/call(multiply), then Ctrl+C

# Record v2 candidate
agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v2.py" \
  -o v2-candidate.vcr
# Send the SAME requests, plus try divide, then Ctrl+C
```

### Step 5.2 — Gate the deploy

```bash
agent-vcr diff v1-baseline.vcr v2-candidate.vcr --fail-on-breaking
echo "Exit code: $?"
```

If v2 only adds things (new tools, extra fields), the diff says **COMPATIBLE** and exits with code 0. Your CI pipeline continues.

If v2 removed a tool or changed an existing response type, the diff says **BREAKING** and exits with code 1. The deploy is blocked.

### Step 5.3 — Add this to your CI

```yaml
# .github/workflows/compatibility.yml
- name: Check MCP compatibility
  run: |
    agent-vcr diff cassettes/baseline.vcr cassettes/current.vcr --fail-on-breaking
```

**What you learned:** `--fail-on-breaking` makes Agent VCR a CI gate that blocks incompatible server updates.

---

## Lab 6: Error Injection for Resilience Testing (Use Case #3)

**Goal:** Simulate server errors without modifying the server.

### Step 6.1 — Create a test with error injection

Create a file `tests/test_error_injection.py`:

```python
"""Test that the client handles server errors gracefully."""
from agent_vcr.core.format import VCRRecording
from agent_vcr.replayer import MCPReplayer


def test_handles_server_error():
    """Inject a server error and verify the client handles it."""
    # Load a normal recording
    recording = VCRRecording.load("examples/recordings/calculator-v1.vcr")
    replayer = MCPReplayer(recording, match_strategy="method_and_params")

    # First, verify the normal response works
    normal_response = replayer.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "add", "arguments": {"a": 15, "b": 27}}
    })
    assert "result" in normal_response
    assert normal_response["result"]["content"][0]["text"] == "42"

    # Now inject an error for the same request
    replayer.set_response_override(1, {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32603, "message": "Internal server error"}
    })

    # The same request now returns an error
    error_response = replayer.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "add", "arguments": {"a": 15, "b": 27}}
    })
    assert "error" in error_response
    assert error_response["error"]["code"] == -32603


def test_handles_timeout_simulation():
    """Use the error recording to test error handling paths."""
    recording = VCRRecording.load("examples/recordings/calculator-errors.vcr")
    replayer = MCPReplayer(recording, match_strategy="method_and_params")

    # This request triggers a "division by zero" error from the recording
    response = replayer.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "divide", "arguments": {"a": 10, "b": 0}}
    })
    assert "error" in response
    assert response["error"]["message"] == "Division by zero"
```

### Step 6.2 — Run the error injection tests

```bash
cd python
pytest tests/test_error_injection.py -v
cd ..
```

### Step 6.3 — Use the pre-built error recording

```bash
agent-vcr inspect examples/recordings/calculator-errors.vcr
```

You'll see the recorded errors: division by zero and method not found.

**What you learned:** You can inject arbitrary errors into recorded responses to test error handling paths without touching the real server.

---

## Lab 7: Offline Development (Use Case #4)

**Goal:** Record a session while online, then develop against the replay while offline.

### Step 7.1 — Record while you have a server

```bash
agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v1.py" \
  -o offline-dev.vcr
```

Send all the requests your client needs, then `Ctrl+C`.

### Step 7.2 — Go offline and replay

```bash
# Kill the real server, disconnect from the network — doesn't matter
agent-vcr replay \
  --file offline-dev.vcr \
  --transport stdio
```

Your client can now develop against the mock as if the real server were running.

### Step 7.3 — SSE variant (for web-based MCP servers)

If your server uses HTTP+SSE instead of stdio:

```bash
# Record (while server is running)
agent-vcr record --transport sse --server-url http://localhost:3000/sse -o sse-session.vcr

# Replay as a local SSE server (while offline)
agent-vcr replay --file sse-session.vcr --transport sse --port 3100
```

Now point your client to `http://localhost:3100/sse` and it works offline.

**What you learned:** Record once while connected, then develop indefinitely against the replay — on a plane, on bad WiFi, wherever.

---

## Lab 8: Multi-Agent Regression Testing (Use Case #5)

**Goal:** When multiple AI agents share MCP infrastructure, one team's server change can break another team's agent. Each team maintains their own cassettes and runs compatibility checks independently.

### Step 8.1 — Set up per-team cassette directories

Imagine two teams: **Team Search** (builds a search agent) and **Team Writer** (builds a writing agent). Both use the same calculator MCP server.

```bash
mkdir -p cassettes/team-search
mkdir -p cassettes/team-writer
```

### Step 8.2 — Each team records their own golden cassettes

**Team Search** records what they care about (tools/list + add):

```bash
agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v1.py" \
  -o cassettes/team-search/baseline.vcr
# Send: initialize, tools/list, tools/call(add), then Ctrl+C
```

**Team Writer** records their usage (tools/list + multiply):

```bash
agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v1.py" \
  -o cassettes/team-writer/baseline.vcr
# Send: initialize, tools/list, tools/call(multiply), then Ctrl+C
```

### Step 8.3 — Server team releases v2

The server team records against v2:

```bash
agent-vcr record \
  --transport stdio \
  --server-command "python demo/servers/calculator_v2.py" \
  -o cassettes/server-v2-candidate.vcr
# Send all known operations, then Ctrl+C
```

### Step 8.4 — Each team independently checks compatibility

```bash
# Team Search checks: will v2 break our agent?
agent-vcr diff cassettes/team-search/baseline.vcr cassettes/server-v2-candidate.vcr --fail-on-breaking
echo "Team Search: exit code $?"

# Team Writer checks: will v2 break our agent?
agent-vcr diff cassettes/team-writer/baseline.vcr cassettes/server-v2-candidate.vcr --fail-on-breaking
echo "Team Writer: exit code $?"
```

Both should pass (v2 only adds features). But if v2 had *removed* the multiply tool, Team Writer's check would fail while Team Search's would pass — catching the issue before deploy.

### Step 8.5 — Automate with CI

Each team adds their own compatibility check to their CI:

```yaml
# team-search/.github/workflows/mcp-compat.yml
- name: Check MCP server compatibility
  run: agent-vcr diff cassettes/team-search/baseline.vcr cassettes/latest-server.vcr --fail-on-breaking
```

**What you learned:** Each team maintains their own cassettes reflecting their agent's actual usage. When the shared server changes, every team independently verifies compatibility — no coordination needed.

---

## Lab 9: Protocol Evolution Tracking (Use Case #6)


**Goal:** Track how your server's behavior changes as the MCP spec evolves.

### Step 9.1 — Create a tracking script

Create a file `track_evolution.py`:

```python
"""Track how the calculator server evolves across versions."""
from agent_vcr.diff import MCPDiff


def track():
    result = MCPDiff.compare(
        "examples/recordings/calculator-v1.vcr",
        "examples/recordings/calculator-v2.vcr"
    )

    print("=== Protocol Evolution Report ===\n")

    if result.is_identical:
        print("No changes between versions.")
        return

    print(f"Added interactions:    {len(result.added_interactions)}")
    print(f"Removed interactions:  {len(result.removed_interactions)}")
    print(f"Modified interactions: {len(result.modified_interactions)}")
    print(f"Breaking changes:      {len(result.breaking_changes)}")
    print()

    if result.is_compatible:
        print("Verdict: COMPATIBLE — safe to upgrade")
    else:
        print("Verdict: BREAKING — review changes before upgrading")
        print("\nBreaking changes:")
        for change in result.breaking_changes:
            print(f"  - {change}")


if __name__ == "__main__":
    track()
```

### Step 9.2 — Run it

```bash
python track_evolution.py
```

### Step 9.3 — Build a version history

Over time, you record each server version:

```bash
agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v1.py" -o versions/v1.0.vcr
agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v2.py" -o versions/v2.0.vcr
# (add more versions as your server evolves)

# Compare any two
agent-vcr diff versions/v1.0.vcr versions/v2.0.vcr
```

**What you learned:** By recording each server version, you build a version history you can diff at any point to understand exactly what changed.

---

## Lab 10: Programmatic Recording (No Live Server)

**Goal:** Build recordings from code — useful for testing without a real server at all.

### Step 10.1 — Run the included example

```bash
cd python
python -m examples.python.create_sample_recording ../programmatic-sample.vcr
cd ..
```

Or run the example script directly:

```bash
python examples/python/create_sample_recording.py programmatic-sample.vcr
```

### Step 10.2 — Inspect and replay it

```bash
agent-vcr inspect programmatic-sample.vcr
agent-vcr replay --file programmatic-sample.vcr --transport stdio
```

### Step 10.3 — Build your own recording

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
recording.save("my-custom.vcr")
print("Saved my-custom.vcr!")
```

**What you learned:** You can build recordings entirely in code, which is useful for creating fixtures without needing any server at all.

---

## Lab 11: Pytest Integration

**Goal:** Use Agent VCR fixtures and markers in your test suite.

### Step 11.1 — The `@pytest.mark.vcr` marker

```python
# tests/test_with_marker.py
import pytest


@pytest.mark.vcr("examples/recordings/calculator-v1.vcr")
def test_tools_list(vcr_replayer):
    response = vcr_replayer.handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    })
    tools = response["result"]["tools"]
    assert len(tools) == 2
```

### Step 11.2 — The async context manager

```python
# tests/test_async.py
from agent_vcr.pytest_plugin import vcr_cassette


async def test_with_cassette():
    async with vcr_cassette("examples/recordings/calculator-v1.vcr") as cassette:
        response = cassette.replayer.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "add", "arguments": {"a": 15, "b": 27}}
        })
        assert response["result"]["content"][0]["text"] == "42"
```

### Step 11.3 — Recording in test mode

```bash
# Run tests in record mode (creates cassettes from live server)
cd python
pytest tests/ --vcr-record

# Specify a custom cassette directory
pytest tests/ --vcr-dir=my_cassettes
cd ..
```

### Step 11.4 — Match strategies

Try different matching strategies to see how they affect replay:

```python
from agent_vcr.core.format import VCRRecording
from agent_vcr.replayer import MCPReplayer

recording = VCRRecording.load("examples/recordings/calculator-v1.vcr")

# Strict: must match method AND full params
strict = MCPReplayer(recording, match_strategy="method_and_params")

# Loose: match by method name only
loose = MCPReplayer(recording, match_strategy="method")

# Ordered: return responses in sequence regardless of request
sequential = MCPReplayer(recording, match_strategy="sequential")

# Fuzzy: match method + subset of params
fuzzy = MCPReplayer(recording, match_strategy="fuzzy")

# Exact: full JSON deep-equal (strictest)
exact = MCPReplayer(recording, match_strategy="exact")
```

**What you learned:** Agent VCR integrates directly with pytest. Choose the match strategy that fits your testing needs — strict for golden tests, fuzzy for flexible integration tests.

---

## Lab 12: Recording the Demo with asciinema

**Goal:** Create a terminal recording you can embed in the README.

### Step 12.1 — Install asciinema

```bash
brew install asciinema        # macOS
# pip install asciinema       # or via pip
```

### Step 12.2 — Option A: Upload the pre-built recording

We've included a handcrafted `.cast` file in the repo:

```bash
asciinema upload demo/agent-vcr-demo.cast
```

It prints a URL — that's your embed link.

### Step 12.3 — Option B: Record a live session

```bash
asciinema rec demo/my-live-demo.cast -c "bash demo/record-demo.sh"
```

Preview it locally:

```bash
asciinema play demo/my-live-demo.cast
```

Then upload:

```bash
asciinema upload demo/my-live-demo.cast
```

### Step 12.4 — Update the README

Replace `DEMO_ID` in `README.md` with the ID from the asciinema URL:

```markdown
[![Agent VCR Demo](https://asciinema.org/a/YOUR_ID.svg)](https://asciinema.org/a/YOUR_ID)
```

**What you learned:** A live terminal demo is worth a thousand words in a README.

---

## Quick Reference

| Command | What It Does |
|---------|-------------|
| `agent-vcr record --transport stdio --server-command "CMD" -o FILE` | Record a live session |
| `agent-vcr replay --file FILE --transport stdio` | Replay as mock server |
| `agent-vcr diff FILE1 FILE2` | Compare two recordings |
| `agent-vcr diff FILE1 FILE2 --fail-on-breaking` | CI gate for compatibility |
| `agent-vcr inspect FILE` | Show recording details |
| `agent-vcr inspect FILE --format table` | Table view |
| `agent-vcr inspect FILE --format json` | Raw JSON output |

## File Inventory

| File | Purpose |
|------|---------|
| `demo/servers/calculator_v1.py` | Demo MCP server v1 (add, multiply) |
| `demo/servers/calculator_v2.py` | Demo MCP server v2 (adds divide, metadata) |
| `demo/record-demo.sh` | Script for recording the asciinema demo |
| `demo/agent-vcr-demo.cast` | Pre-built asciinema recording |
| `demo/README-GIFS.md` | How to create GIFs for all 12 labs (asciinema + agg) |
| `demo/make-lab-gifs.sh` | Run per-lab commands for asciinema → GIF (usage: `bash demo/make-lab-gifs.sh <1-12>`) |
| `examples/recordings/calculator-v1.vcr` | Sample cassette — v1 session |
| `examples/recordings/calculator-v2.vcr` | Sample cassette — v2 session |
| `examples/recordings/calculator-errors.vcr` | Sample cassette — error scenarios |

---

## Running tests (Python and TypeScript)

- **Python:** From `python/`, run `pytest tests/ -v`. See [CONTRIBUTING.md](CONTRIBUTING.md#getting-started).
- **TypeScript:** From `typescript/`, run `npm install`, `npm run build`, then `npm test`. See [typescript/README.md](typescript/README.md).

---

## Next Steps

After completing these labs, you're ready to:

1. **Record your own MCP servers** and build a cassette library
2. **Add golden cassette tests** to your CI pipeline
3. **Diff server versions** before deploying updates
4. **Inject errors** to harden your client's error handling
5. **Contribute to Agent VCR** — see [CONTRIBUTING.md](CONTRIBUTING.md)
