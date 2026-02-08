#!/usr/bin/env python3
"""
Calculator MCP Server v2.0.0

An updated version of the calculator server with:
  - NEW tool: divide
  - NEW capability: resources
  - CHANGED: responses now include metadata (computation_time_ms, precision)

Usage:
    python demo/servers/calculator_v2.py

Used in the Agent VCR tutorial to demonstrate:
  - Diffing v1 vs v2 to detect added tools and schema changes
  - Compatibility gating in CI (--fail-on-breaking)
  - Protocol evolution tracking
"""

import json
import sys
import time


SERVER_INFO = {
    "name": "calculator-server",
    "version": "2.0.0",
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
    {
        "name": "divide",
        "description": "Divide first number by second",
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number", "description": "Dividend"},
                "b": {"type": "number", "description": "Divisor (non-zero)"},
            },
            "required": ["a", "b"],
        },
    },
]


def make_result(value, start_time):
    """Build a result with v2 metadata."""
    elapsed_ms = round((time.time() - start_time) * 1000, 2)
    return {
        "content": [{"type": "text", "text": str(value)}],
        "metadata": {
            "computation_time_ms": elapsed_ms,
            "precision": "float64",
        },
    }


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
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "serverInfo": SERVER_INFO,
            },
        }

    elif method == "notifications/initialized":
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
        start = time.time()

        if tool_name == "add":
            result_value = args.get("a", 0) + args.get("b", 0)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": make_result(result_value, start),
            }

        elif tool_name == "multiply":
            result_value = args.get("a", 0) * args.get("b", 0)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": make_result(result_value, start),
            }

        elif tool_name == "divide":
            a = args.get("a", 0)
            b = args.get("b", 0)
            if b == 0:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32603,
                        "message": "Division by zero",
                        "data": {
                            "details": f"Cannot divide {a} by 0",
                            "tool": "divide",
                            "input": {"a": a, "b": b},
                        },
                    },
                }
            result_value = a / b
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": make_result(result_value, start),
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
    sys.stderr.write("Calculator MCP Server v2.0.0 started (stdio)\n")
    sys.stderr.write("New in v2: divide tool, resources capability, response metadata\n")
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
