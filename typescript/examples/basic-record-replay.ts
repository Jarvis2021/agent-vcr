/**
 * Basic example: Record and replay MCP interactions
 *
 * This example demonstrates:
 * 1. Recording MCP interactions to a .vcr file
 * 2. Loading and replaying the recording
 * 3. Handling requests programmatically
 */

import { MCPRecorder, MCPReplayer } from "../src/index.js";

async function recordExample() {
  console.log("Starting recording...");

  const recorder = new MCPRecorder({
    transport: "stdio",
    command: "node",
    args: ["../demo/servers/calculator_v1.js"],
    metadata: {
      tags: {
        env: "development",
        purpose: "example",
      },
    },
  });

  await recorder.start();
  console.log("Recording started. Interact with the server, then press Ctrl+C to stop.");

  // Handle graceful shutdown
  process.on("SIGINT", async () => {
    console.log("\nStopping recording...");
    const recording = await recorder.stop();
    await recorder.save(recording, "examples/basic-recording.vcr");
    console.log("Recording saved to examples/basic-recording.vcr");
    process.exit(0);
  });

  // Keep alive
  await new Promise(() => {});
}

async function replayExample() {
  console.log("Loading recording...");

  // Load the recording
  const replayer = await MCPReplayer.fromFile(
    "examples/basic-recording.vcr",
    "method_and_params",
    false // not strict - allow unmatched requests
  );

  console.log("Recording loaded. Handling some requests...\n");

  // Handle initialize
  const initRequest = {
    jsonrpc: "2.0" as const,
    id: 0,
    method: "initialize",
    params: {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: {
        name: "example-client",
        version: "1.0.0",
      },
    },
  };

  const initResponse = replayer.handleRequest(initRequest);
  console.log("Initialize response:", JSON.stringify(initResponse, null, 2));

  // Handle a tools/list request
  const listToolsRequest = {
    jsonrpc: "2.0" as const,
    id: 1,
    method: "tools/list",
  };

  const listToolsResponse = replayer.handleRequest(listToolsRequest);
  console.log("\nTools list response:", JSON.stringify(listToolsResponse, null, 2));

  // Handle a tools/call request
  const callToolRequest = {
    jsonrpc: "2.0" as const,
    id: 2,
    method: "tools/call",
    params: {
      name: "add",
      arguments: { a: 5, b: 3 },
    },
  };

  const callToolResponse = replayer.handleRequest(callToolRequest);
  console.log("\nTool call response:", JSON.stringify(callToolResponse, null, 2));

  console.log("\n✅ Replay complete!");
}

async function errorInjectionExample() {
  console.log("Loading recording for error injection...");

  const replayer = await MCPReplayer.fromFile("examples/basic-recording.vcr");

  // Inject an error for request id=2
  console.log("\nInjecting error for request id=2...");
  replayer.setResponseOverride(2, {
    jsonrpc: "2.0",
    id: 2,
    error: {
      code: -32603,
      message: "Simulated internal server error",
      data: { reason: "Testing error handling" },
    },
  });

  // Now when we make the request, we get the error
  const request = {
    jsonrpc: "2.0" as const,
    id: 2,
    method: "tools/call",
    params: {
      name: "add",
      arguments: { a: 5, b: 3 },
    },
  };

  const response = replayer.handleRequest(request);
  console.log("\nError response:", JSON.stringify(response, null, 2));

  // Clear overrides and try again
  console.log("\nClearing overrides and retrying...");
  replayer.clearResponseOverrides();
  replayer.reset();

  const normalResponse = replayer.handleRequest(request);
  console.log("\nNormal response:", JSON.stringify(normalResponse, null, 2));

  console.log("\n✅ Error injection example complete!");
}

// Main
const mode = process.argv[2] || "replay";

switch (mode) {
  case "record":
    recordExample();
    break;
  case "replay":
    replayExample();
    break;
  case "error-injection":
    errorInjectionExample();
    break;
  default:
    console.log("Usage: node basic-record-replay.js [record|replay|error-injection]");
    process.exit(1);
}
