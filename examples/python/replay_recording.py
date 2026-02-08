#!/usr/bin/env python3
"""
Replay a VCR recording using MCPReplayer programmatically.

This script demonstrates how to:
1. Load a .vcr file
2. Initialize MCPReplayer with different match strategies
3. Handle requests against the recorded responses
4. Use response overrides for custom scenarios

This is useful for testing clients programmatically without needing
to run the CLI.

Usage:
    python replay_recording.py [vcr_file] [match_strategy]

Example:
    python replay_recording.py sample.vcr method_and_params
    python replay_recording.py sample.vcr exact
"""

import json
import sys
from pathlib import Path

from agent_vcr.replayer import MCPReplayer


def demonstrate_replayer(vcr_file: str, match_strategy: str = "method_and_params") -> None:
    """Demonstrate MCPReplayer functionality.

    Args:
        vcr_file: Path to the .vcr file to load
        match_strategy: Request matching strategy

    Raises:
        FileNotFoundError: If vcr_file doesn't exist
        ValueError: If the file is invalid
    """
    vcr_path = Path(vcr_file)

    if not vcr_path.exists():
        print(f"Error: VCR file not found: {vcr_file}", file=sys.stderr)
        sys.exit(1)

    try:
        # Create the replayer
        replayer = MCPReplayer.from_file(vcr_path, match_strategy=match_strategy)
        print(f"Loaded recording: {vcr_file}")
        print(f"  Interactions: {len(replayer.recording.session.interactions)}")
        print(f"  Match strategy: {match_strategy}")
        print()

        # Example 1: Replay tools/list
        print("=" * 60)
        print("Example 1: Replaying tools/list request")
        print("=" * 60)

        tools_list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        print(f"Request: {json.dumps(tools_list_request, indent=2)}")
        response = replayer.handle_request(tools_list_request)
        print(f"Response: {json.dumps(response, indent=2)}")
        print()

        # Example 2: Replay tools/call
        print("=" * 60)
        print("Example 2: Replaying tools/call request")
        print("=" * 60)

        tools_call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "calculate",
                "arguments": {
                    "expression": "2 + 2",
                },
            },
        }

        print(f"Request: {json.dumps(tools_call_request, indent=2)}")
        response = replayer.handle_request(tools_call_request)
        print(f"Response: {json.dumps(response, indent=2)}")
        print()

        # Example 3: Replay resources/read (success case)
        print("=" * 60)
        print("Example 3: Replaying resources/read request (success)")
        print("=" * 60)

        resources_read_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/read",
            "params": {
                "uri": "file:///example/data.txt",
            },
        }

        print(f"Request: {json.dumps(resources_read_request, indent=2)}")
        response = replayer.handle_request(resources_read_request)
        print(f"Response: {json.dumps(response, indent=2)}")
        print()

        # Example 4: Replay resources/read (error case)
        print("=" * 60)
        print("Example 4: Replaying resources/read request (error)")
        print("=" * 60)

        resources_read_error_request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/read",
            "params": {
                "uri": "file:///nonexistent/file.txt",
            },
        }

        print(f"Request: {json.dumps(resources_read_error_request, indent=2)}")
        response = replayer.handle_request(resources_read_error_request)
        print(f"Response: {json.dumps(response, indent=2)}")
        print()

        # Example 5: Using response overrides
        print("=" * 60)
        print("Example 5: Using response overrides")
        print("=" * 60)

        # Set a custom override for a request
        custom_response = {
            "jsonrpc": "2.0",
            "id": 99,
            "result": {
                "message": "Custom override response",
            },
        }

        replayer.set_response_override(99, custom_response)
        print(f"Set override for request id=99")

        override_request = {
            "jsonrpc": "2.0",
            "id": 99,
            "method": "tools/list",
            "params": {},
        }

        print(f"Request: {json.dumps(override_request, indent=2)}")
        response = replayer.handle_request(override_request)
        print(f"Response: {json.dumps(response, indent=2)}")
        print(f"(This is the custom override, not the recorded response)")
        print()

        # Example 6: Handling unknown requests
        print("=" * 60)
        print("Example 6: Handling unknown requests")
        print("=" * 60)

        unknown_request = {
            "jsonrpc": "2.0",
            "id": 999,
            "method": "unknown/method",
            "params": {},
        }

        print(f"Request: {json.dumps(unknown_request, indent=2)}")
        try:
            response = replayer.handle_request(unknown_request)
            print(f"Response: {json.dumps(response, indent=2)}")
        except ValueError as e:
            print(f"Error: {e}")
        print()

        # Summary
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Successfully replayed {len(replayer.recording.session.interactions)} interactions")
        print(f"Match strategy: {replayer.match_strategy}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python replay_recording.py <vcr_file> [match_strategy]", file=sys.stderr)
        print()
        print("Examples:")
        print("  python replay_recording.py sample.vcr")
        print("  python replay_recording.py sample.vcr method_and_params")
        print("  python replay_recording.py sample.vcr exact")
        sys.exit(1)

    vcr_file = sys.argv[1]
    match_strategy = sys.argv[2] if len(sys.argv) > 2 else "method_and_params"

    demonstrate_replayer(vcr_file, match_strategy)


if __name__ == "__main__":
    main()
