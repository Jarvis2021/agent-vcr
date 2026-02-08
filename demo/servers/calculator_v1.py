#!/usr/bin/env python3
"""
Calculator MCP Server v1.0.0

A minimal MCP server that speaks JSON-RPC 2.0 over stdio.
Supports two tools: add and multiply.

Usage:
    python demo/servers/calculator_v1.py

This server is used in the Agent VCR tutorial to demonstrate:
  - Recording a live MCP session
  - Replaying it as a mock
  - Diffing against v2

The server reads JSON-RPC requests from stdin (one per line)
and writes JSON-RPC responses to stdout.
"""

import json
import sys


SERVER_INFO = {
    "name": "calculator-server",
    "version": "1.0.0",
}

TOOLS = [
    {
        "name": "add",
        "description": "Add two numbers together",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            "required": ["a", "b"],
        },
    },
    {
        "name": "multiply",
        "description": "Multiply two numbers",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "First factor"},
                "b": {"type": "number", "description": "Second factor"},
            },
            "required": ["a", "b"],
        },
    },
]


def handle_request(request: dict) -> dict:
    """Route a JSON-RPC request to the appropriate handler."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }

    elif method == "notifications/initialized":
        # This is a notification, no response needed
        return None

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "add":
            result_value = args.get("a", 0) + args.get("b", 0)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(result_value)}]
                },
            }

        elif tool_name == "multiply":
            result_value = args.get("a", 0) * args.get("b", 0)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(result_value)}]
                },
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                    "data": {"details": f"Tool '{tool_name}' is not registered"},
                },
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": "Method not found",
                "data": {"details": f"Unknown method: {method}"},
            },
        }


def main():
    """Read JSON-RPC from stdin, write responses to stdout."""
    sys.stderr.write("Calculator MCP Server v1.0.0 started (stdio)\n")
    sys.stderr.write("Waiting for JSON-RPC requests on stdin...\n")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                    "data": {"details": str(e)},
                },
            }
            print(json.dumps(error_response), flush=True)
            continue

        response = handle_request(request)
        if response is not None:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
