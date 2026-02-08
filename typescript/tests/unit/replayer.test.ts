/**
 * Tests for MCPReplayer — replay recorded interactions.
 * Ported from Python test_replayer.py.
 */
import { describe, it, expect } from "vitest";
import { MCPReplayer } from "../../src/replayer.js";
import { sampleRecording, createInteraction } from "../fixtures.js";

describe("MCPReplayer", () => {
  it("handleRequest returns initialize response for initialize method", () => {
    const replayer = new MCPReplayer({ recording: sampleRecording });
    const request = {
      jsonrpc: "2.0" as const,
      id: 99,
      method: "initialize",
      params: {},
    };
    const response = replayer.handleRequest(request);
    expect(response).not.toBeNull();
    expect(response!.id).toBe(99);
    expect(response!.result).toBeDefined();
  });

  it("handleRequest returns matched interaction response", () => {
    const replayer = new MCPReplayer({ recording: sampleRecording });
    const request = {
      jsonrpc: "2.0" as const,
      id: 1,
      method: "tools/list",
      params: {},
    };
    const response = replayer.handleRequest(request);
    expect(response).not.toBeNull();
    expect(response!.result).toEqual({});
  });

  it("handleRequest returns JSON-RPC error when no match (non-strict)", () => {
    const replayer = new MCPReplayer({ recording: sampleRecording });
    const request = {
      jsonrpc: "2.0" as const,
      id: 999,
      method: "unknown/method",
      params: {},
    };
    const response = replayer.handleRequest(request);
    expect(response).not.toBeNull();
    expect(response!.jsonrpc).toBe("2.0");
    expect(response!.id).toBe(999);
    expect(response!.error).toEqual({
      code: -32601,
      message: "No matching recorded interaction found for method 'unknown/method'",
    });
  });

  it("handleRequest uses response override when set", () => {
    const replayer = new MCPReplayer({ recording: sampleRecording });
    replayer.setResponseOverride(1, {
      jsonrpc: "2.0",
      id: 1,
      error: { code: -32603, message: "Injected error" },
    });
    const request = {
      jsonrpc: "2.0" as const,
      id: 1,
      method: "tools/list",
      params: {},
    };
    const response = replayer.handleRequest(request);
    expect(response).not.toBeNull();
    expect(response!.error?.code).toBe(-32603);
    expect(response!.id).toBe(1);
  });

  it("accepts matchStrategy option", () => {
    const replayer = new MCPReplayer({
      recording: sampleRecording,
      matchStrategy: "method",
    });
    const response = replayer.handleRequest({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/list",
      params: {},
    });
    expect(response).not.toBeNull();
  });
});
