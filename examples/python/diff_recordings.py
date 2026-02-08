#!/usr/bin/env python3
"""
Diff two VCR recordings to show what changed.

This script demonstrates how to:
1. Create two slightly different recordings programmatically
2. Use MCPDiff.compare() to diff them
3. Interpret the diff result
4. Detect breaking changes

This is useful for regression testing: record a baseline, make changes,
record again, then diff to see exactly what changed in the MCP communication.

Usage:
    python diff_recordings.py
"""

import sys
from datetime import datetime, timedelta

from agent_vcr.core.format import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
    VCRRecording,
    VCRSession,
)
from agent_vcr.diff import MCPDiff


def create_baseline_recording() -> VCRRecording:
    """Create a baseline VCR recording.

    Returns:
        VCRRecording with baseline interactions
    """
    now = datetime.now()
    metadata = VCRMetadata(
        version="1.0.0",
        recorded_at=now,
        transport="stdio",
        client_info={"name": "example-client", "version": "1.0.0"},
        server_info={"name": "example-server", "version": "1.0.0"},
        tags={"version": "baseline"},
    )

    init_request = JSONRPCRequest(
        jsonrpc="2.0",
        id=1,
        method="initialize",
        params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "example-client", "version": "1.0.0"},
        },
    )

    init_response = JSONRPCResponse(
        jsonrpc="2.0",
        id=1,
        result={
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": "example-server", "version": "1.0.0"},
        },
    )

    session = VCRSession(
        initialize_request=init_request,
        initialize_response=init_response,
        capabilities={"tools": {}, "resources": {}},
        interactions=[],
    )

    # Add baseline interactions
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
                                    "description": "Mathematical expression",
                                }
                            },
                        },
                    },
                    {
                        "name": "fetch",
                        "description": "Fetch from URL",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "url": {
                                    "type": "string",
                                    "description": "URL to fetch",
                                }
                            },
                        },
                    },
                ]
            },
        ),
        notifications=[],
        latency_ms=45.2,
    )
    session.interactions.append(interaction1)

    # Interaction 2: tools/call (calculate)
    interaction2 = VCRInteraction(
        sequence=1,
        timestamp=base_timestamp + timedelta(milliseconds=50),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=3,
            method="tools/call",
            params={
                "name": "calculate",
                "arguments": {"expression": "10 * 5"},
            },
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=3,
            result={"content": [{"type": "text", "text": "50"}]},
        ),
        notifications=[],
        latency_ms=123.5,
    )
    session.interactions.append(interaction2)

    recording = VCRRecording(
        format_version="1.0.0",
        metadata=metadata,
        session=session,
    )

    return recording


def create_modified_recording() -> VCRRecording:
    """Create a modified VCR recording with changes.

    Returns:
        VCRRecording with modified interactions
    """
    now = datetime.now()
    metadata = VCRMetadata(
        version="1.0.0",
        recorded_at=now,
        transport="stdio",
        client_info={"name": "example-client", "version": "1.1.0"},  # Version changed
        server_info={"name": "example-server", "version": "2.0.0"},  # Version changed
        tags={"version": "modified"},
    )

    init_request = JSONRPCRequest(
        jsonrpc="2.0",
        id=1,
        method="initialize",
        params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "example-client", "version": "1.1.0"},
        },
    )

    init_response = JSONRPCResponse(
        jsonrpc="2.0",
        id=1,
        result={
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": "example-server", "version": "2.0.0"},
        },
    )

    session = VCRSession(
        initialize_request=init_request,
        initialize_response=init_response,
        capabilities={"tools": {}, "resources": {}},
        interactions=[],
    )

    base_timestamp = now

    # Interaction 1: tools/list - MODIFIED
    # Removed 'fetch' tool, added 'search' tool
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
                                    "description": "Mathematical expression",
                                }
                            },
                        },
                    },
                    {
                        "name": "search",  # Changed from fetch
                        "description": "Search the knowledge base",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query",
                                }
                            },
                        },
                    },
                ]
            },
        ),
        notifications=[],
        latency_ms=50.1,  # Also slightly different latency
    )
    session.interactions.append(interaction1)

    # Interaction 2: tools/call - MODIFIED
    # Same method, but response content changed
    interaction2 = VCRInteraction(
        sequence=1,
        timestamp=base_timestamp + timedelta(milliseconds=60),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=3,
            method="tools/call",
            params={
                "name": "calculate",
                "arguments": {"expression": "10 * 5"},
            },
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=3,
            result={
                "content": [
                    {"type": "text", "text": "50"},
                    {"type": "text", "text": "Result: 10 * 5 = 50"},  # Added extra field
                ]
            },
        ),
        notifications=[],
        latency_ms=110.0,
    )
    session.interactions.append(interaction2)

    # Interaction 3: NEW interaction - tools/call (search)
    interaction3 = VCRInteraction(
        sequence=2,
        timestamp=base_timestamp + timedelta(milliseconds=150),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=4,
            method="tools/call",
            params={
                "name": "search",
                "arguments": {"query": "climate change"},
            },
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=4,
            result={"content": [{"type": "text", "text": "Found 5 results"}]},
        ),
        notifications=[],
        latency_ms=200.5,
    )
    session.interactions.append(interaction3)

    recording = VCRRecording(
        format_version="1.0.0",
        metadata=metadata,
        session=session,
    )

    return recording


def main() -> None:
    """Main entry point."""
    print("Creating baseline recording...")
    baseline_recording = create_baseline_recording()
    print(f"  Baseline interactions: {len(baseline_recording.session.interactions)}")

    print("\nCreating modified recording...")
    modified_recording = create_modified_recording()
    print(f"  Modified interactions: {len(modified_recording.session.interactions)}")

    # Compare recordings
    print("\n" + "=" * 70)
    print("DIFFING RECORDINGS")
    print("=" * 70)

    diff_result = MCPDiff.compare(baseline_recording, modified_recording)

    # Print summary
    print("\n" + diff_result.summary())

    # Print detailed output
    print("\n" + "=" * 70)
    print("DETAILED DIFF")
    print("=" * 70)
    diff_result.print_detailed()

    # Check compatibility
    print("\n" + "=" * 70)
    print("COMPATIBILITY CHECK")
    print("=" * 70)

    if diff_result.is_identical:
        print("Recordings are identical.")
    else:
        print(f"Recordings differ:")
        print(f"  - Added interactions: {len(diff_result.added_interactions)}")
        print(f"  - Removed interactions: {len(diff_result.removed_interactions)}")
        print(f"  - Modified interactions: {len(diff_result.modified_interactions)}")
        print(f"  - Is compatible: {diff_result.is_compatible}")

    if not diff_result.is_compatible:
        print("\nBreaking changes detected:")
        for change in diff_result.breaking_changes:
            print(f"  - {change}")
    else:
        print("\nNo breaking changes detected. Changes are backward compatible.")

    # Detailed interaction analysis
    if diff_result.added_interactions:
        print("\n" + "-" * 70)
        print("Added Interactions:")
        for interaction in diff_result.added_interactions:
            method = interaction.request.method if interaction.request else "unknown"
            print(f"  - {method} (seq {interaction.sequence})")

    if diff_result.removed_interactions:
        print("\n" + "-" * 70)
        print("Removed Interactions:")
        for interaction in diff_result.removed_interactions:
            method = interaction.request.method if interaction.request else "unknown"
            print(f"  - {method} (seq {interaction.sequence})")

    if diff_result.modified_interactions:
        print("\n" + "-" * 70)
        print("Modified Interactions:")
        for mod in diff_result.modified_interactions:
            req_changed = "Yes" if mod.request_diff else "No"
            resp_changed = "Yes" if mod.response_diff else "No"
            print(f"  - {mod.method}")
            print(f"    Request changed: {req_changed}")
            print(f"    Response changed: {resp_changed}")
            print(f"    Compatible: {mod.is_compatible}")


if __name__ == "__main__":
    main()
