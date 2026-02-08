/**
 * Bugfix and edge-case tests — mirrors Python test_bugfixes.py.
 */
import { describe, it, expect } from "vitest";
import {
  loadVCRRecording,
  validateVCRRecording,
  createVCRRecording,
} from "../../src/core/format.js";
import { createMatcher } from "../../src/core/matcher.js";
import { sampleInitRequest, sampleInitResponse, sampleRecording } from "../fixtures.js";

describe("loadVCRRecording", () => {
  it("parses valid recording from JSON object", () => {
    const json = JSON.parse(JSON.stringify(sampleRecording));
    const loaded = loadVCRRecording(json);
    expect(loaded.format_version).toBe("1.0.0");
    expect(loaded.session.interactions.length).toBeGreaterThanOrEqual(1);
  });
});

describe("validateVCRRecording", () => {
  it("returns success true and data for valid input", () => {
    const result = validateVCRRecording(JSON.parse(JSON.stringify(sampleRecording)));
    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
  });

  it("returns success false for invalid structure", () => {
    const result = validateVCRRecording({});
    expect(result.success).toBe(false);
    expect(result.errors).toBeDefined();
  });

  it("returns success false for null", () => {
    const result = validateVCRRecording(null);
    expect(result.success).toBe(false);
  });
});

describe("createVCRRecording metadata", () => {
  it("preserves server_command and server_args in metadata", () => {
    const rec = createVCRRecording(
      {
        transport: "stdio",
        server_command: "python demo/servers/calculator_v1.py",
        server_args: ["--debug"],
      },
      sampleInitRequest,
      sampleInitResponse
    );
    expect(rec.metadata.server_command).toBe("python demo/servers/calculator_v1.py");
    expect(rec.metadata.server_args).toEqual(["--debug"]);
  });
});

describe("matcher invalid strategy", () => {
  it("createMatcher throws for unknown strategy", () => {
    expect(() => createMatcher("unknown" as "exact")).toThrow();
  });
});

describe("recording round-trip", () => {
  it("serialize and parse preserves structure", () => {
    const rec = createVCRRecording(
      { transport: "stdio", version: "1.0", recorded_at: "2024-01-15T10:30:00Z" },
      sampleInitRequest,
      sampleInitResponse
    );
    const json = JSON.stringify(rec);
    const parsed = JSON.parse(json);
    const loaded = loadVCRRecording(parsed);
    expect(loaded.metadata.transport).toBe(rec.metadata.transport);
    expect(loaded.session.initialize_request.method).toBe(rec.session.initialize_request.method);
  });
});
