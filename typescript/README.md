# Agent VCR - TypeScript/Node.js

**Record, replay, and diff MCP interactions — like VCR for AI agents.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node 18+](https://img.shields.io/badge/node-18+-blue.svg)](https://nodejs.org/)

First-class TypeScript implementation for the MCP ecosystem. **72 tests** cover format, matcher, replayer, recorder, and diff. **npm-ready** as `@agent-vcr/core` (publish when you ship). Same functionality as the Python version with full cross-language compatibility — record with Python, replay with TypeScript (or the other way around). Ideal for teams that build MCP servers and clients in TypeScript/Node, where most of the MCP ecosystem lives.

## Installation

```bash
npm install @agent-vcr/core
```

For testing framework integrations:

```bash
# Jest
npm install --save-dev @agent-vcr/core

# Vitest
npm install --save-dev @agent-vcr/core
```

## Quick Start

### Recording MCP Interactions (CLI)

```bash
# Record stdio transport
npx agent-vcr record \
  --transport stdio \
  --server-command "node my-mcp-server.js" \
  -o my-recording.vcr

# Record SSE transport
npx agent-vcr record \
  --transport sse \
  --server-command "node my-mcp-server.js" \
  --host 127.0.0.1 \
  --port 3000 \
  -o my-recording.vcr
```

### Replaying Recordings (CLI)

```bash
# Replay via stdio
npx agent-vcr replay -i my-recording.vcr --transport stdio

# Replay via SSE
npx agent-vcr replay -i my-recording.vcr --transport sse --port 3000
```

### Diffing Recordings (CLI)

```bash
npx agent-vcr diff \
  --baseline v1-recording.vcr \
  --current v2-recording.vcr \
  --fail-on-breaking
```

## Programmatic Usage

### Recording

```typescript
import { MCPRecorder } from "@agent-vcr/core";

const recorder = new MCPRecorder({
  transport: "stdio",
  command: "node my-mcp-server.js",
  metadata: {
    tags: { env: "test" },
  },
});

await recorder.start();

// Let it record interactions...
// Press Ctrl+C or call stop()

const recording = await recorder.stop();
await recorder.save(recording, "recording.vcr");
```

### Replaying

```typescript
import { MCPReplayer } from "@agent-vcr/core";

// Load from file
const replayer = await MCPReplayer.fromFile("recording.vcr");

// Handle a request
const request = {
  jsonrpc: "2.0",
  id: 1,
  method: "tools/list",
};

const response = replayer.handleRequest(request);
console.log(response);

// Serve as a mock server
await replayer.serveStdio(); // or serveSSE(host, port)
```

### Error Injection

```typescript
const replayer = await MCPReplayer.fromFile("recording.vcr");

// Inject an error for request id=3
replayer.setResponseOverride(3, {
  jsonrpc: "2.0",
  id: 3,
  error: {
    code: -32603,
    message: "Internal server error",
  },
});

// Test your error handling
const response = replayer.handleRequest({
  jsonrpc: "2.0",
  id: 3,
  method: "tools/call",
  params: { name: "calculator" },
});
```

### Diffing

```typescript
import { MCPDiff } from "@agent-vcr/core";

const result = await MCPDiff.compareFiles("v1.vcr", "v2.vcr");

console.log(`Breaking changes: ${result.summary.breaking_count}`);
console.log(`Added methods: ${result.summary.added_count}`);
console.log(`Removed methods: ${result.summary.removed_count}`);

// Check for specific breaking changes
for (const change of result.breaking_changes) {
  console.log(`⚠️ ${change.type}: ${change.method}`);
  console.log(`   ${change.details}`);
}
```

## Testing Framework Integration

### Vitest

```typescript
import { describe, it, expect } from "vitest";
import { useVCRCassette } from "@agent-vcr/core/vitest";

describe("My MCP client", () => {
  it("should list tools correctly", async () => {
    const { replayer, cassette } = await useVCRCassette({
      name: "list-tools",
      dir: "tests/fixtures/cassettes",
    });

    try {
      const response = replayer.handleRequest({
        jsonrpc: "2.0",
        id: 1,
        method: "tools/list",
      });

      expect(response?.result).toBeDefined();
      expect(response?.result?.tools).toHaveLength(3);
    } finally {
      await cassette.eject();
    }
  });
});
```

### Jest

```typescript
import { useVCRCassette } from "@agent-vcr/core/jest";

describe("My MCP client", () => {
  it("should list tools correctly", async () => {
    const { replayer, cassette } = await useVCRCassette({
      name: "list-tools",
      dir: "__fixtures__/cassettes",
    });

    try {
      const response = replayer.handleRequest({
        jsonrpc: "2.0",
        id: 1,
        method: "tools/list",
      });

      expect(response?.result).toBeDefined();
    } finally {
      await cassette.eject();
    }
  });
});
```

## Match Strategies

When replaying, you can choose how requests are matched to recorded interactions:

| Strategy             | Description                          | Best For                 |
| -------------------- | ------------------------------------ | ------------------------ |
| `exact`              | Full JSON equality                   | Strictest regression     |
| `method`             | Method name only                     | Broad acceptance tests   |
| `method_and_params`  | Method + params equality (default)   | Standard testing         |
| `fuzzy`              | Method + params subset matching      | Flexible testing         |
| `sequential`         | Returns in order, ignores content    | Scripted replay          |

```typescript
const replayer = await MCPReplayer.fromFile("recording.vcr", "fuzzy");
```

## Cross-Language Compatibility

Recordings are stored as JSON and are fully compatible between Python and TypeScript implementations:

```bash
# Record with Python
python -m agent_vcr record --server-command "node server.js" -o recording.vcr

# Replay with TypeScript
npx agent-vcr replay -i recording.vcr

# Or vice versa!
```

## CLI Reference

```bash
agent-vcr record --help
agent-vcr replay --help
agent-vcr diff --help
agent-vcr inspect --help
agent-vcr convert --help
```

## API Documentation

Full TypeScript API documentation is available in the source code with JSDoc comments. Key exports:

```typescript
import {
  // Core types
  VCRRecording,
  VCRInteraction,
  JSONRPCRequest,
  JSONRPCResponse,

  // Main classes
  MCPRecorder,
  MCPReplayer,
  MCPDiff,

  // Transport
  StdioTransport,
  SSETransport,

  // Matching
  createMatcher,
  MatchStrategy,

  // Testing integrations
} from "@agent-vcr/core";
```

## Examples

See the `/examples` directory in the repository for complete examples:

- **Basic recording and replay**
- **Error injection for resilience testing**
- **CI/CD integration patterns**
- **Multi-version compatibility testing**

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) in the repository root.

## License

MIT — see [LICENSE](../LICENSE)

## Related Projects

- [Python implementation](../python/README.md)
- [Model Context Protocol](https://modelcontextprotocol.io)
