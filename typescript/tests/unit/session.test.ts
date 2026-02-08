/**
 * Tests for SessionManager lifecycle and state.
 * Ported from Python test_session.py.
 */
import { describe, it, expect } from "vitest";
import { SessionManager } from "../../src/core/session.js";
import {
  sampleInitRequest,
  sampleInitResponse,
  createInteraction,
} from "../fixtures.js";

describe("SessionManager init", () => {
  it("starts in idle state", () => {
    const manager = new SessionManager();
    expect(manager.isRecording()).toBe(false);
    expect(manager.getCurrentRecording()).toBeNull();
  });
});

describe("SessionManager lifecycle", () => {
  it("startRecording transitions to recording", () => {
    const manager = new SessionManager();
    manager.startRecording(
      { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
      sampleInitRequest,
      sampleInitResponse
    );
    expect(manager.isRecording()).toBe(true);
    expect(manager.getCurrentRecording()).not.toBeNull();
  });

  it("startRecording creates recording with init request/response", () => {
    const manager = new SessionManager();
    manager.startRecording(
      { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
      sampleInitRequest,
      sampleInitResponse
    );
    const rec = manager.getCurrentRecording()!;
    expect(rec.session.initialize_request.method).toBe("initialize");
    expect(rec.session.interactions).toHaveLength(0);
  });

  it("startRecording throws if already recording", () => {
    const manager = new SessionManager();
    manager.startRecording(
      { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
      sampleInitRequest,
      sampleInitResponse
    );
    expect(() =>
      manager.startRecording(
        { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
        sampleInitRequest,
        sampleInitResponse
      )
    ).toThrow(/Recording already in progress/);
  });

  it("recordInteraction adds interaction", () => {
    const manager = new SessionManager();
    manager.startRecording(
      { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
      sampleInitRequest,
      sampleInitResponse
    );
    const req = { jsonrpc: "2.0" as const, id: 2, method: "tools/list", params: {} };
    const resp = { jsonrpc: "2.0" as const, id: 2, result: { tools: [] } };
    manager.recordInteraction(req, resp);
    const rec = manager.getCurrentRecording()!;
    expect(rec.session.interactions).toHaveLength(1);
    expect(rec.session.interactions[0].request.method).toBe("tools/list");
  });

  it("recordInteraction throws when not recording", () => {
    const manager = new SessionManager();
    const req = { jsonrpc: "2.0" as const, id: 1, method: "test" };
    const resp = { jsonrpc: "2.0" as const, id: 1, result: {} };
    expect(() => manager.recordInteraction(req, resp)).toThrow(/No recording in progress/);
  });

  it("stopRecording returns recording and resets state", () => {
    const manager = new SessionManager();
    manager.startRecording(
      { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
      sampleInitRequest,
      sampleInitResponse
    );
    const recording = manager.stopRecording();
    expect(recording).not.toBeNull();
    expect(recording.session.initialize_request.method).toBe("initialize");
    expect(manager.isRecording()).toBe(false);
    expect(manager.getCurrentRecording()).toBeNull();
  });

  it("stopRecording throws when not recording", () => {
    const manager = new SessionManager();
    expect(() => manager.stopRecording()).toThrow(/No recording in progress/);
  });

  it("reset clears state", () => {
    const manager = new SessionManager();
    manager.startRecording(
      { version: "1.0", recorded_at: "2024-01-15T10:30:00Z", transport: "stdio" },
      sampleInitRequest,
      sampleInitResponse
    );
    manager.reset();
    expect(manager.isRecording()).toBe(false);
    expect(manager.getCurrentRecording()).toBeNull();
  });
});
