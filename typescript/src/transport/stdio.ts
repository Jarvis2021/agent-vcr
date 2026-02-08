/**
 * Stdio transport for MCP — spawns subprocess and proxies stdin/stdout.
 *
 * This transport spawns an MCP server as a subprocess and transparently
 * proxies JSON-RPC messages between client stdin/stdout and the server.
 */

import { spawn, ChildProcess } from "child_process";
import { createInterface, Interface } from "readline";
import { BaseTransport, TransportConfig } from "./base.js";
import { JSONRPCRequest, JSONRPCResponse } from "../core/format.js";

export interface StdioTransportConfig extends TransportConfig {
  command: string;
  args?: string[];
  cwd?: string;
  env?: Record<string, string>;
  timeout?: number;
}

/**
 * Stdio transport implementation.
 */
export class StdioTransport extends BaseTransport {
  private serverProcess: ChildProcess | null = null;
  private serverReadline: Interface | null = null;
  private clientReadline: Interface | null = null;
  private config: StdioTransportConfig;

  constructor(config: StdioTransportConfig) {
    super(config);
    this.config = config;
  }

  async start(): Promise<void> {
    if (this.isStarted) {
      throw new Error("Transport already started");
    }

    // Parse command if it's a single string with arguments
    let command = this.config.command;
    let args = this.config.args || [];

    // If command contains spaces and no args provided, split it
    if (!this.config.args && command.includes(" ")) {
      const parts = command.split(" ");
      command = parts[0];
      args = parts.slice(1);
    }

    // Spawn the MCP server subprocess
    this.serverProcess = spawn(command, args, {
      cwd: this.config.cwd,
      env: { ...process.env, ...this.config.env },
      stdio: ["pipe", "pipe", "pipe"],
    });

    if (!this.serverProcess.stdin || !this.serverProcess.stdout) {
      throw new Error("Failed to create server process stdio streams");
    }

    // Setup readline for server output
    this.serverReadline = createInterface({
      input: this.serverProcess.stdout,
      crlfDelay: Infinity,
    });

    // Setup readline for client input (stdin)
    this.clientReadline = createInterface({
      input: process.stdin,
      crlfDelay: Infinity,
    });

    // Forward server messages to client
    this.serverReadline.on("line", async (line) => {
      try {
        const message = JSON.parse(line);
        if (this.onServerMessage) {
          await this.onServerMessage(message);
        }
        // Forward to client stdout
        process.stdout.write(line + "\n");
      } catch (error) {
        console.error("Error processing server message:", error);
      }
    });

    // Forward client messages to server
    this.clientReadline.on("line", async (line) => {
      try {
        const message = JSON.parse(line);
        if (this.onClientMessage) {
          await this.onClientMessage(message);
        }
        // Forward to server stdin
        this.serverProcess?.stdin?.write(line + "\n");
      } catch (error) {
        console.error("Error processing client message:", error);
      }
    });

    // Handle server process errors
    this.serverProcess.on("error", (error) => {
      console.error("Server process error:", error);
    });

    // Handle server process exit
    this.serverProcess.on("exit", (code) => {
      if (code !== 0 && code !== null) {
        console.error(`Server process exited with code ${code}`);
      }
    });

    // Handle stderr from server (for debugging)
    this.serverProcess.stderr?.on("data", (data) => {
      console.error("Server stderr:", data.toString());
    });

    this.isStarted = true;
  }

  async stop(): Promise<void> {
    if (!this.isStarted) {
      return;
    }

    // Close readline interfaces
    this.serverReadline?.close();
    this.clientReadline?.close();

    // Kill server process
    if (this.serverProcess && !this.serverProcess.killed) {
      this.serverProcess.kill("SIGTERM");

      // Wait for process to exit with timeout
      await new Promise<void>((resolve) => {
        const timeout = setTimeout(() => {
          if (this.serverProcess && !this.serverProcess.killed) {
            this.serverProcess.kill("SIGKILL");
          }
          resolve();
        }, this.config.timeout || 5000);

        this.serverProcess?.once("exit", () => {
          clearTimeout(timeout);
          resolve();
        });
      });
    }

    this.serverProcess = null;
    this.serverReadline = null;
    this.clientReadline = null;
    this.isStarted = false;
  }

  async sendToClient(message: JSONRPCRequest | JSONRPCResponse): Promise<void> {
    process.stdout.write(JSON.stringify(message) + "\n");
  }

  async sendToServer(message: JSONRPCRequest | JSONRPCResponse): Promise<void> {
    if (!this.serverProcess?.stdin) {
      throw new Error("Server process not started");
    }
    this.serverProcess.stdin.write(JSON.stringify(message) + "\n");
  }
}
