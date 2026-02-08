"""stdio transport — proxy for MCP servers that communicate via stdin/stdout.

Usage: Agent VCR spawns the real MCP server as a subprocess and proxies
stdin/stdout between the client and server while recording all messages.

The client connects to Agent VCR's stdin/stdout, and Agent VCR connects
to the real server's stdin/stdout via subprocess.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Callable

from .base import BaseTransport

logger = logging.getLogger(__name__)


class StdioTransport(BaseTransport):
    """Stdio-based transport proxy for subprocess-based MCP servers.

    This transport spawns an MCP server as a subprocess and proxies JSON-RPC
    messages bidirectionally between the client (via process stdin/stdout)
    and the server subprocess.
    """

    def __init__(
        self,
        server_command: str,
        server_args: list[str] | None = None,
        server_env: dict[str, str] | None = None,
        client_stdin_fd: int | None = None,
    ) -> None:
        """Initialize the stdio transport.

        Args:
            server_command: Path or name of the MCP server executable.
            server_args: Command-line arguments to pass to the server. Defaults to empty list.
            server_env: Environment variables for the server process. If None, inherits
                from the current process. To merge with current env, pass
                {**os.environ, ...your_vars...}.
            client_stdin_fd: Optional fd to read client input from (e.g. pipe read end).
                When set, used instead of sys.stdin for demo/automated recording.
        """
        self._server_command = server_command
        self._server_args = server_args or []
        self._server_env = server_env
        self._client_stdin_fd = client_stdin_fd
        self._is_connected = False
        self._on_client_message: Callable[[dict], dict | None] | None = None
        self._on_server_message: Callable[[dict], dict | None] | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._writer_task: asyncio.Task[None] | None = None
        self._shutdown = False

    @property
    def is_connected(self) -> bool:
        """Return whether the transport is connected."""
        return self._is_connected

    @property
    def transport_type(self) -> str:
        """Return the transport type identifier."""
        return "stdio"

    async def start(
        self,
        on_client_message: Callable[[dict], dict | None],
        on_server_message: Callable[[dict], dict | None],
    ) -> None:
        """Start proxying between client and server.

        Spawns the MCP server subprocess and begins bidirectional message proxying.

        Args:
            on_client_message: Callback for messages from the client.
            on_server_message: Callback for messages from the server.

        Raises:
            RuntimeError: If the transport is already running.
            OSError: If the server executable cannot be found or started.
        """
        if self._is_connected:
            raise RuntimeError("Transport is already running")

        self._on_client_message = on_client_message
        self._on_server_message = on_server_message
        self._shutdown = False

        try:
            # Spawn the server subprocess
            logger.info(
                "Starting subprocess: %s %s",
                self._server_command,
                " ".join(self._server_args),
            )
            self._process = await asyncio.create_subprocess_exec(
                self._server_command,
                *self._server_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._server_env,
            )
            self._is_connected = True
            logger.info("Server subprocess started (PID: %d)", self._process.pid)

            # Start reader and writer tasks
            self._reader_task = asyncio.create_task(self._read_messages())
            self._writer_task = asyncio.create_task(self._monitor_process())

        except Exception as e:
            self._is_connected = False
            logger.error("Failed to start transport: %s", e)
            raise

    async def stop(self) -> None:
        """Stop proxying and clean up resources.

        Gracefully terminates the server subprocess and cancels I/O tasks.
        """
        self._shutdown = True
        self._is_connected = False

        # Cancel reader task
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

        # Cancel writer task
        if self._writer_task and not self._writer_task.done():
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass

        # Terminate the subprocess
        if self._process:
            if self._process.returncode is None:
                logger.info("Terminating server subprocess (PID: %d)", self._process.pid)
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        "Subprocess did not terminate, killing (PID: %d)",
                        self._process.pid,
                    )
                    self._process.kill()
                    try:
                        await asyncio.wait_for(self._process.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.error("Failed to kill subprocess (PID: %d)", self._process.pid)
            else:
                logger.info(
                    "Server subprocess already terminated (PID: %d, code: %d)",
                    self._process.pid,
                    self._process.returncode,
                )

    async def send_to_server(self, message: dict) -> None:
        """Forward a message to the server.

        Args:
            message: The JSON-RPC message dict to forward.

        Raises:
            ConnectionError: If not connected to the server.
        """
        if not self._is_connected or not self._process or not self._process.stdin:
            raise ConnectionError("Not connected to server")

        try:
            json_line = json.dumps(message)
            self._process.stdin.write((json_line + "\n").encode("utf-8"))
            await self._process.stdin.drain()
            logger.debug("Forwarded message to server: %s", json_line)
        except (BrokenPipeError, ConnectionResetError) as e:
            self._is_connected = False
            raise ConnectionError(f"Failed to send message to server: {e}") from e

    async def send_to_client(self, message: dict) -> None:
        """Forward a message to the client via stdout.

        Args:
            message: The JSON-RPC message dict to forward.

        Raises:
            ConnectionError: If unable to write to stdout.
        """
        try:
            json_line = json.dumps(message)
            sys.stdout.write(json_line + "\n")
            sys.stdout.flush()
            logger.debug("Forwarded message to client: %s", json_line)
        except (BrokenPipeError, OSError) as e:
            raise ConnectionError(f"Failed to send message to client: {e}") from e

    async def _read_messages(self) -> None:
        """Read and proxy messages from both client stdin and server stdout.

        Runs two concurrent flows: one reading server stdout, one reading client stdin.
        This allows the client to send first (MCP initialize), avoiding deadlock where
        the server waits for input and the transport was waiting for server output.
        """
        if not self._process or not self._process.stdout:
            raise RuntimeError("Cannot read messages: server process not started or stdout unavailable")

        loop = asyncio.get_event_loop()
        client_reader = asyncio.StreamReader()
        stdin_fd = self._client_stdin_fd if self._client_stdin_fd is not None else sys.stdin.fileno()

        def _read_client_stdin() -> None:
            try:
                if self._client_stdin_fd is not None:
                    buf = os.read(self._client_stdin_fd, 4096)
                    data = buf if buf else b""
                    if not data:
                        client_reader.feed_eof()
                        try:
                            loop.remove_reader(stdin_fd)
                        except Exception:
                            pass
                        return
                else:
                    data = sys.stdin.buffer.read(4096)
                    if not data:
                        client_reader.feed_eof()
                        return
                if data:
                    client_reader.feed_data(data)
            except Exception as e:
                logger.error("Error reading from client stdin: %s", e)
                client_reader.feed_eof()

        try:
            loop.add_reader(stdin_fd, _read_client_stdin)

            async def _read_from_server() -> None:
                """Read server stdout and forward to client."""
                try:
                    while not self._shutdown and self._process and self._process.stdout:
                        server_line = await asyncio.wait_for(
                            self._process.stdout.readline(), timeout=60.0
                        )
                        if not server_line:
                            logger.info("Server stdout closed")
                            return
                        try:
                            server_message = json.loads(server_line.decode("utf-8").strip())
                            logger.debug("Received from server: %s", server_message)
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
                            if forwarded is not None:
                                await self.send_to_client(forwarded)
                        except json.JSONDecodeError as e:
                            logger.error("Failed to parse server message: %s", e)
                        except ConnectionError as e:
                            logger.error("Failed to forward server message to client: %s", e)
                            return
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(
                        "Error in server read loop: %s %s",
                        type(e).__name__,
                        e or "(no message)",
                    )

            async def _read_from_client() -> None:
                """Read client stdin and forward to server."""
                try:
                    while not self._shutdown:
                        try:
                            client_line = await asyncio.wait_for(
                                client_reader.readline(), timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            continue
                        if not client_line:
                            logger.info("Client stdin closed")
                            return
                        try:
                            client_message = json.loads(
                                client_line.decode("utf-8").strip()
                            )
                            logger.debug("Received from client: %s", client_message)
                            if self._on_client_message:
                                try:
                                    forwarded = self._on_client_message(client_message)
                                except Exception as e:
                                    logger.exception(
                                        "Exception in on_client_message callback: %s", e
                                    )
                                    forwarded = client_message
                            else:
                                forwarded = client_message
                            if forwarded is not None:
                                await self.send_to_server(forwarded)
                        except json.JSONDecodeError as e:
                            logger.error("Failed to parse client message: %s", e)
                        except ConnectionError as e:
                            logger.error(
                                "Failed to forward client message to server: %s", e
                            )
                            return
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(
                        "Error in client read loop: %s %s",
                        type(e).__name__,
                        e or "(no message)",
                    )

            await asyncio.gather(_read_from_server(), _read_from_client())
        except asyncio.CancelledError:
            logger.debug("Message reader cancelled")
            raise
        except Exception as e:
            logger.error(
                "Error in message reading loop: %s %s",
                type(e).__name__,
                e or "(no message)",
            )
        finally:
            try:
                loop.remove_reader(stdin_fd)
            except Exception:
                pass
            if self._client_stdin_fd is not None:
                try:
                    os.close(self._client_stdin_fd)
                except OSError:
                    pass
            self._is_connected = False

    async def _monitor_process(self) -> None:
        """Monitor the server subprocess and detect crashes.

        This task waits for the process to exit and logs the exit code.
        """
        if not self._process:
            return

        try:
            await self._process.wait()
            exit_code = self._process.returncode
            logger.warning("Server subprocess exited with code: %d", exit_code)
            self._is_connected = False
        except asyncio.CancelledError:
            logger.debug("Process monitor cancelled")
            raise
        except Exception as e:
            logger.error("Error monitoring process: %s", e)
            self._is_connected = False
