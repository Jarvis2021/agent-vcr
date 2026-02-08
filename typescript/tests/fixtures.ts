/**
 * Shared test fixtures — mirrors Python conftest.py.
 */
import type {
  JSONRPCRequest,
  JSONRPCResponse,
  VCRInteraction,
  VCRRecording,
} from "../src/core/format.js";
import {
  JSONRPCRequestSchema,
  JSONRPCResponseSchema,
  VCRRecordingSchema,
  createVCRRecording,
} from "../src/core/format.js";

const ISO_DATE = "2024-01-15T10:30:00.000Z";

export const sampleInitRequest: JSONRPCRequest = JSONRPCRequestSchema.parse({
  jsonrpc: "2.0",
  id: 1,
  method: "initialize",
  params: {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "test-client", version: "1.0.0" },
  },
});

export const sampleInitResponse: JSONRPCResponse = JSONRPCResponseSchema.parse({
  jsonrpc: "2.0",
  id: 1,
  result: {
    protocolVersion: "2024-11-05",
    capabilities: { tools: {}, resources: {} },
    serverInfo: { name: "test-server", version: "1.0.0" },
  },
});

export function createInteraction(
  method: string,
  params: Record<string, unknown> | undefined = undefined,
  sequence = 0
): VCRInteraction {
  return {
    sequence,
    timestamp: new Date().toISOString(),
    direction: "client_to_server",
    request: JSONRPCRequestSchema.parse({
      jsonrpc: "2.0",
      id: 1,
      method,
      params: params ?? {},
    }),
    response: JSONRPCResponseSchema.parse({
      jsonrpc: "2.0",
      id: 1,
      result: {},
    }),
    notifications: [],
    latency_ms: 10,
  };
}

export const sampleRecording: VCRRecording = (() => {
  const rec = createVCRRecording(
    {
      version: "1.0.0",
      recorded_at: ISO_DATE,
      transport: "stdio",
      client_info: { name: "test-client", version: "1.0.0" },
      server_info: { name: "test-server", version: "1.0.0" },
      server_command: "python -m test_server",
      server_args: ["--debug"],
      tags: { environment: "test" },
    },
    sampleInitRequest,
    sampleInitResponse
  );
  rec.session.interactions.push(
    createInteraction("tools/list", {}, 0),
    createInteraction("tools/call", { name: "echo", arguments: { text: "hi" } }, 1),
    createInteraction("tools/call", { name: "add", arguments: { a: 1, b: 2 } }, 2)
  );
  return rec;
})();

export const emptyRecording: VCRRecording = createVCRRecording(
  { version: "1.0.0", recorded_at: ISO_DATE, transport: "stdio" },
  sampleInitRequest,
  sampleInitResponse
);

export function minimalRecording(): VCRRecording {
  return VCRRecordingSchema.parse({
    format_version: "1.0.0",
    metadata: {
      version: "1.0",
      recorded_at: ISO_DATE,
      transport: "stdio",
    },
    session: {
      initialize_request: {
        jsonrpc: "2.0",
        id: 0,
        method: "initialize",
        params: {},
      },
      initialize_response: {
        jsonrpc: "2.0",
        id: 0,
        result: { capabilities: {} },
      },
      capabilities: {},
      interactions: [],
    },
  });
}
