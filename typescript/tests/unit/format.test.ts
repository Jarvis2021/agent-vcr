/**
 * Unit tests for VCR format (Zod schemas and helpers).
 * Ported from Python test_format.py.
 */
import { describe, it, expect } from "vitest";
import {
  JSONRPCMessageSchema,
  JSONRPCErrorSchema,
  JSONRPCRequestSchema,
  JSONRPCResponseSchema,
  JSONRPCNotificationSchema,
  VCRInteractionSchema,
  VCRMetadataSchema,
  VCRSessionSchema,
  VCRRecordingSchema,
  loadVCRRecording,
  validateVCRRecording,
  createVCRRecording,
} from "../../src/core/format.js";
import { sampleInitRequest, sampleInitResponse, minimalRecording } from "../fixtures.js";

describe("JSONRPCMessage", () => {
  it("validates jsonrpc 2.0", () => {
    const msg = JSONRPCMessageSchema.parse({ jsonrpc: "2.0" });
    expect(msg.jsonrpc).toBe("2.0");
  });
});

describe("JSONRPCError", () => {
  it("creates error with code and message only", () => {
    const error = JSONRPCErrorSchema.parse({ code: -32600, message: "Invalid Request" });
    expect(error.code).toBe(-32600);
    expect(error.message).toBe("Invalid Request");
    expect(error.data).toBeUndefined();
  });

  it("creates error with data", () => {
    const error = JSONRPCErrorSchema.parse({
      code: -32603,
      message: "Internal error",
      data: { details: "something went wrong" },
    });
    expect(error.data).toEqual({ details: "something went wrong" });
  });
});

describe("JSONRPCRequest", () => {
  it("parses minimal request", () => {
    const req = JSONRPCRequestSchema.parse({ jsonrpc: "2.0", id: 1, method: "test" });
    expect(req.jsonrpc).toBe("2.0");
    expect(req.id).toBe(1);
    expect(req.method).toBe("test");
    expect(req.params).toBeUndefined();
  });

  it("parses request with dict params", () => {
    const req = JSONRPCRequestSchema.parse({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: { name: "echo", arguments: { text: "hello" } },
    });
    expect((req.params as Record<string, unknown>).name).toBe("echo");
  });

  it("parses request with string id", () => {
    const req = JSONRPCRequestSchema.parse({
      jsonrpc: "2.0",
      id: "request-abc",
      method: "test",
    });
    expect(req.id).toBe("request-abc");
  });
});

describe("JSONRPCResponse", () => {
  it("parses response with result", () => {
    const resp = JSONRPCResponseSchema.parse({
      jsonrpc: "2.0",
      id: 1,
      result: { status: "ok" },
    });
    expect(resp.result).toEqual({ status: "ok" });
    expect(resp.error).toBeUndefined();
  });

  it("parses response with error", () => {
    const resp = JSONRPCResponseSchema.parse({
      jsonrpc: "2.0",
      id: 2,
      error: { code: -32603, message: "Internal error" },
    });
    expect(resp.error?.code).toBe(-32603);
    expect(resp.result).toBeUndefined();
  });
});

describe("JSONRPCNotification", () => {
  it("parses notification with params", () => {
    const notif = JSONRPCNotificationSchema.parse({
      jsonrpc: "2.0",
      method: "notification/test",
      params: { key: "value" },
    });
    expect(notif.method).toBe("notification/test");
    expect(notif.params).toEqual({ key: "value" });
  });
});

describe("VCRInteraction", () => {
  it("parses basic interaction", () => {
    const interaction = VCRInteractionSchema.parse({
      sequence: 0,
      timestamp: "2024-01-15T10:30:01.000Z",
      direction: "client_to_server",
      request: { jsonrpc: "2.0", id: 1, method: "tools/list" },
      response: { jsonrpc: "2.0", id: 1, result: { tools: [] } },
      latency_ms: 50,
    });
    expect(interaction.sequence).toBe(0);
    expect(interaction.direction).toBe("client_to_server");
    expect(interaction.latency_ms).toBe(50);
  });

  it("allows optional response", () => {
    const interaction = VCRInteractionSchema.parse({
      sequence: 0,
      timestamp: "2024-01-15T10:30:01.000Z",
      direction: "client_to_server",
      request: { jsonrpc: "2.0", id: 1, method: "notification_send" },
      latency_ms: 0,
    });
    expect(interaction.response).toBeUndefined();
  });
});

describe("VCRMetadata", () => {
  it("parses with required fields only", () => {
    const meta = VCRMetadataSchema.parse({
      version: "1.0.0",
      recorded_at: "2024-01-15T10:30:00.000Z",
      transport: "stdio",
    });
    expect(meta.transport).toBe("stdio");
    expect(meta.client_info).toEqual({});
  });

  it("parses transport stdio and sse", () => {
    VCRMetadataSchema.parse({
      version: "1.0",
      recorded_at: "2024-01-15T10:30:00.000Z",
      transport: "stdio",
    });
    VCRMetadataSchema.parse({
      version: "1.0",
      recorded_at: "2024-01-15T10:30:00.000Z",
      transport: "sse",
    });
  });

  it("rejects invalid transport", () => {
    expect(() =>
      VCRMetadataSchema.parse({
        version: "1.0",
        recorded_at: "2024-01-15T10:30:00.000Z",
        transport: "invalid",
      })
    ).toThrow();
  });
});

describe("VCRSession", () => {
  it("parses session with init and empty interactions", () => {
    const session = VCRSessionSchema.parse({
      initialize_request: sampleInitRequest,
      initialize_response: sampleInitResponse,
      capabilities: {},
      interactions: [],
    });
    expect(session.interactions).toHaveLength(0);
  });
});

describe("VCRRecording", () => {
  it("VCRRecordingSchema validates minimal recording", () => {
    const rec = minimalRecording();
    expect(rec.format_version).toBe("1.0.0");
    expect(rec.metadata.transport).toBe("stdio");
    expect(rec.session.interactions).toHaveLength(0);
  });

  it("createVCRRecording returns valid shape", () => {
    const recording = createVCRRecording(
      { transport: "stdio", server_command: "node server.js" },
      sampleInitRequest,
      sampleInitResponse
    );
    expect(recording.format_version).toBeDefined();
    expect(recording.metadata.transport).toBe("stdio");
    expect(recording.session.initialize_request.method).toBe("initialize");
  });

  it("loadVCRRecording parses valid JSON", () => {
    const rec = minimalRecording();
    const loaded = loadVCRRecording(JSON.parse(JSON.stringify(rec)));
    expect(loaded.format_version).toBe(rec.format_version);
    expect(loaded.session.initialize_request.method).toBe("initialize");
  });

  it("validateVCRRecording returns success for valid data", () => {
    const rec = minimalRecording();
    const result = validateVCRRecording(JSON.parse(JSON.stringify(rec)));
    expect(result.success).toBe(true);
    expect(result.data?.format_version).toBe("1.0.0");
  });

  it("validateVCRRecording returns errors for invalid data", () => {
    const result = validateVCRRecording({ invalid: "object" });
    expect(result.success).toBe(false);
    expect(result.errors).toBeDefined();
  });

  it("loadVCRRecording throws for invalid format", () => {
    expect(() => loadVCRRecording({ key: "value" })).toThrow();
  });
});
