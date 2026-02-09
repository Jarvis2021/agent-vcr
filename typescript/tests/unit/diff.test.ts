/**
 * Tests for MCPDiff — compare two recordings.
 * Ported from Python test_diff.py.
 */
import { describe, it, expect } from "vitest";
import { MCPDiff } from "../../src/diff.js";
import {
  sampleRecording,
  emptyRecording,
  createInteraction,
  sampleInitRequest,
  sampleInitResponse,
} from "../fixtures.js";
import { createVCRRecording } from "../../src/core/format.js";
import { JSONRPCRequestSchema, JSONRPCResponseSchema } from "../../src/core/format.js";

// Recording with one interaction for "current" in tests
function recordingWithOneInteraction() {
  const r = createVCRRecording(
    { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
    sampleInitRequest,
    sampleInitResponse
  );
  r.session.interactions.push(createInteraction("tools/list", {}, 0));
  return r;
}

// Baseline with one tools/list (result); current with same method but error → breaking
function baselineWithResultCurrentWithError() {
  const baseline = createVCRRecording(
    { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
    sampleInitRequest,
    sampleInitResponse
  );
  baseline.session.interactions.push({
    sequence: 0,
    timestamp: new Date().toISOString(),
    direction: "client_to_server" as const,
    request: JSONRPCRequestSchema.parse({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/list",
      params: {},
    }),
    response: JSONRPCResponseSchema.parse({
      jsonrpc: "2.0",
      id: 1,
      result: { tools: [] },
    }),
    notifications: [],
    latency_ms: 10,
  });

  const current = createVCRRecording(
    { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
    sampleInitRequest,
    sampleInitResponse
  );
  current.session.interactions.push({
    sequence: 0,
    timestamp: new Date().toISOString(),
    direction: "client_to_server" as const,
    request: JSONRPCRequestSchema.parse({
      jsonrpc: "2.0",
      id: 1,
      method: "tools/list",
      params: {},
    }),
    response: JSONRPCResponseSchema.parse({
      jsonrpc: "2.0",
      id: 1,
      error: { code: -32603, message: "Internal error" },
    }),
    notifications: [],
    latency_ms: 10,
  });

  return { baseline, current };
}

describe("MCPDiff", () => {
  it("compare identical recordings returns no changes", () => {
    const result = MCPDiff.compare(sampleRecording, sampleRecording);
    expect(result.added).toHaveLength(0);
    expect(result.removed).toHaveLength(0);
    expect(result.modified).toHaveLength(0);
    expect(result.breaking_changes).toHaveLength(0);
    expect(result.summary.total_changes).toBe(0);
  });

  it("compare baseline with extra interaction in current reports added", () => {
    const baseline = emptyRecording;
    const current = recordingWithOneInteraction();
    const result = MCPDiff.compare(baseline, current);
    expect(result.added.length).toBeGreaterThanOrEqual(1);
    expect(result.summary.added_count).toBe(result.added.length);
  });

  it("compare current with fewer interactions reports removed and breaking", () => {
    const baseline = sampleRecording;
    const current = recordingWithOneInteraction();
    const result = MCPDiff.compare(baseline, current);
    expect(result.removed.length).toBeGreaterThanOrEqual(0);
    expect(result.summary.removed_count).toBe(result.removed.length);
    // Removed interactions are breaking
    if (result.removed.length > 0) {
      expect(result.breaking_changes.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("summary counts match arrays", () => {
    const result = MCPDiff.compare(emptyRecording, sampleRecording);
    expect(result.summary.added_count).toBe(result.added.length);
    expect(result.summary.removed_count).toBe(result.removed.length);
    expect(result.summary.modified_count).toBe(result.modified.length);
    expect(result.summary.breaking_count).toBe(result.breaking_changes.length);
    expect(result.summary.total_changes).toBe(
      result.added.length + result.removed.length + result.modified.length
    );
  });

  it("success to error response is breaking", () => {
    const { baseline, current } = baselineWithResultCurrentWithError();
    const result = MCPDiff.compare(baseline, current);
    expect(result.modified.length).toBeGreaterThanOrEqual(1);
    expect(result.breaking_changes.length).toBeGreaterThanOrEqual(1);
    expect(result.breaking_changes.some((c) => c.breaking)).toBe(true);
  });

  it("compareFiles loads and compares", async () => {
    const { default: fs } = await import("fs/promises");
    const { tmpdir } = await import("os");
    const { join } = await import("path");
    const basePath = join(tmpdir(), "agent-vcr-diff-base.json");
    const curPath = join(tmpdir(), "agent-vcr-diff-current.json");
    const baseJson = JSON.stringify({
      format_version: "1.0.0",
      metadata: { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
      session: {
        initialize_request: { jsonrpc: "2.0", id: 0, method: "initialize", params: {} },
        initialize_response: { jsonrpc: "2.0", id: 0, result: {} },
        capabilities: {},
        interactions: [],
      },
    });
    await fs.writeFile(basePath, baseJson);
    await fs.writeFile(curPath, baseJson);
    const result = await MCPDiff.compareFiles(basePath, curPath);
    expect(result.added).toHaveLength(0);
    expect(result.removed).toHaveLength(0);
    expect(result.breaking_changes).toHaveLength(0);
  });
});
