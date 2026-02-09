# LinkedIn Post (copy-paste ready)

---

Just open-sourced Agent VCR — record, replay, and diff MCP server interactions.

If you're building AI agents with MCP, your tests probably depend on live servers. They're slow, flaky, and break CI for reasons that have nothing to do with your code.

The testing options that exist today don't quite solve this. Some only work if your server is built with a specific framework. Others operate at the HTTP layer without understanding MCP's JSON-RPC protocol, notifications, or capability negotiation. The rest? Hand-roll your own mocks for every tool call. None of them give you record/replay/diff at the MCP protocol level.

Agent VCR fixes this. Framework-agnostic — works with any MCP server over stdio or SSE, regardless of how it was built. Record your MCP interactions once, save them as .vcr cassettes, replay them forever. Instant, deterministic, offline.

The part I'm most excited about: the diff engine. Before deploying a new MCP server version, diff it against the baseline. It catches removed fields, type changes, error code shifts, and latency regressions — automatically. Gate your deploys on compatibility.

Both Python and TypeScript are first-class. 250+ tests in Python, 72 in TypeScript. Same .vcr format across both.

Now live on PyPI and npm:

pip install agent-vcr
npm install @agent-vcr/core

GitHub: https://github.com/jarvis2021/agent-vcr

MIT licensed, fully open source. Contributions welcome.

#MCP #OpenSource #AIAgents #Testing #DeveloperTools

---

**Posting tips:**
- Attach the cover image (medium-cover-image.png) when posting
- Best times to post: Tue-Thu, 8-10am your timezone
- After posting, reply to your own post with: "For context — the closest alternatives are framework-locked in-memory testing (only works with servers built on that framework), HTTP-level traffic replay (doesn't understand MCP protocol), or rolling your own mocks. Agent VCR is protocol-native and works with any MCP server. Happy to answer questions about the architecture."
