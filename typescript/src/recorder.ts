/**
 * MCP Recorder — transparently records MCP interactions.
 *
 * The recorder acts as a proxy between client and server, capturing all
 * JSON-RPC messages and saving them to a .vcr file.
 */

import { promises as fs } from "fs";
import { SessionManager } from "./core/session.js";
import {
  JSONRPCRequest,
  JSONRPCResponse,
  VCRRecording,
  VCRMetadata,
} from "./core/format.js";
import { StdioTransport, StdioTransportConfig } from "./transport/stdio.js";
import { SSETransport, SSETransportConfig } from "./transport/sse.js";
import { BaseTransport } from "./transport/base.js";

export interface RecorderConfig {
  transport: "stdio" | "sse";
  command: string;
  args?: string[];
  host?: string;
  port?: number;
  cwd?: string;
  env?: Record<string, string>;
  metadata?: Partial<VCRMetadata>;
}

/**
 * Records MCP interactions to a VCR cassette.
 */
export class MCPRecorder {
  private transport: BaseTransport | null = null;
  private sessionManager: SessionManager;
  private config: RecorderConfig;
  private pendingRequests = new Map<string | number, {
    request: JSONRPCRequest;
    timestamp: Date;
  }>();
  private initRequest: JSONRPCRequest | null = null;
  private initResponse: JSONRPCResponse | null = null;

  constructor(config: RecorderConfig) {
    this.config = config;
    this.sessionManager = new SessionManager();
  }

  /**
   * Start recording.
   */
  async start(): Promise<void> {
    if (this.transport) {
      throw new Error("Recorder already started");
    }

    // Create transport with callbacks
    if (this.config.transport === "stdio") {
      this.transport = new StdioTransport({
        command: this.config.command,
        args: this.config.args,
        cwd: this.config.cwd,
        env: this.config.env,
        onClientMessage: async (msg) => this.handleClientMessage(msg),
        onServerMessage: async (msg) => this.handleServerMessage(msg),
      } as StdioTransportConfig);
    } else if (this.config.transport === "sse") {
      this.transport = new SSETransport({
        command: this.config.command,
        args: this.config.args,
        host: this.config.host,
        port: this.config.port,
        cwd: this.config.cwd,
        env: this.config.env,
        onClientMessage: async (msg) => this.handleClientMessage(msg),
        onServerMessage: async (msg) => this.handleServerMessage(msg),
      } as SSETransportConfig);
    } else {
      throw new Error(`Unknown transport: ${this.config.transport}`);
    }

    await this.transport.start();
  }

  /**
   * Stop recording and return the completed recording.
   */
  async stop(): Promise<VCRRecording> {
    if (!this.transport) {
      throw new Error("Recorder not started");
    }

    await this.transport.stop();
    this.transport = null;

    if (!this.sessionManager.isRecording()) {
      throw new Error("No recording session active");
    }

    return this.sessionManager.stopRecording();
  }

  /**
   * Save the recording to a file.
   */
  async save(recording: VCRRecording, path: string): Promise<void> {
    const json = JSON.stringify(recording, null, 2);
    await fs.writeFile(path, json, "utf-8");
  }

  private async handleClientMessage(msg: Record<string, unknown>): Promise<void> {
    if (!this.isJSONRPCRequest(msg)) {
      return;
    }

    const request = msg as JSONRPCRequest;

    // Handle initialize request specially
    if (request.method === "initialize") {
      this.initRequest = request;
      this.pendingRequests.set(request.id, {
        request,
        timestamp: new Date(),
      });
      return;
    }

    // Store pending request
    this.pendingRequests.set(request.id, {
      request,
      timestamp: new Date(),
    });

    // If we have initialize response and haven't started recording yet
    if (this.initResponse && !this.sessionManager.isRecording()) {
      this.startRecordingSession();
    }

    // Record interaction if session is active
    if (this.sessionManager.isRecording()) {
      // Note: response will be null until we receive it
      // This will be updated when response arrives
    }
  }

  private async handleServerMessage(msg: Record<string, unknown>): Promise<void> {
    if (!this.isJSONRPCResponse(msg)) {
      return;
    }

    const response = msg as JSONRPCResponse;
    const pending = this.pendingRequests.get(response.id);

    if (!pending) {
      console.warn(`Received response for unknown request id: ${response.id}`);
      return;
    }

    // Handle initialize response specially
    if (pending.request.method === "initialize") {
      this.initResponse = response;
      this.pendingRequests.delete(response.id);

      // Start recording session now that we have both init request and response
      if (this.initRequest) {
        this.startRecordingSession();
      }
      return;
    }

    // Record the interaction
    if (this.sessionManager.isRecording()) {
      this.sessionManager.recordInteraction(pending.request, response);
    }

    this.pendingRequests.delete(response.id);
  }

  private startRecordingSession(): void {
    if (!this.initRequest || !this.initResponse) {
      throw new Error("Initialize handshake not complete");
    }

    const metadata: Partial<VCRMetadata> = {
      transport: this.config.transport,
      server_command: this.config.command,
      server_args: this.config.args || [],
      client_info: (this.initRequest.params as any)?.clientInfo || {},
      server_info: this.initResponse.result?.serverInfo || {},
      ...this.config.metadata,
    };

    this.sessionManager.startRecording(
      metadata,
      this.initRequest,
      this.initResponse
    );
  }

  private isJSONRPCRequest(msg: Record<string, unknown>): boolean {
    return (
      msg.jsonrpc === "2.0" &&
      typeof msg.id !== "undefined" &&
      typeof msg.method === "string"
    );
  }

  private isJSONRPCResponse(msg: Record<string, unknown>): boolean {
    return (
      msg.jsonrpc === "2.0" &&
      typeof msg.id !== "undefined" &&
      (msg.result !== undefined || msg.error !== undefined)
    );
  }
}
