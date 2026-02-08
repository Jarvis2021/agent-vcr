/**
 * MCP Replayer — replays recorded MCP interactions as a mock server.
 *
 * The replayer loads a .vcr file and acts as a mock MCP server,
 * responding to requests with recorded responses.
 */

import { promises as fs } from "fs";
import { createInterface } from "readline";
import { createServer, Server } from "http";
import {
  VCRRecording,
  JSONRPCRequest,
  JSONRPCResponse,
  loadVCRRecording,
} from "./core/format.js";
import { RequestMatcher, createMatcher, MatchStrategy } from "./core/matcher.js";

export interface ReplayerConfig {
  recording: VCRRecording;
  matchStrategy?: MatchStrategy;
  strict?: boolean;
}

/**
 * Replays VCR recordings as a mock MCP server.
 */
export class MCPReplayer {
  private recording: VCRRecording;
  private matcher: RequestMatcher;
  private responseOverrides = new Map<string | number, JSONRPCResponse>();
  private strict: boolean;

  constructor(config: ReplayerConfig) {
    this.recording = config.recording;
    this.matcher = createMatcher(config.matchStrategy || "method_and_params");
    this.strict = config.strict ?? false;
  }

  /**
   * Load a replayer from a .vcr file.
   */
  static async fromFile(
    path: string,
    matchStrategy?: MatchStrategy,
    strict?: boolean
  ): Promise<MCPReplayer> {
    const content = await fs.readFile(path, "utf-8");
    const json = JSON.parse(content);
    const recording = loadVCRRecording(json);

    return new MCPReplayer({
      recording,
      matchStrategy,
      strict,
    });
  }

  /**
   * Handle a request and return the corresponding response.
   */
  handleRequest(request: JSONRPCRequest): JSONRPCResponse | null {
    // Check for response overrides (for error injection)
    if (this.responseOverrides.has(request.id)) {
      const override = this.responseOverrides.get(request.id)!;
      // Update the response ID to match the request
      return { ...override, id: request.id };
    }

    // Handle initialize specially
    if (request.method === "initialize") {
      return {
        ...this.recording.session.initialize_response,
        id: request.id,
      };
    }

    // Find matching interaction
    const interaction = this.matcher.match(
      request,
      this.recording.session.interactions
    );

    if (!interaction) {
      if (this.strict) {
        throw new Error(
          `No matching interaction found for request: ${JSON.stringify(request)}`
        );
      }
      return {
        jsonrpc: "2.0",
        id: request.id,
        error: {
          code: -32601,
          message: `No matching recorded interaction found for method '${request.method}'`,
        },
      };
    }

    if (!interaction.response) {
      if (this.strict) {
        throw new Error(
          `Interaction ${interaction.sequence} has no recorded response`
        );
      }
      return {
        jsonrpc: "2.0",
        id: request.id,
        error: {
          code: -32603,
          message: `Recorded interaction for '${request.method}' has no response`,
        },
      };
    }

    // Return the recorded response with the incoming request's ID
    return {
      ...interaction.response,
      id: request.id,
    };
  }

  /**
   * Set a response override for a specific request ID (for error injection).
   */
  setResponseOverride(id: string | number, response: JSONRPCResponse): void {
    this.responseOverrides.set(id, response);
  }

  /**
   * Clear all response overrides.
   */
  clearResponseOverrides(): void {
    this.responseOverrides.clear();
  }

  /**
   * Reset the matcher state (for sequential matching).
   */
  reset(): void {
    this.matcher.reset();
    this.responseOverrides.clear();
  }

  /**
   * Serve via stdio (read from stdin, write to stdout).
   */
  async serveStdio(): Promise<void> {
    const readline = createInterface({
      input: process.stdin,
      output: process.stdout,
      terminal: false,
    });

    readline.on("line", (line) => {
      try {
        const request = JSON.parse(line) as JSONRPCRequest;
        const response = this.handleRequest(request);

        if (response) {
          process.stdout.write(JSON.stringify(response) + "\n");
        }
      } catch (error) {
        console.error("Error handling request:", error);
      }
    });

    // Keep process alive
    await new Promise(() => {});
  }

  /**
   * Serve via HTTP + SSE.
   */
  async serveSSE(host = "127.0.0.1", port = 3000): Promise<Server> {
    const server = createServer((req, res) => {
      // Enable CORS
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers", "Content-Type");

      if (req.method === "OPTIONS") {
        res.writeHead(204);
        res.end();
        return;
      }

      // Handle POST requests with JSON-RPC messages
      if (req.method === "POST" && req.url === "/message") {
        let body = "";

        req.on("data", (chunk) => {
          body += chunk.toString();
        });

        req.on("end", () => {
          try {
            const request = JSON.parse(body) as JSONRPCRequest;
            const response = this.handleRequest(request);

            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(JSON.stringify(response));
          } catch (error) {
            res.writeHead(400, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "Invalid request" }));
          }
        });

        return;
      }

      // Health check
      if (req.method === "GET" && req.url === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok" }));
        return;
      }

      res.writeHead(404);
      res.end("Not found");
    });

    await new Promise<void>((resolve) => {
      server.listen(port, host, () => {
        console.log(`Replayer serving on ${host}:${port}`);
        resolve();
      });
    });

    return server;
  }

  /**
   * Get the recording.
   */
  getRecording(): VCRRecording {
    return this.recording;
  }
}
