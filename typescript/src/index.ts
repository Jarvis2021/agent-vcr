/**
 * Agent VCR - TypeScript SDK
 *
 * Record, replay, and diff MCP (Model Context Protocol) interactions.
 */

// Core types and schemas
export {
  JSONRPCMessage,
  JSONRPCError,
  JSONRPCRequest,
  JSONRPCResponse,
  JSONRPCNotification,
  VCRInteraction,
  VCRMetadata,
  VCRSession,
  VCRRecording,
  loadVCRRecording,
  validateVCRRecording,
  createVCRRecording,
  JSONRPCMessageSchema,
  JSONRPCErrorSchema,
  JSONRPCRequestSchema,
  JSONRPCResponseSchema,
  JSONRPCNotificationSchema,
  VCRInteractionSchema,
  VCRMetadataSchema,
  VCRSessionSchema,
  VCRRecordingSchema,
} from "./core/format.js";

// Request matching
export {
  MatchStrategy,
  RequestMatcher,
  ExactMatcher,
  MethodMatcher,
  MethodAndParamsMatcher,
  FuzzyMatcher,
  SequentialMatcher,
  createMatcher,
} from "./core/matcher.js";

// Session management
export { SessionManager } from "./core/session.js";

// Transport layer
export { BaseTransport, MessageCallback, TransportConfig } from "./transport/base.js";
export { StdioTransport, StdioTransportConfig } from "./transport/stdio.js";
export { SSETransport, SSETransportConfig } from "./transport/sse.js";

// Recorder
export { MCPRecorder, RecorderConfig } from "./recorder.js";

// Replayer
export { MCPReplayer, ReplayerConfig } from "./replayer.js";

// Diff
export { MCPDiff, DiffChange, DiffResult } from "./diff.js";
