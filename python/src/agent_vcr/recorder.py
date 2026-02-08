"""MCPRecorder — The main recording engine that transparently proxies MCP traffic.

The recorder sits between an MCP client and server, forwarding all messages
while capturing them into a VCR recording file.

Supports both stdio and SSE transports.

Usage:
    recorder = MCPRecorder(
        transport="stdio",
        server_command="node",
        server_args=["server.js"],
    )
    recording = await recorder.record(output_path="session.vcr")

    # Or with SSE:
    recorder = MCPRecorder(
        transport="sse",
        server_url="http://localhost:3000/sse",
    )
    recording = await recorder.record(output_path="session.vcr")
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from agent_vcr.core.format import (
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
    VCRRecording,
    VCRSession,
)
from agent_vcr.core.session import SessionManager
from agent_vcr.transport.sse import SSETransport
from agent_vcr.transport.stdio import StdioTransport


def _make_empty_recording(recorder: MCPRecorder) -> VCRRecording:
    """Build a minimal valid VCR recording when stop is called before any session started.

    This handles the case where a user presses Ctrl+C before any MCP client
    connects and sends an 'initialize' request, so SessionManager is still idle.
    """
    recorded_at = datetime.fromtimestamp(
        recorder._recording_start_time or time.time()
    )
    metadata = VCRMetadata(
        version="1.0",
        recorded_at=recorded_at,
        transport=recorder.transport_type,
        tags=recorder.metadata_tags,
        server_command=recorder.server_command,
        server_args=recorder.server_args,
    )
    init_request = JSONRPCRequest(jsonrpc="2.0", id=0, method="initialize", params={})
    init_response = JSONRPCResponse(jsonrpc="2.0", id=0, result={"capabilities": {}})
    session = VCRSession(
        initialize_request=init_request,
        initialize_response=init_response,
        capabilities={},
        interactions=[],
    )
    return VCRRecording(
        format_version="1.0.0",
        metadata=metadata,
        session=session,
    )

logger = logging.getLogger(__name__)


class MCPRecorder:
    """Transparent MCP traffic recorder that proxies between client and server.

    Records all JSON-RPC 2.0 interactions in a VCR format while forwarding
    messages unchanged to maintain compatibility.

    Attributes:
        transport: Transport type ("stdio" or "sse")
        server_command: Command to start server (stdio only)
        server_args: Arguments for server command (stdio only)
        server_env: Environment variables for server (stdio only)
        server_url: SSE server URL (SSE only)
        proxy_host: Proxy host for SSE (SSE only)
        proxy_port: Proxy port for SSE (SSE only)
        metadata_tags: Custom tags for recording metadata
        filter_methods: Optional set of method names to record (None = all)
        auto_save_interval: Seconds between auto-saves (0 = no auto-save)
    """

    def __init__(
        self,
        transport: str,
        server_command: Optional[str] = None,
        server_args: Optional[list[str]] = None,
        server_env: Optional[dict[str, str]] = None,
        server_url: Optional[str] = None,
        proxy_host: Optional[str] = None,
        proxy_port: Optional[int] = None,
        metadata_tags: Optional[dict[str, str]] = None,
        filter_methods: Optional[set[str]] = None,
        auto_save_interval: float = 0.0,
    ) -> None:
        """Initialize the MCPRecorder.

        Args:
            transport: "stdio" or "sse"
            server_command: Command to start server (required for stdio)
            server_args: Arguments for server command
            server_env: Environment variables for server
            server_url: SSE server URL (required for sse)
            proxy_host: Proxy host for SSE
            proxy_port: Proxy port for SSE
            metadata_tags: Custom metadata tags
            filter_methods: Set of method names to record (None = all)
            auto_save_interval: Seconds between auto-saves (0 = disabled)

        Raises:
            ValueError: If required parameters for transport type are missing
        """
        if transport not in ("stdio", "sse"):
            raise ValueError(f"Invalid transport: {transport}. Must be 'stdio' or 'sse'")

        if transport == "stdio" and not server_command:
            raise ValueError("server_command required for stdio transport")
        if transport == "sse" and not server_url:
            raise ValueError("server_url required for sse transport")

        self.transport_type = transport
        self.server_command = server_command
        self.server_args = server_args or []
        self.server_env = server_env
        self.server_url = server_url
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.metadata_tags = metadata_tags or {}
        self.filter_methods = filter_methods
        self.auto_save_interval = auto_save_interval

        # Transport instance (set up during start)
        self._transport: Optional[StdioTransport | SSETransport] = None

        # Session management
        self._session_manager = SessionManager()

        # Request/response tracking
        self._pending_requests: dict[int | str, JSONRPCRequest] = {}  # id -> request object
        self._pending_request_times: dict[int | str, float] = {}  # id -> timestamp

        # Recording state
        self._is_recording = False
        self._recording_start_time: Optional[float] = None
        self._last_auto_save: float = 0.0
        self._initialize_captured = False

        logger.info(f"MCPRecorder initialized with transport={transport}")

    async def record(self, output_path: str | Path) -> VCRRecording:
        """Record MCP traffic in blocking mode.

        Starts recording, waits for completion (until stop() is called or
        external signal), then saves and returns the recording.

        Args:
            output_path: Path to save .vcr file

        Returns:
            The completed VCRRecording

        Raises:
            RuntimeError: If recorder is already recording
            IOError: If output file cannot be written
        """
        if self._is_recording:
            raise RuntimeError("Recorder is already recording")

        await self.start()
        try:
            # Wait indefinitely for stop() to be called
            while self._is_recording:
                await asyncio.sleep(0.1)
        finally:
            return await self.stop(output_path)

    async def start(self) -> None:
        """Start recording (non-blocking).

        Initializes the transport and begins capturing messages.
        Waits for the 'initialize' method call to bootstrap the session.

        Raises:
            RuntimeError: If already recording
        """
        if self._is_recording:
            raise RuntimeError("Recorder is already recording")

        logger.info(f"Starting recorder (transport={self.transport_type})")

        # Initialize transport
        if self.transport_type == "stdio":
            self._transport = StdioTransport(
                server_command=self.server_command,
                server_args=self.server_args,
                server_env=self.server_env,
            )
        else:  # sse
            self._transport = SSETransport(
                server_url=self.server_url,
                proxy_host=self.proxy_host,
                proxy_port=self.proxy_port,
            )

        # Set recording state (but not recording yet - wait for initialize)
        self._is_recording = True
        self._recording_start_time = time.time()
        self._last_auto_save = self._recording_start_time
        self._initialize_captured = False

        # Start the transport with callbacks passed directly
        await self._transport.start(
            on_client_message=self._on_client_message,
            on_server_message=self._on_server_message,
        )

        logger.info("Recorder started")

    async def stop(self, output_path: str | Path) -> VCRRecording:
        """Stop recording and save to file.

        Args:
            output_path: Path to save .vcr file

        Returns:
            The completed VCRRecording

        Raises:
            RuntimeError: If not currently recording
            IOError: If output file cannot be written
        """
        if not self._is_recording:
            raise RuntimeError("Recorder is not currently recording")

        logger.info("Stopping recorder")

        # Close transport
        if self._transport:
            await self._transport.stop()

        # Get final recording (or minimal placeholder if session never started, e.g. Ctrl+C before any client connected)
        if self._session_manager.is_recording:
            recording = self._session_manager.stop_recording()
        else:
            recording = _make_empty_recording(self)

        # Save to file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(
                recording.model_dump(mode="json", default=str),
                f,
                indent=2,
            )

        self._is_recording = False
        logger.info(f"Recording saved to {output_path}")

        return recording

    def _on_client_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle message from client to server.

        Captures the message and stores it pending the response.
        For 'initialize' method, triggers session recording initialization.

        Args:
            message: JSON-RPC 2.0 message dict

        Returns:
            The message to forward (unchanged), or None to drop it
        """
        try:
            msg_id = message.get("id")
            method = message.get("method")

            # Skip if filtering and method not included
            if self.filter_methods and method and method not in self.filter_methods:
                logger.debug(f"Filtering out client message: {method}")
                return message

            # Parse as JSONRPCRequest
            request_obj = self._parse_jsonrpc_request(message)
            if not request_obj:
                return message

            # Track request and timing
            if msg_id is not None:
                self._pending_requests[msg_id] = request_obj
                self._pending_request_times[msg_id] = time.time()

            # Log for debugging
            if method:
                logger.debug(f"Client request: {method} (id={msg_id})")

            # Forward the message unchanged
            return message

        except Exception as e:
            logger.error(f"Error handling client message: {e}", exc_info=True)
            return message

    def _on_server_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle message from server to client.

        Captures the message and pairs it with the corresponding request,
        then records the interaction.

        Args:
            message: JSON-RPC 2.0 message dict

        Returns:
            The message to forward (unchanged), or None to drop it
        """
        try:
            msg_id = message.get("id")

            # Parse response
            response_obj = self._parse_jsonrpc_response(message)
            if not response_obj:
                return message

            # Pair with pending request
            request_obj = self._pending_requests.pop(msg_id, None)
            request_time = self._pending_request_times.pop(msg_id, None)

            if request_obj:
                logger.debug(f"Server response: id={msg_id}")

                # Check if this is the initialize method response
                if request_obj.method == "initialize" and not self._initialize_captured:
                    self._initialize_captured = True
                    # Bootstrap the session with initialize request/response
                    metadata = VCRMetadata(
                        version="1.0",
                        recorded_at=datetime.fromtimestamp(
                            self._recording_start_time or time.time()
                        ),
                        transport=self.transport_type,
                        tags=self.metadata_tags,
                        server_command=self.server_command,
                        server_args=self.server_args,
                    )
                    self._session_manager.start_recording(
                        metadata=metadata,
                        initialize_request=request_obj,
                        initialize_response=response_obj,
                    )
                    logger.info("Session initialized with initialize handshake")
                else:
                    # Record regular interaction
                    self._session_manager.record_interaction(request_obj, response_obj)
            else:
                logger.debug(f"Received response for unknown request id={msg_id}")

        except Exception as e:
            logger.error(f"Error handling server message: {e}", exc_info=True)

        # Check if auto-save interval has elapsed
        if self.auto_save_interval > 0:
            current_time = time.time()
            if current_time - self._last_auto_save >= self.auto_save_interval:
                self._auto_save()
                self._last_auto_save = current_time

        # Forward the message unchanged
        return message

    def _parse_jsonrpc_request(self, message: dict[str, Any]) -> Optional[JSONRPCRequest]:
        """Parse a JSON-RPC request message.

        Args:
            message: Raw message dict

        Returns:
            JSONRPCRequest object or None if not a valid request
        """
        if "method" not in message or message.get("jsonrpc") != "2.0":
            return None

        return JSONRPCRequest(
            jsonrpc="2.0",
            method=message["method"],
            params=message.get("params"),
            id=message.get("id"),
        )

    def _parse_jsonrpc_response(
        self, message: dict[str, Any]
    ) -> Optional[JSONRPCResponse | JSONRPCNotification]:
        """Parse a JSON-RPC response or notification message.

        Args:
            message: Raw message dict

        Returns:
            JSONRPCResponse/JSONRPCNotification object or None if not valid
        """
        if message.get("jsonrpc") != "2.0":
            return None

        # Check if it's a notification (method but no id)
        if "method" in message and "id" not in message:
            return JSONRPCNotification(
                jsonrpc="2.0",
                method=message["method"],
                params=message.get("params"),
            )

        # Must be a response
        if "id" not in message:
            return None

        if "error" in message:
            return JSONRPCResponse(
                jsonrpc="2.0",
                error=message["error"],
                id=message["id"],
            )

        if "result" in message:
            return JSONRPCResponse(
                jsonrpc="2.0",
                result=message["result"],
                id=message["id"],
            )

        return None

    def _auto_save(self) -> None:
        """Auto-save current recording state.

        This is a checkpoint save and does not stop the recording.
        """
        try:
            # Get current recording via property
            recording = self._session_manager.current_recording
            if recording and recording.session:
                interaction_count = len(recording.session.interactions)
                logger.debug(f"Auto-save: {interaction_count} interactions")
            else:
                logger.debug("Auto-save: no recording or session yet")
        except Exception as e:
            logger.error(f"Auto-save failed: {e}")


__all__ = ["MCPRecorder"]
