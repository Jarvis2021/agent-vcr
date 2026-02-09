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

from agent_vcr.core.format import VCRRecording, VCRInteraction
from agent_vcr.core.matcher import RequestMatcher, JSONRPCRequest

logger = logging.getLogger(__name__)


class MCPReplayer:
    """Mock MCP server that replays recorded interactions.

    Loads a VCR recording and responds to requests with the corresponding
    recorded responses, supporting multiple matching strategies.

    Attributes:
        recording: The VCRRecording to replay
        match_strategy: Matching strategy for requests ("exact", "method", etc)
        simulate_latency: If True, sleep for the recorded latency before responding
        latency_multiplier: Multiplier for simulated latency (e.g. 0.5 = half speed)
    """

    def __init__(
        self,
        recording: VCRRecording,
        match_strategy: str = "method_and_params",
        simulate_latency: bool = False,
        latency_multiplier: float = 1.0,
    ) -> None:
        """Initialize the MCPReplayer.

        Args:
            recording: VCRRecording object to replay
            match_strategy: Request matching strategy (see RequestMatcher)
            simulate_latency: Whether to sleep for recorded latency before responding
            latency_multiplier: Multiplier for simulated latency (default 1.0)

        Raises:
            ValueError: If match_strategy is invalid
        """
        self.recording = recording
        self.match_strategy = match_strategy
        self.simulate_latency = simulate_latency
        self.latency_multiplier = latency_multiplier

        # Initialize matcher
        try:
            self._matcher = RequestMatcher(strategy=match_strategy)
        except ValueError as e:
            raise ValueError(f"Invalid match_strategy: {e}")

        # Custom response overrides
        self._response_overrides: dict[str, Any] = {}

        # Extract interactions from the single session
        self._interactions = list(recording.session.interactions)

        # SSE client connections for streaming responses
        self._sse_clients: list[web.StreamResponse] = []

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
        response, _ = self._handle_request_with_interaction(request)
        return response

    async def handle_request_async(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a JSON-RPC request asynchronously, with optional latency simulation.

        If simulate_latency is enabled, sleeps for the recorded latency before
        returning the response. Also sends any recorded notifications before
        the response via the notification callback.

        Args:
            request: JSON-RPC 2.0 request dict

        Returns:
            JSON-RPC 2.0 response dict
        """
        response, interaction = self._handle_request_with_interaction(request)

        if interaction and self.simulate_latency and interaction.latency_ms > 0:
            delay = (interaction.latency_ms / 1000.0) * self.latency_multiplier
            if delay > 0:
                logger.debug(f"Simulating latency: {delay:.3f}s")
                await asyncio.sleep(delay)

        return response

    def get_notifications_for_request(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        """Get recorded notifications that were associated with a request.

        Args:
            request: JSON-RPC 2.0 request dict

        Returns:
            List of JSON-RPC notification dicts
        """
        _, interaction = self._handle_request_with_interaction(request)
        if not interaction or not interaction.notifications:
            return []
        return [
            {"jsonrpc": "2.0", "method": n.method, **({"params": n.params} if n.params else {})}
            for n in interaction.notifications
        ]

    def _handle_request_with_interaction(
        self, request: dict[str, Any]
    ) -> tuple[dict[str, Any], Optional[VCRInteraction]]:
        """Internal: handle request and return both response and matched interaction.

        Args:
            request: JSON-RPC 2.0 request dict

        Returns:
            Tuple of (response_dict, matched_interaction_or_None)
        """
        method = request.get("method")
        params = request.get("params")
        msg_id = request.get("id")

        logger.debug(f"Replayer handling request: {method} (id={msg_id})")

        # Check for override first
        if msg_id in self._response_overrides:
            logger.debug(f"Using override for request id={msg_id}")
            return self._response_overrides.pop(msg_id), None

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
            return self._error_response(msg_id, error_msg), None

        # Find matching interaction using the matcher
        matching_interaction = self._matcher.find_match(request_obj, self._interactions)

        if not matching_interaction:
            error_msg = f"No recorded interaction matching {method}({params})"
            logger.error(error_msg)
            return self._error_response(msg_id, error_msg, code=-32601), None

        # Extract response from interaction
        if not matching_interaction.response:
            error_msg = f"Interaction {method} has no recorded response"
            logger.error(error_msg)
            return self._error_response(msg_id, error_msg), matching_interaction

        response_obj = matching_interaction.response

        # Build response message
        response: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": msg_id,
        }

        if response_obj.result is not None:
            response["result"] = response_obj.result
        elif response_obj.error is not None:
            response["error"] = response_obj.error.model_dump(exclude_none=True)

        logger.debug(f"Returning recorded response for id={msg_id}")
        return response, matching_interaction

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
        Sends any recorded notifications before the response.
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

                # Handle the request (with latency simulation if enabled)
                try:
                    # Send recorded notifications before the response
                    response, interaction = self._handle_request_with_interaction(request)

                    if interaction and interaction.notifications:
                        for notification in interaction.notifications:
                            notif_dict: dict[str, Any] = {
                                "jsonrpc": "2.0",
                                "method": notification.method,
                            }
                            if notification.params is not None:
                                notif_dict["params"] = notification.params
                            notif_line = json.dumps(notif_dict)
                            await loop.run_in_executor(None, sys.stdout.write, notif_line + "\n")
                            await loop.run_in_executor(None, sys.stdout.flush)

                    # Simulate latency if enabled
                    if interaction and self.simulate_latency and interaction.latency_ms > 0:
                        delay = (interaction.latency_ms / 1000.0) * self.latency_multiplier
                        if delay > 0:
                            await asyncio.sleep(delay)

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
        The MCP SSE protocol works as follows:
        1. Client connects to GET /sse to establish an SSE stream
        2. Server sends an 'endpoint' event with the URL for POST requests
        3. Client sends JSON-RPC requests to POST /message
        4. Server sends responses back via the SSE stream

        Args:
            host: Server host
            port: Server port
        """
        logger.info(f"Starting SSE server on {host}:{port}")

        app = web.Application()
        app.router.add_get("/sse", self._handle_sse_get)
        app.router.add_post("/message", self._handle_sse_message)
        # Also support /rpc for backward compatibility
        app.router.add_post("/rpc", self._handle_rpc_post)

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
            # Clean up SSE clients
            for client in self._sse_clients:
                try:
                    await client.write_eof()
                except Exception:
                    pass
            self._sse_clients.clear()
            await runner.cleanup()

    async def _handle_rpc_post(self, request: web.Request) -> web.Response:
        """Handle POST /rpc endpoint (JSON-RPC over HTTP, direct response).

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
            response = await self.handle_request_async(data)
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

        Establishes an SSE connection and sends the endpoint URL for the client
        to POST JSON-RPC requests to.

        Args:
            request: aiohttp request

        Returns:
            SSE stream response
        """
        response = web.StreamResponse()
        response.content_type = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        response.headers["Access-Control-Allow-Origin"] = "*"

        await response.prepare(request)

        # Register this SSE client
        self._sse_clients.append(response)

        # Send the endpoint event per MCP SSE protocol
        # Client should POST JSON-RPC requests to this URL
        host = request.host
        endpoint_url = f"http://{host}/message"
        await response.write(
            f"event: endpoint\ndata: {endpoint_url}\n\n".encode("utf-8")
        )

        logger.info(f"SSE client connected, endpoint: {endpoint_url}")

        # Keep connection open until client disconnects
        try:
            disconnected = asyncio.Event()
            # Check periodically if connection is still alive
            while not disconnected.is_set():
                try:
                    await asyncio.sleep(30)
                    # Send keepalive comment
                    await response.write(b": keepalive\n\n")
                except (ConnectionError, ConnectionResetError):
                    break
        except (asyncio.CancelledError, ConnectionError):
            pass
        finally:
            if response in self._sse_clients:
                self._sse_clients.remove(response)
            logger.info("SSE client disconnected")

        return response

    async def _handle_sse_message(self, request: web.Request) -> web.Response:
        """Handle POST /message endpoint (JSON-RPC via SSE).

        Receives a JSON-RPC request, matches it to a recorded interaction,
        sends any recorded notifications via SSE, then sends the response via SSE.

        Args:
            request: aiohttp request

        Returns:
            HTTP 202 Accepted (response is sent via SSE stream)
        """
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Invalid JSON in POST /message: {e}")
            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}},
                status=400,
            )

        # Process the request
        try:
            response, interaction = self._handle_request_with_interaction(data)

            # Simulate latency if enabled
            if interaction and self.simulate_latency and interaction.latency_ms > 0:
                delay = (interaction.latency_ms / 1000.0) * self.latency_multiplier
                if delay > 0:
                    await asyncio.sleep(delay)

            # Send notifications via SSE before the response
            if interaction and interaction.notifications:
                for notification in interaction.notifications:
                    notif_dict: dict[str, Any] = {
                        "jsonrpc": "2.0",
                        "method": notification.method,
                    }
                    if notification.params is not None:
                        notif_dict["params"] = notification.params
                    await self._broadcast_sse_event("message", json.dumps(notif_dict))

            # Send response via SSE
            await self._broadcast_sse_event("message", json.dumps(response))

        except Exception as e:
            logger.error(f"Error handling SSE message: {e}")
            error_response = self._error_response(
                data.get("id"), f"Internal error: {e}"
            )
            await self._broadcast_sse_event("message", json.dumps(error_response))

        # Return 202 Accepted — the actual response goes via SSE
        return web.Response(status=202, text="Accepted")

    async def _broadcast_sse_event(self, event: str, data: str) -> None:
        """Send an SSE event to all connected clients.

        Args:
            event: SSE event name
            data: SSE event data (JSON string)
        """
        dead_clients = []
        for client in self._sse_clients:
            try:
                await client.write(
                    f"event: {event}\ndata: {data}\n\n".encode("utf-8")
                )
            except (ConnectionError, ConnectionResetError):
                dead_clients.append(client)

        # Remove disconnected clients
        for client in dead_clients:
            self._sse_clients.remove(client)

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
