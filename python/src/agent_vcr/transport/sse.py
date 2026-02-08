"""SSE transport — proxy for MCP servers using HTTP + Server-Sent Events.

Usage: Agent VCR runs an HTTP server that MCP clients connect to,
and proxies requests to the real MCP server's HTTP+SSE endpoint.

Client -> Agent VCR HTTP Server -> Real MCP Server (HTTP+SSE)
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Callable

import aiohttp
from aiohttp import web

from .base import BaseTransport

logger = logging.getLogger(__name__)


class SSETransport(BaseTransport):
    """HTTP+SSE-based transport proxy for remote MCP servers.

    This transport runs a local HTTP server that MCP clients connect to via HTTP.
    It proxies JSON-RPC requests to a remote MCP server and streams server-sent
    events back to the client.
    """

    def __init__(
        self,
        server_url: str,
        proxy_host: str = "127.0.0.1",
        proxy_port: int = 3100,
    ) -> None:
        """Initialize the SSE transport.

        Args:
            server_url: Base URL of the remote MCP server (e.g., "http://localhost:5000").
            proxy_host: Host to bind the proxy HTTP server to. Defaults to 127.0.0.1.
            proxy_port: Port to bind the proxy HTTP server to. Defaults to 3100.
        """
        self._server_url = server_url.rstrip("/")
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        self._is_connected = False
        self._on_client_message: Callable[[dict], dict | None] | None = None
        self._on_server_message: Callable[[dict], dict | None] | None = None
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._session: aiohttp.ClientSession | None = None
        self._sse_response: web.StreamResponse | None = None
        self._shutdown = False
        self._client_queues: dict[str, asyncio.Queue[dict]] = {}
        self._active_sse_clients: set[str] = set()

    @property
    def is_connected(self) -> bool:
        """Return whether the transport is connected."""
        return self._is_connected

    @property
    def transport_type(self) -> str:
        """Return the transport type identifier."""
        return "sse"

    async def start(
        self,
        on_client_message: Callable[[dict], dict | None],
        on_server_message: Callable[[dict], dict | None],
    ) -> None:
        """Start proxying between client and server.

        Starts the proxy HTTP server and establishes a connection to the remote
        MCP server via SSE.

        Args:
            on_client_message: Callback for messages from the client.
            on_server_message: Callback for messages from the server.

        Raises:
            RuntimeError: If the transport is already running.
            OSError: If the proxy server cannot bind to the specified host/port.
            aiohttp.ClientError: If unable to connect to the remote server.
        """
        if self._is_connected:
            raise RuntimeError("Transport is already running")

        self._on_client_message = on_client_message
        self._on_server_message = on_server_message
        self._shutdown = False

        try:
            # Create aiohttp client session
            self._session = aiohttp.ClientSession()

            # Create and start HTTP server
            self._app = web.Application()
            self._app.router.add_post("/message", self._handle_message)
            self._app.router.add_get("/sse", self._handle_sse)

            self._runner = web.AppRunner(self._app)
            await self._runner.setup()
            self._site = web.TCPSite(
                self._runner, self._proxy_host, self._proxy_port
            )
            await self._site.start()

            logger.info(
                "Proxy HTTP server started on %s:%d",
                self._proxy_host,
                self._proxy_port,
            )

            # Verify connection to remote server
            try:
                async with self._session.get(
                    f"{self._server_url}/sse",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status != 200:
                        raise aiohttp.ClientError(
                            f"Remote server returned status {resp.status}"
                        )
                    # Close this test connection immediately
                    await resp.read()
            except Exception as e:
                await self.stop()
                raise ConnectionError(f"Cannot connect to remote server: {e}") from e

            self._is_connected = True
            logger.info("Connected to remote server at %s", self._server_url)

        except Exception as e:
            self._is_connected = False
            logger.error("Failed to start transport: %s", e)
            raise

    async def stop(self) -> None:
        """Stop proxying and clean up resources.

        Shuts down the proxy HTTP server and closes the session.
        """
        self._shutdown = True
        self._is_connected = False

        # Close all client queues
        for queue in self._client_queues.values():
            queue.put_nowait(None)  # Signal EOF
        self._client_queues.clear()
        self._active_sse_clients.clear()

        # Shutdown HTTP server
        if self._site:
            try:
                await self._site.stop()
                logger.info("Proxy HTTP server stopped")
            except Exception as e:
                logger.error("Error stopping HTTP site: %s", e)

        if self._runner:
            try:
                await self._runner.cleanup()
                logger.info("Proxy HTTP server cleaned up")
            except Exception as e:
                logger.error("Error cleaning up HTTP runner: %s", e)

        # Close client session
        if self._session:
            try:
                await self._session.close()
                logger.info("Client session closed")
            except Exception as e:
                logger.error("Error closing client session: %s", e)

    async def send_to_server(self, message: dict) -> None:
        """Forward a message to the server via HTTP POST.

        Args:
            message: The JSON-RPC message dict to forward.

        Raises:
            ConnectionError: If not connected or unable to send.
        """
        if not self._is_connected or not self._session:
            raise ConnectionError("Not connected to server")

        try:
            async with self._session.post(
                f"{self._server_url}/message",
                json=message,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    raise aiohttp.ClientError(
                        f"Server returned status {resp.status}: {error_text}"
                    )
                logger.debug("Forwarded message to server: %s", message)
        except aiohttp.ClientError as e:
            self._is_connected = False
            raise ConnectionError(f"Failed to send message to server: {e}") from e

    async def send_to_client(self, message: dict) -> None:
        """Forward a message to connected clients via SSE or queue.

        For HTTP+SSE transports, messages are typically delivered via SSE events
        or queued for SSE clients. This method sends to all active SSE clients.

        Args:
            message: The JSON-RPC message dict to forward.

        Raises:
            ConnectionError: If no clients are connected.
        """
        if not self._active_sse_clients:
            raise ConnectionError("No connected clients")

        try:
            # Queue the message for all active SSE clients
            for client_id in self._active_sse_clients:
                if client_id in self._client_queues:
                    await self._client_queues[client_id].put(message)
            logger.debug("Queued message for %d clients", len(self._active_sse_clients))
        except Exception as e:
            raise ConnectionError(f"Failed to send message to clients: {e}") from e

    async def _handle_message(self, request: web.Request) -> web.Response:
        """Handle JSON-RPC message POST requests from the client.

        Args:
            request: The aiohttp request object.

        Returns:
            JSON response with status 200 or error response.
        """
        try:
            message = await request.json()
            logger.debug("Received message from client: %s", message)

            # Invoke client message callback
            if self._on_client_message:
                try:
                    forwarded = self._on_client_message(message)
                except Exception as e:
                    logger.exception("Exception in on_client_message callback: %s", e)
                    forwarded = message
            else:
                forwarded = message

            # Forward to server if not suppressed
            if forwarded is None:
                return web.json_response({"jsonrpc": "2.0", "result": None})

            try:
                await self.send_to_server(forwarded)
                return web.json_response({"jsonrpc": "2.0", "result": "ok"})
            except ConnectionError as e:
                logger.error("Failed to forward message to server: %s", e)
                return web.json_response(
                    {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}},
                    status=500,
                )

        except json.JSONDecodeError as e:
            logger.error("Failed to parse request JSON: %s", e)
            return web.json_response(
                {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}},
                status=400,
            )
        except Exception as e:
            logger.error("Unexpected error handling message: %s", e)
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32603, "message": "Internal error"},
                },
                status=500,
            )

    async def _handle_sse(self, request: web.Request) -> web.StreamResponse:
        """Handle Server-Sent Events stream requests from the client.

        Args:
            request: The aiohttp request object.

        Returns:
            A streaming response that sends events from the server to the client.
        """
        client_id = str(uuid.uuid4())
        self._active_sse_clients.add(client_id)
        client_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._client_queues[client_id] = client_queue

        logger.info("SSE client connected: %s", client_id)

        response = web.StreamResponse()
        response.content_type = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"

        try:
            await response.prepare(request)

            # Start listening for server-sent events
            server_sse_task = asyncio.create_task(
                self._proxy_server_sse(client_id, response)
            )

            # Also listen to the client queue for other messages
            while not self._shutdown:
                try:
                    message = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    if message is None:  # EOF signal
                        break

                    # Send as SSE event
                    sse_data = json.dumps(message)
                    await response.write(f"data: {sse_data}\n\n".encode("utf-8"))
                    logger.debug("Sent SSE event to client %s: %s", client_id, message)

                except asyncio.TimeoutError:
                    # Send a keep-alive comment
                    await response.write(b": keep-alive\n\n")
                except Exception as e:
                    logger.error("Error sending SSE data to client %s: %s", client_id, e)
                    break

            # Cancel the server SSE task
            server_sse_task.cancel()
            try:
                await server_sse_task
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.error("Error in SSE stream for client %s: %s", client_id, e)
        finally:
            self._active_sse_clients.discard(client_id)
            self._client_queues.pop(client_id, None)
            logger.info("SSE client disconnected: %s", client_id)
            try:
                await response.write_eof()
            except Exception:
                pass

        return response

    async def _proxy_server_sse(self, client_id: str, response: web.StreamResponse) -> None:
        """Proxy SSE events from the remote server to a client.

        Connects to the remote server's SSE endpoint and forwards events.

        Args:
            client_id: The ID of the client to send events to.
            response: The StreamResponse to write events to.
        """
        if not self._session:
            return

        try:
            async with self._session.get(
                f"{self._server_url}/sse",
                timeout=aiohttp.ClientTimeout(total=None, sock_read=30),
            ) as server_resp:
                if server_resp.status != 200:
                    logger.error(
                        "Remote server SSE returned status %d for client %s",
                        server_resp.status,
                        client_id,
                    )
                    return

                async for line in server_resp.content:
                    if self._shutdown:
                        break

                    line_str = line.decode("utf-8").rstrip()
                    if not line_str or line_str.startswith(":"):
                        # Keep-alive or empty line
                        continue

                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        try:
                            server_message = json.loads(data_str)
                            logger.debug(
                                "Received SSE from server for client %s: %s",
                                client_id,
                                server_message,
                            )

                            # Invoke server message callback
                            if self._on_server_message:
                                try:
                                    forwarded = self._on_server_message(server_message)
                                except Exception as e:
                                    logger.exception(
                                        "Exception in on_server_message callback: %s", e
                                    )
                                    forwarded = server_message
                            else:
                                forwarded = server_message

                            # Forward to client if not suppressed
                            if forwarded is not None:
                                await self.send_to_client(forwarded)

                        except json.JSONDecodeError as e:
                            logger.error("Failed to parse server SSE data: %s", e)

        except asyncio.CancelledError:
            logger.debug("Server SSE proxy cancelled for client %s", client_id)
        except Exception as e:
            logger.error("Error proxying server SSE for client %s: %s", client_id, e)
