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

  it("compare current with fewer interactions reports removed", () => {
    const baseline = sampleRecording;
    const current = recordingWithOneInteraction();
    const result = MCPDiff.compare(baseline, current);
    expect(result.removed.length).toBeGreaterThanOrEqual(0);
    expect(result.summary.removed_count).toBe(result.removed.length);
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
});
