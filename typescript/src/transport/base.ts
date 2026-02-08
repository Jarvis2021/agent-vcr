/**
 * Abstract transport interface for MCP communication.
 *
 * Transports handle the raw communication protocol and invoke callbacks
 * for messages flowing in both directions.
 */

import { JSONRPCRequest, JSONRPCResponse } from "../core/format.js";

export type MessageCallback = (message: Record<string, unknown>) => void | Promise<void>;

export interface TransportConfig {
  onClientMessage?: MessageCallback;
  onServerMessage?: MessageCallback;
}

/**
 * Abstract base class for MCP transports.
 */
export abstract class BaseTransport {
  protected onClientMessage?: MessageCallback;
  protected onServerMessage?: MessageCallback;
  protected isStarted = false;

  constructor(config: TransportConfig = {}) {
    this.onClientMessage = config.onClientMessage;
    this.onServerMessage = config.onServerMessage;
  }

  /**
   * Start the transport and begin proxying messages.
   */
  abstract start(): Promise<void>;

  /**
   * Stop the transport and cleanup resources.
   */
  abstract stop(): Promise<void>;

  /**
   * Send a message to the client.
   */
  abstract sendToClient(message: JSONRPCRequest | JSONRPCResponse): Promise<void>;

  /**
   * Send a message to the server.
   */
  abstract sendToServer(message: JSONRPCRequest | JSONRPCResponse): Promise<void>;

  /**
   * Check if the transport is currently running.
   */
  isRunning(): boolean {
    return this.isStarted;
  }
}
