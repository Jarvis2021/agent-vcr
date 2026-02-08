/**
 * VCR file format — Zod schemas and types for .vcr recording files.
 *
 * The .vcr format captures complete MCP sessions including:
 * - Session metadata (timestamp, transport, client/server info)
 * - Initialize handshake
 * - All request/response/notification interactions in sequence
 * - Timing information for each interaction
 */

import { z } from "zod";

// JSON-RPC 2.0 Message Types
export const JSONRPCMessageSchema = z.object({
  jsonrpc: z.literal("2.0"),
});

export const JSONRPCErrorSchema = z.object({
  code: z.number(),
  message: z.string(),
  data: z.record(z.any()).optional(),
});

export const JSONRPCRequestSchema = JSONRPCMessageSchema.extend({
  id: z.union([z.string(), z.number()]),
  method: z.string(),
  params: z.union([z.record(z.any()), z.array(z.any())]).optional(),
});

export const JSONRPCResponseSchema = JSONRPCMessageSchema.extend({
  id: z.union([z.string(), z.number()]),
  result: z.record(z.any()).optional(),
  error: JSONRPCErrorSchema.optional(),
}).refine(
  (data) => (data.result !== undefined) !== (data.error !== undefined),
  { message: "Response must have either result or error, not both" }
);

export const JSONRPCNotificationSchema = JSONRPCMessageSchema.extend({
  method: z.string(),
  params: z.union([z.record(z.any()), z.array(z.any())]).optional(),
});

// VCR Recording Types
export const VCRInteractionSchema = z.object({
  sequence: z.number().int().nonnegative(),
  timestamp: z.string().datetime(),
  direction: z.enum(["client_to_server", "server_to_client"]),
  request: JSONRPCRequestSchema,
  response: JSONRPCResponseSchema.optional(),
  notifications: z.array(JSONRPCNotificationSchema).default([]),
  latency_ms: z.number().nonnegative(),
});

export const VCRMetadataSchema = z.object({
  version: z.string(),
  recorded_at: z.string().datetime(),
  transport: z.enum(["stdio", "sse"]),
  client_info: z.record(z.any()).default({}),
  server_info: z.record(z.any()).default({}),
  server_command: z.string().optional(),
  server_args: z.array(z.string()).default([]),
  tags: z.record(z.any()).default({}),
});

export const VCRSessionSchema = z.object({
  initialize_request: JSONRPCRequestSchema,
  initialize_response: JSONRPCResponseSchema,
  capabilities: z.record(z.any()).default({}),
  interactions: z.array(VCRInteractionSchema),
});

export const VCRRecordingSchema = z.object({
  format_version: z.string(),
  metadata: VCRMetadataSchema,
  session: VCRSessionSchema,
});

// Export TypeScript types derived from Zod schemas
export type JSONRPCMessage = z.infer<typeof JSONRPCMessageSchema>;
export type JSONRPCError = z.infer<typeof JSONRPCErrorSchema>;
export type JSONRPCRequest = z.infer<typeof JSONRPCRequestSchema>;
export type JSONRPCResponse = z.infer<typeof JSONRPCResponseSchema>;
export type JSONRPCNotification = z.infer<typeof JSONRPCNotificationSchema>;
export type VCRInteraction = z.infer<typeof VCRInteractionSchema>;
export type VCRMetadata = z.infer<typeof VCRMetadataSchema>;
export type VCRSession = z.infer<typeof VCRSessionSchema>;
export type VCRRecording = z.infer<typeof VCRRecordingSchema>;

/**
 * Load and validate a VCR recording from JSON.
 */
export function loadVCRRecording(json: unknown): VCRRecording {
  return VCRRecordingSchema.parse(json);
}

/**
 * Validate a VCR recording and return validation errors if invalid.
 */
export function validateVCRRecording(json: unknown): {
  success: boolean;
  data?: VCRRecording;
  errors?: z.ZodError;
} {
  const result = VCRRecordingSchema.safeParse(json);
  if (result.success) {
    return { success: true, data: result.data };
  } else {
    return { success: false, errors: result.error };
  }
}

/**
 * Create a new empty VCR recording with default metadata.
 */
export function createVCRRecording(
  metadata: Partial<VCRMetadata>,
  initRequest: JSONRPCRequest,
  initResponse: JSONRPCResponse
): VCRRecording {
  return {
    format_version: "1.0.0",
    metadata: {
      version: "1.0.0",
      recorded_at: new Date().toISOString(),
      transport: "stdio",
      client_info: {},
      server_info: {},
      server_args: [],
      tags: {},
      ...metadata,
    },
    session: {
      initialize_request: initRequest,
      initialize_response: initResponse,
      capabilities: initResponse.result?.capabilities || {},
      interactions: [],
    },
  };
}
