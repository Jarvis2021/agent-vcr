"""Base transport interface for MCP proxy transports."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable

logger = logging.getLogger(__name__)


class BaseTransport(ABC):
    """Abstract base class for MCP proxy transports.

    Subclasses implement transparent proxying between MCP clients and servers,
    recording JSON-RPC 2.0 messages as they pass through.
    """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return whether the transport is currently connected and operational."""
        pass

    @property
    @abstractmethod
    def transport_type(self) -> str:
        """Return a string identifier for this transport type (e.g., 'stdio', 'sse')."""
        pass

    @abstractmethod
    async def start(
        self,
        on_client_message: Callable[[dict], dict | None],
        on_server_message: Callable[[dict], dict | None],
    ) -> None:
        """Start proxying between client and server.

        Args:
            on_client_message: Callback invoked when a message arrives from the client.
                Receives a parsed JSON-RPC message dict. Should return a dict to forward
                (possibly modified), or None to suppress forwarding. Exceptions raised
                in the callback will be logged and the original message forwarded.
            on_server_message: Callback invoked when a message arrives from the server.
                Receives a parsed JSON-RPC message dict. Should return a dict to forward
                (possibly modified), or None to suppress forwarding. Exceptions raised
                in the callback will be logged and the original message forwarded.

        Raises:
            RuntimeError: If the transport is already running.
            ConnectionError: If unable to establish connection to the server.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop proxying and clean up resources.

        This method should gracefully shut down the transport, close any open
        connections, and terminate any spawned processes. It is safe to call
        multiple times and should not raise exceptions.
        """
        pass

    @abstractmethod
    async def send_to_server(self, message: dict) -> None:
        """Forward a JSON-RPC message to the MCP server.

        Args:
            message: The parsed JSON-RPC message dict to forward.

        Raises:
            ConnectionError: If not connected to the server.
            Exception: Subclass-specific exceptions for send failures.
        """
        pass

    @abstractmethod
    async def send_to_client(self, message: dict) -> None:
        """Forward a JSON-RPC message to the MCP client.

        Args:
            message: The parsed JSON-RPC message dict to forward.

        Raises:
            ConnectionError: If not connected to the client.
            Exception: Subclass-specific exceptions for send failures.
        """
        pass
