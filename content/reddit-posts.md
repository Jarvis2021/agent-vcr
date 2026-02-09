# Reddit Posts (copy-paste ready)

---

## r/LocalLLaMA and r/MachineLearning

**Title:** I built an open-source record/replay tool for MCP — no more flaky agent tests against live servers

**Body:**

I've been building AI agents that use MCP (Model Context Protocol) to call tools, and testing was driving me crazy. Every test run depended on a live MCP server — slow, flaky, and breaks CI randomly.

So I built Agent VCR. It sits between your MCP client and server, records every JSON-RPC interaction into a `.vcr` file, and replays them deterministically. Like VCR cassettes for HTTP, but purpose-built for MCP's protocol (stdio + SSE transports, bidirectional notifications, capability negotiation).

The feature I'm most proud of is the **diff engine**. You can compare two recordings and it tells you exactly what broke — removed fields, type changes, new error codes, latency regressions. We use it to gate server deploys.

**What it does:**
- Record MCP interactions → save as `.vcr` cassettes
- Replay as a mock server (instant, offline, deterministic)
- Diff two recordings to catch breaking changes
- CLI: `record`, `replay`, `diff`, `validate`, `merge`, `stats`
- pytest plugin + Jest/Vitest integrations

**Both Python and TypeScript.** 250+ Python tests, 72 TypeScript tests. Same `.vcr` format works cross-language.

```
pip install agent-vcr
npm install @agent-vcr/core
```

GitHub: https://github.com/jarvis2021/agent-vcr

MIT licensed. Would love feedback — especially from anyone running multi-agent setups with shared MCP servers.

---

## r/Python

**Title:** agent-vcr: Record/replay/diff for MCP testing — pytest plugin included

**Body:**

I just published `agent-vcr` on PyPI — a testing tool for MCP (Model Context Protocol) that records JSON-RPC interactions and replays them deterministically.

**The problem:** If you're testing MCP clients or agents, your tests depend on live servers. Flaky, slow, and impossible to run offline or in CI reliably.

**The fix:** Record once, replay forever.

```bash
# Record against real server
agent-vcr record --transport stdio --server-command "python my_server.py" -o golden.vcr

# Replay in tests — instant, deterministic
agent-vcr replay --file golden.vcr --transport stdio
```

**pytest integration:**

```python
@pytest.mark.vcr("cassettes/golden.vcr")
def test_tools_list(vcr_replayer):
    response = vcr_replayer.handle_request({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/list", "params": {}
    })
    assert len(response["result"]["tools"]) > 0
```

**Other features:**
- Diff engine that detects breaking changes at the field level (type changes, removed fields, error code shifts)
- 6 matching strategies (exact, method, method_and_params, subset, sequential)
- Latency simulation for testing timeout handling
- CLI tools: `validate`, `merge`, `stats`, `index`, `search`, `diff-batch`
- 250+ tests, Python 3.10+

```
pip install agent-vcr
```

GitHub: https://github.com/jarvis2021/agent-vcr

Built with Pydantic, Click, aiohttp. Happy to answer questions about the architecture.

---

## r/node / r/typescript

**Title:** @agent-vcr/core — record/replay/diff MCP interactions in TypeScript. Jest + Vitest integrations.

**Body:**

Published `@agent-vcr/core` on npm — a testing library for MCP (Model Context Protocol) that records JSON-RPC interactions and replays them as a deterministic mock server.

If you're building MCP clients or AI agents in TypeScript, you know the pain: tests depend on live servers, CI is flaky, and mocking the full MCP protocol by hand is tedious.

Agent VCR records everything (initialize handshake, tool calls, notifications, latencies) into a `.vcr` file and replays it. One recording, infinite test runs.

```bash
npm install @agent-vcr/core
```

```typescript
import { withVCR } from '@agent-vcr/core/vitest';

test('tools list', withVCR('golden.vcr', async (replayer) => {
  const response = replayer.handleRequest({
    jsonrpc: '2.0', id: 1,
    method: 'tools/list', params: {}
  });
  expect(response.result.tools.length).toBeGreaterThan(0);
}));
```

**Key features:**
- Full CLI (`record`, `replay`, `diff`, `inspect`)
- Jest and Vitest integrations
- Diff engine detects breaking changes between server versions
- Cross-language: `.vcr` files work in both TypeScript and Python
- 72 unit tests, Zod schemas, ESM

GitHub: https://github.com/jarvis2021/agent-vcr

The Python implementation has 250+ tests and a few more CLI tools (`validate`, `merge`, `stats`). Same `.vcr` format — record in Python, replay in TypeScript or vice versa.

MIT licensed. Feedback welcome.

---

## Hacker News

**Title:** Show HN: Agent VCR – Record, replay, and diff MCP server interactions

**URL:** https://github.com/jarvis2021/agent-vcr

*(No body text — HN URL submissions don't have a body. The README is your pitch. If it makes the front page, be ready to respond to comments within minutes.)*

---

## Posting checklist

- [ ] **Hacker News** — post first (Tue-Thu, 8-10am ET). Respond to every comment.
- [ ] **r/LocalLLaMA** — post same day. Add a comment with backstory.
- [ ] **r/Python** — post same day or next day. Python-specific angle.
- [ ] **r/node** or **r/typescript** — post next day. TypeScript angle.
- [ ] **LinkedIn** — use linkedin-post.md. Attach cover image.
- [ ] **Twitter/X** — use twitter-thread.md. Post as thread. Pin to profile.
