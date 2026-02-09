# We Just Open-Sourced Agent VCR — Deterministic Testing for MCP-Powered AI Agents

I'm excited to announce **Agent VCR**, an open-source testing framework for the Model Context Protocol (MCP). It's now live on [PyPI](https://pypi.org/project/agent-vcr/) and [npm](https://www.npmjs.com/package/@agent-vcr/core).

## The Problem We Solved

If your organization is adopting MCP — the protocol that connects AI agents to external tools and data — you've probably noticed the testing story is weak. Your agent tests depend on live MCP servers. They're slow, flaky, and impossible to run offline. When a server team ships an update, downstream agents break with no warning.

This isn't a niche issue. MCP adoption is accelerating across the industry, and every team building agents on MCP faces the same gap: there's no standard way to test MCP interactions without a live server.

## What Agent VCR Does

Think of it as "VCR cassettes for MCP." You record your MCP server interactions once against the real server, save them as `.vcr` files, and replay them in every test run — instant, deterministic, offline.

But the real differentiator for enterprise teams is the **diff engine**. Before deploying a new MCP server version, you record the new behavior and diff it against the baseline. Agent VCR detects breaking changes at the field level — removed fields, type changes, new error codes, latency regressions — and can fail your CI pipeline automatically.

For organizations running multiple AI agents against shared MCP infrastructure, this turns "deploy and hope" into "diff and verify."

## Key Capabilities

- **Record/Replay** — transparent proxy for both stdio and SSE transports, capturing the full JSON-RPC protocol including notifications and latencies
- **Breaking Change Detection** — field-level diff with compatibility analysis, latency regression detection, and CI integration via `--fail-on-breaking`
- **Cross-Language** — first-class Python and TypeScript implementations sharing the same `.vcr` format; 250+ Python tests, 72 TypeScript tests
- **Scale Features** — multi-MCP indexing, batch diffing, and cassette merging for teams managing dozens of MCP endpoints
- **Framework Integration** — pytest plugin (Python), Jest and Vitest support (TypeScript)

## Why This Matters for Enterprise

Three scenarios where Agent VCR changes the game:

**1. CI Reliability.** Your agent test suite runs in seconds instead of minutes, with zero external dependencies. No more flaky builds because an MCP server was down or rate-limited.

**2. Safe Deployments.** Before any MCP server update reaches production, the diff engine validates backward compatibility. Platform teams can gate deployments on automated compatibility checks.

**3. Cost Control.** MCP servers that call paid APIs (LLMs, databases, SaaS tools) cost money on every test run. Record once, replay forever — your test suite burns zero API quota.

## Get Started

```bash
pip install agent-vcr      # Python
npm install @agent-vcr/core  # TypeScript
```

The project is MIT-licensed and we welcome contributions. Whether you're an individual developer building MCP tools or an engineering lead evaluating testing strategies for your team's MCP infrastructure, I'd love to hear your feedback.

**GitHub:** https://github.com/jarvis2021/agent-vcr
**PyPI:** https://pypi.org/project/agent-vcr/
**npm:** https://www.npmjs.com/package/@agent-vcr/core

#MCP #AI #Testing #OpenSource #AIAgents #DeveloperTools #ModelContextProtocol
