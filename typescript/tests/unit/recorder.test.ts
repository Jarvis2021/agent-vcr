/**
 * Tests for MCPRecorder — construction and basic behavior.
 * Full recording is integration-style (requires running process).
 */
import { describe, it, expect } from "vitest";
import { MCPRecorder } from "../../src/recorder.js";

describe("MCPRecorder", () => {
  it("constructs with stdio transport config", () => {
    const recorder = new MCPRecorder({
      transport: "stdio",
      command: "node",
      args: ["server.js"],
    });
    expect(recorder).toBeDefined();
  });

  it("constructs with sse transport config", () => {
    const recorder = new MCPRecorder({
      transport: "sse",
      command: "node",
      args: ["server.js"],
      host: "127.0.0.1",
      port: 3000,
    });
    expect(recorder).toBeDefined();
  });

  it("constructs with metadata", () => {
    const recorder = new MCPRecorder({
      transport: "stdio",
      command: "node",
      args: ["server.js"],
      metadata: { tags: { env: "test" } },
    });
    expect(recorder).toBeDefined();
  });
});
