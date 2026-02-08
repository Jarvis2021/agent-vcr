/**
 * SSE (Server-Sent Events) transport for MCP.
 *
 * This transport runs an HTTP server that accepts POST requests from clients
 * and forwards them to the MCP server, then streams responses back via SSE.
 */

import { createServer, IncomingMessage, ServerResponse, Server } from "http";
import { BaseTransport, TransportConfig } from "./base.js";
import { JSONRPCRequest, JSONRPCResponse } from "../core/format.js";
import { StdioTransport } from "./stdio.js";

export interface SSETransportConfig extends TransportConfig {
  command: string;
  args?: string[];
  host?: string;
  port?: number;
  cwd?: string;
  env?: Record<string, string>;
}

/**
 * SSE transport implementation.
 */
export class SSETransport extends BaseTransport {
  private httpServer: Server | null = null;
  private stdioTransport: StdioTransport | null = null;
  private config: SSETransportConfig;
  private sseClients: Set<ServerResponse> = new Set();

  constructor(config: SSETransportConfig) {
    super(config);
    this.config = {
      host: "127.0.0.1",
      port: 3000,
      ...config,
    };
  }

  async start(): Promise<void> {
    if (this.isStarted) {
      throw new Error("Transport already started");
    }

    // Start stdio transport to communicate with the MCP server
    this.stdioTransport = new StdioTransport({
      command: this.config.command,
      args: this.config.args,
      cwd: this.config.cwd,
      env: this.config.env,
      onServerMessage: async (message) => {
        // Forward server messages via SSE to all connected clients
        this.broadcastSSE(message);

        // Also invoke the original callback if provided
        if (this.onServerMessage) {
          await this.onServerMessage(message);
        }
      },
      onClientMessage: this.onClientMessage,
    });

    await this.stdioTransport.start();

    // Create HTTP server
    this.httpServer = createServer((req, res) => {
      this.handleRequest(req, res);
    });

    // Start HTTP server
    await new Promise<void>((resolve, reject) => {
      this.httpServer!.listen(
        this.config.port,
        this.config.host,
        () => {
          console.log(`SSE transport listening on ${this.config.host}:${this.config.port}`);
          resolve();
        }
      );
      this.httpServer!.once("error", reject);
    });

    this.isStarted = true;
  }

  async stop(): Promise<void> {
    if (!this.isStarted) {
      return;
    }

    // Close all SSE connections
    for (const client of this.sseClients) {
      client.end();
    }
    this.sseClients.clear();

    // Stop HTTP server
    if (this.httpServer) {
      await new Promise<void>((resolve) => {
        this.httpServer!.close(() => resolve());
      });
      this.httpServer = null;
    }

    // Stop stdio transport
    if (this.stdioTransport) {
      await this.stdioTransport.stop();
      this.stdioTransport = null;
    }

    this.isStarted = false;
  }

  async sendToClient(message: JSONRPCRequest | JSONRPCResponse): Promise<void> {
    this.broadcastSSE(message);
  }

  async sendToServer(message: JSONRPCRequest | JSONRPCResponse): Promise<void> {
    if (!this.stdioTransport) {
      throw new Error("Transport not started");
    }
    await this.stdioTransport.sendToServer(message);
  }

  private async handleRequest(req: IncomingMessage, res: ServerResponse): Promise<void> {
    // Enable CORS
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");

    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    // SSE endpoint
    if (req.method === "GET" && req.url === "/sse") {
      this.handleSSEConnection(res);
      return;
    }

    // JSON-RPC message endpoint
    if (req.method === "POST" && req.url === "/message") {
      await this.handleMessage(req, res);
      return;
    }

    // Health check
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "ok" }));
      return;
    }

    // Not found
    res.writeHead(404);
    res.end("Not found");
  }

  private handleSSEConnection(res: ServerResponse): void {
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    });

    this.sseClients.add(res);

    res.on("close", () => {
      this.sseClients.delete(res);
    });

    // Send initial connection event
    this.sendSSE(res, { type: "connected" });
  }

  private async handleMessage(req: IncomingMessage, res: ServerResponse): Promise<void> {
    let body = "";

    req.on("data", (chunk) => {
      body += chunk.toString();
    });

    req.on("end", async () => {
      try {
        const message = JSON.parse(body);

        // Invoke client message callback
        if (this.onClientMessage) {
          await this.onClientMessage(message);
        }

        // Forward to server via stdio transport
        if (this.stdioTransport) {
          await this.stdioTransport.sendToServer(message);
        }

        res.writeHead(202, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ accepted: true }));
      } catch (error) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Invalid JSON" }));
      }
    });
  }

  private broadcastSSE(data: unknown): void {
    for (const client of this.sseClients) {
      this.sendSSE(client, data);
    }
  }

  private sendSSE(client: ServerResponse, data: unknown): void {
    const json = JSON.stringify(data);
    client.write(`data: ${json}\n\n`);
  }
}
