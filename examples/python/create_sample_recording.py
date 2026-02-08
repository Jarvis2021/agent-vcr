#!/usr/bin/env python3
"""
Create a sample VCR recording demonstrating realistic MCP interactions.

This script programmatically builds a complete .vcr recording file with:
- Proper session initialization (initialize request/response)
- tools/list interaction
- tools/call interaction for a sample tool
- resources/read interaction

This is useful for demonstration and testing without needing a real MCP server.

Usage:
    python create_sample_recording.py [output_path]

Example:
    python create_sample_recording.py sample.vcr
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from agent_vcr.core.format import (
    JSONRPCError,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
    VCRRecording,
    VCRSession,
)


def create_sample_recording() -> VCRRecording:
    """Create a sample VCR recording with realistic MCP interactions.

    Returns:
        VCRRecording with initialization and sample interactions
    """
    # Recording metadata
    now = datetime.now()
    metadata = VCRMetadata(
        version="1.0.0",
        recorded_at=now,
        transport="stdio",
        client_info={
            "name": "example-client",
            "version": "1.0.0",
        },
        server_info={
            "name": "example-server",
            "version": "1.0.0",
        },
        server_command="example-server",
        server_args=["--debug"],
        tags={
            "purpose": "demonstration",
            "environment": "dev",
        },
    )

    # Initialize request
    init_request = JSONRPCRequest(
        jsonrpc="2.0",
        id=1,
        method="initialize",
        params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "example-client",
                "version": "1.0.0",
            },
        },
    )

    # Initialize response with server capabilities
    init_response = JSONRPCResponse(
        jsonrpc="2.0",
        id=1,
        result={
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
            },
            "serverInfo": {
                "name": "example-server",
                "version": "1.0.0",
            },
        },
    )

    # Session with initialize handshake
    session = VCRSession(
        initialize_request=init_request,
        initialize_response=init_response,
        capabilities={
            "tools": {},
            "resources": {},
        },
        interactions=[],
    )

    # Add interactions after initialization
    base_timestamp = now

    # Interaction 1: tools/list
    interaction1 = VCRInteraction(
        sequence=0,
        timestamp=base_timestamp,
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=2,
            method="tools/list",
            params={},
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=2,
            result={
                "tools": [
                    {
                        "name": "calculate",
                        "description": "Perform a calculation",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "expression": {
                                    "type": "string",
                                    "description": "Mathematical expression to evaluate",
                                }
                            },
                            "required": ["expression"],
                        },
                    }
                ]
            },
        ),
        notifications=[],
        latency_ms=45.2,
    )
    session.interactions.append(interaction1)

    # Interaction 2: tools/call
    interaction2 = VCRInteraction(
        sequence=1,
        timestamp=datetime.fromisoformat(base_timestamp.isoformat()) +
                  __import__('datetime').timedelta(milliseconds=50),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=3,
            method="tools/call",
            params={
                "name": "calculate",
                "arguments": {
                    "expression": "2 + 2",
                },
            },
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=3,
            result={
                "content": [
                    {
                        "type": "text",
                        "text": "4",
                    }
                ]
            },
        ),
        notifications=[],
        latency_ms=123.5,
    )
    session.interactions.append(interaction2)

    # Interaction 3: resources/read
    interaction3 = VCRInteraction(
        sequence=2,
        timestamp=datetime.fromisoformat(base_timestamp.isoformat()) +
                  __import__('datetime').timedelta(milliseconds=200),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=4,
            method="resources/read",
            params={
                "uri": "file:///example/data.txt",
            },
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=4,
            result={
                "contents": [
                    {
                        "uri": "file:///example/data.txt",
                        "mimeType": "text/plain",
                        "text": "Hello, World!",
                    }
                ]
            },
        ),
        notifications=[],
        latency_ms=87.3,
    )
    session.interactions.append(interaction3)

    # Interaction 4: Error response example
    interaction4 = VCRInteraction(
        sequence=3,
        timestamp=datetime.fromisoformat(base_timestamp.isoformat()) +
                  __import__('datetime').timedelta(milliseconds=300),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=5,
            method="resources/read",
            params={
                "uri": "file:///nonexistent/file.txt",
            },
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=5,
            error=JSONRPCError(
                code=-32603,
                message="Internal error",
                data={
                    "details": "Resource not found",
                },
            ),
        ),
        notifications=[],
        latency_ms=12.1,
    )
    session.interactions.append(interaction4)

    # Create recording
    recording = VCRRecording(
        format_version="1.0.0",
        metadata=metadata,
        session=session,
    )

    return recording


def main() -> None:
    """Main entry point."""
    # Get output path from command line or use default
    output_path = sys.argv[1] if len(sys.argv) > 1 else "sample.vcr"

    # Create sample recording
    recording = create_sample_recording()

    # Save to file
    try:
        recording.save(output_path)
        print(f"Created sample recording: {output_path}")
        print(f"  Format version: {recording.format_version}")
        print(f"  Transport: {recording.metadata.transport}")
        print(f"  Interactions: {recording.interaction_count}")
        print(f"  Duration: {recording.duration:.2f}s")
        print(f"  Recorded at: {recording.metadata.recorded_at}")

        # Display a preview of the recording
        print(f"\nRecording preview:")
        for interaction in recording.session.interactions:
            method = interaction.request.method if interaction.request else "unknown"
            status = "success" if interaction.response and not interaction.response.error else "error"
            print(f"  [{interaction.sequence}] {method} -> {status} ({interaction.latency_ms}ms)")

    except IOError as e:
        print(f"Error saving recording: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
