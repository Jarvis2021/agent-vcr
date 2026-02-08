"""MCPReplayer — Replay recorded MCP sessions as a mock server.

The replayer loads a .vcr recording and acts as a fake MCP server,
responding to requests with the recorded responses.

Usage:
    replayer = MCPReplayer.from_file("session.vcr")

    # As stdio server (pipe to your client):
    await replayer.serve_stdio()

    # As HTTP+SSE server:
    await replayer.serve_sse(host="127.0.0.1", port=3100)

    # Programmatic usage:
    response = replayer.handle_request(request_dict)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from aiohttp import web

from agent_vcr.core.format import VCRRecording
from agent_vcr.core.matcher import RequestMatcher, JSONRPCRequest

logger = logging.getLogger(__name__)


class MCPReplayer:
    """Mock MCP server that replays recorded interactions.

    Loads a VCR recording and responds to requests with the corresponding
    recorded responses, supporting multiple matching strategies.

    Attributes:
        recording: The VCRRecording to replay
        match_strategy: Matching strategy for requests ("exact", "method", etc)
    """

    def __init__(
        self,
        recording: VCRRecording,
        match_strategy: str = "method_and_params",
    ) -> None:
        """Initialize the MCPReplayer.

        Args:
            recording: VCRRecording object to replay
            match_strategy: Request matching strategy (see RequestMatcher)

        Raises:
            ValueError: If match_strategy is invalid
        """
        self.recording = recording
        self.match_strategy = match_strategy

        # Initialize matcher
        try:
            self._matcher = RequestMatcher(strategy=match_strategy)
        except ValueError as e:
            raise ValueError(f"Invalid match_strategy: {e}")

        # Track replayed interactions for sequential mode
        self._replay_count: dict[str, int] = {}

        # Custom response overrides
        self._response_overrides: dict[str, Any] = {}

        # Extract interactions from the single session
        self._interactions = list(recording.session.interactions)

        logger.info(
            f"MCPReplayer initialized with {len(self._interactions)} "
            f"interactions (strategy={match_strategy})"
        )

    @classmethod
    def from_file(
        cls, path: str | Path, match_strategy: str = "method_and_params"
    ) -> MCPReplayer:
        """Load a VCR recording from file.

        Args:
            path: Path to .vcr file
            match_strategy: Request matching strategy (see RequestMatcher)

        Returns:
            MCPReplayer instance

        Raises:
            FileNotFoundError: If file does not exist
            json.JSONDecodeError: If file is not valid JSON
            ValueError: If file is not a valid VCR recording
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"VCR file not found: {path}")

        with open(path) as f:
            data = json.load(f)

        recording = VCRRecording.model_validate(data)
        return cls(recording, match_strategy=match_strategy)

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a JSON-RPC request and return the recorded response.

        Args:
            request: JSON-RPC 2.0 request dict

        Returns:
            JSON-RPC 2.0 response dict

        Raises:
            ValueError: If no matching interaction found
            KeyError: If request is malformed
        """
        method = request.get("method")
        params = request.get("params")
        msg_id = request.get("id")

        logger.debug(f"Replayer handling request: {method} (id={msg_id})")

        # Check for override first
        if msg_id in self._response_overrides:
            logger.debug(f"Using override for request id={msg_id}")
            return self._response_overrides.pop(msg_id)

        # Parse the request into a JSONRPCRequest object
        try:
            request_obj = JSONRPCRequest(
                jsonrpc="2.0",
                id=msg_id,
                method=method,
                params=params,
            )
        except Exception as e:
            error_msg = f"Failed to parse request: {e}"
            logger.error(error_msg)
            return self._error_response(msg_id, error_msg)

        # Find matching interaction using the matcher
        matching_interaction = self._matcher.find_match(request_obj, self._interactions)

        if not matching_interaction:
            error_msg = f"No recorded interaction matching {method}({params})"
            logger.error(error_msg)
            return self._error_response(msg_id, error_msg)

        # Extract response from interaction
        if not matching_interaction.response:
            error_msg = f"Interaction {method} has no recorded response"
            logger.error(error_msg)
            return self._error_response(msg_id, error_msg)

        response_obj = matching_interaction.response

        # Build response message
        response: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": msg_id,
        }

        if response_obj.result is not None:
            response["result"] = response_obj.result
        elif response_obj.error is not None:
            response["error"] = response_obj.error

        logger.debug(f"Returning recorded response for id={msg_id}")
        return response

    def set_response_override(self, msg_id: int | str, response: dict[str, Any]) -> None:
        """Set a custom response override for a specific request id.

        Useful for testing error scenarios or modifying recorded responses.

        Args:
            msg_id: Request ID to override
            response: JSON-RPC response dict to return
        """
        self._response_overrides[msg_id] = response
        logger.debug(f"Set response override for id={msg_id}")

    def clear_response_overrides(self) -> None:
        """Clear all response overrides."""
        self._response_overrides.clear()
        logger.debug("Cleared all response overrides")

    async def serve_stdio(self) -> None:
        """Serve as a stdio-based MCP server.

        Reads JSON-RPC requests from stdin and writes responses to stdout.
        Useful for direct testing or piping to MCP clients.

        Reads until EOF or error.
        """
        logger.info("Starting stdio server")

        loop = asyncio.get_event_loop()

        try:
            while True:
                # Read line from stdin
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line:
                    # EOF
                    break

                try:
                    request = json.loads(line)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from stdin: {line}")
                    continue

                # Handle the request
                try:
                    response = self.handle_request(request)
                except Exception as e:
                    logger.error(f"Error handling request: {e}")
                    response = self._error_response(
                        request.get("id"), f"Internal error: {e}"
                    )

                # Send response
                response_line = json.dumps(response)
                await loop.run_in_executor(None, sys.stdout.write, response_line + "\n")
                await loop.run_in_executor(None, sys.stdout.flush)

        except KeyboardInterrupt:
            logger.info("Stdio server interrupted")
        except Exception as e:
            logger.error(f"Stdio server error: {e}", exc_info=True)

    async def serve_sse(
        self,
        host: str = "127.0.0.1",
        port: int = 3100,
    ) -> None:
        """Serve as an HTTP+SSE-based MCP server.

        Provides HTTP endpoints for SSE connections and JSON-RPC over HTTP.

        Args:
            host: Server host
            port: Server port
        """
        logger.info(f"Starting SSE server on {host}:{port}")

        app = web.Application()
        app.router.add_post("/rpc", self._handle_rpc_post)
        app.router.add_get("/sse", self._handle_sse_get)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        logger.info(f"SSE server listening on http://{host}:{port}")

        try:
            # Keep server running
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("SSE server interrupted")
        finally:
            await runner.cleanup()

    async def _handle_rpc_post(self, request: web.Request) -> web.Response:
        """Handle POST /rpc endpoint (JSON-RPC over HTTP).

        Args:
            request: aiohttp request

        Returns:
            JSON-RPC response
        """
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Invalid JSON in POST /rpc: {e}")
            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}},
                status=400,
            )

        try:
            response = self.handle_request(data)
            return web.json_response(response)
        except Exception as e:
            logger.error(f"Error handling RPC request: {e}")
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": "Internal error"},
                    "id": data.get("id"),
                },
                status=500,
            )

    async def _handle_sse_get(self, request: web.Request) -> web.StreamResponse:
        """Handle GET /sse endpoint (Server-Sent Events).

        Args:
            request: aiohttp request

        Returns:
            SSE stream response
        """
        response = web.StreamResponse()
        response.content_type = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"

        await response.prepare(request)

        # Send a test event
        await response.write(b"data: {\"type\": \"ready\"}\n\n")

        # Keep connection open (in a real scenario, would send events as they arrive)
        try:
            await asyncio.Event().wait()
        except (asyncio.CancelledError, ConnectionError):
            pass

        return response

    def _error_response(
        self, msg_id: int | str | None, message: str, code: int = -32603
    ) -> dict[str, Any]:
        """Create a JSON-RPC error response.

        Args:
            msg_id: Request ID
            message: Error message
            code: JSON-RPC error code (default: -32603 Internal error)

        Returns:
            JSON-RPC error response dict
        """
        response: dict[str, Any] = {
            "jsonrpc": "2.0",
            "error": {
                "code": code,
                "message": message,
            },
        }

        if msg_id is not None:
            response["id"] = msg_id

        return response


__all__ = ["MCPReplayer"]
