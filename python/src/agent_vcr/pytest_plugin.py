"""Pytest plugin for Agent VCR - seamless recording/replay in tests.

Provides pytest fixtures and markers for recording and replaying MCP interactions.

Usage:
    # In your test file:
    @pytest.mark.vcr("path/to/recording.vcr")
    def test_my_mcp_tool(vcr_replayer):
        response = vcr_replayer.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "my_tool", "arguments": {}}
        })
        assert "result" in response

    # Or use the async context manager:
    async def test_inline():
        async with vcr_cassette("my_test.vcr") as cassette:
            response = cassette.replayer.handle_request(...)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

import pytest

from agent_vcr.core.format import VCRRecording
from agent_vcr.recorder import MCPRecorder
from agent_vcr.replayer import MCPReplayer


class VCRConfig:
    """Configuration for the VCR pytest plugin."""

    def __init__(self, vcr_record: bool, vcr_dir: str):
        """Initialize VCR configuration.

        Args:
            vcr_record: Whether to record new cassettes instead of replaying.
            vcr_dir: Directory for cassette files.
        """
        self.vcr_record = vcr_record
        self.vcr_dir = Path(vcr_dir)
        self.vcr_dir.mkdir(parents=True, exist_ok=True)


def pytest_addoption(parser: Any) -> None:
    """Add pytest command-line options for VCR.

    Options:
        --vcr-record: Record new cassettes instead of replaying existing ones
        --vcr-dir: Directory for cassette files (default: cassettes/)
    """
    group = parser.getgroup("vcr")
    group.addoption(
        "--vcr-record",
        action="store_true",
        default=False,
        help="Record new VCR cassettes instead of replaying existing ones",
    )
    group.addoption(
        "--vcr-dir",
        default="cassettes",
        help="Directory for VCR cassette files (default: cassettes/)",
    )


def pytest_configure(config: Any) -> None:
    """Configure pytest and register markers for VCR.

    Registers the following markers:
        @pytest.mark.vcr("path/to/recording.vcr"): Use specific VCR recording
        @pytest.mark.vcr_record(...): Record a new VCR cassette
    """
    config.addinivalue_line(
        "markers",
        "vcr(path): Use a specific VCR recording file for this test",
    )
    config.addinivalue_line(
        "markers",
        "vcr_record(transport, server_command, ...): Record a new VCR cassette for this test",
    )

    # Store VCR config on the config object
    vcr_config = VCRConfig(
        vcr_record=config.getoption("--vcr-record"),
        vcr_dir=config.getoption("--vcr-dir"),
    )
    config.vcr = vcr_config


@pytest.fixture
def vcr_recording(request: Any) -> VCRRecording:
    """Load a VCR recording for the test.

    Uses the recording specified by @pytest.mark.vcr("path") if available,
    or defaults to cassettes/{test_name}.vcr.

    Returns:
        VCRRecording: The loaded recording.

    Raises:
        FileNotFoundError: If the recording file cannot be found.
    """
    vcr_config: VCRConfig = request.config.vcr

    # Check for explicit marker
    vcr_marker = request.node.get_closest_marker("vcr")
    if vcr_marker:
        recording_path = vcr_marker.args[0]
    else:
        # Use default naming: cassettes/{test_name}.vcr
        test_name = request.node.name
        recording_path = str(vcr_config.vcr_dir / f"{test_name}.vcr")

    recording_path = Path(recording_path)

    # Load existing or raise
    if not recording_path.exists():
        raise FileNotFoundError(
            f"VCR recording not found: {recording_path}. "
            f"Run with --vcr-record to create it."
        )

    return VCRRecording.load(str(recording_path))


@pytest.fixture
def vcr_replayer(vcr_recording: VCRRecording) -> MCPReplayer:
    """Get a replayer pre-loaded with the test's recording.

    Args:
        vcr_recording: The VCR recording fixture.

    Returns:
        MCPReplayer: A configured replayer instance.
    """
    return MCPReplayer(vcr_recording, match_strategy="method_and_params")


@pytest.fixture
def vcr_recorder(request: Any, tmp_path: Path) -> MCPRecorder:
    """Get a recorder configured for testing.

    Creates a recorder with stdio transport. The test must provide a
    server_command via the @pytest.mark.vcr_record marker.

    Args:
        request: Pytest request fixture.
        tmp_path: Pytest's tmp_path fixture.

    Returns:
        MCPRecorder: A configured recorder instance (not yet started).
    """
    vcr_record_marker = request.node.get_closest_marker("vcr_record")

    transport = "stdio"
    server_command = None
    server_args: list[str] = []
    server_url = None

    if vcr_record_marker:
        transport = vcr_record_marker.kwargs.get("transport", "stdio")
        server_command = vcr_record_marker.kwargs.get("server_command")
        server_args = vcr_record_marker.kwargs.get("server_args", [])
        server_url = vcr_record_marker.kwargs.get("server_url")

    return MCPRecorder(
        transport=transport,
        server_command=server_command,
        server_args=server_args,
        server_url=server_url,
    )


@asynccontextmanager
async def vcr_cassette(
    name: str,
    transport: str = "stdio",
    server_command: str | None = None,
    server_args: list[str] | None = None,
    server_url: str | None = None,
    match_strategy: str = "method_and_params",
    record: bool = False,
    cassette_dir: str = "cassettes",
) -> AsyncGenerator[VCRCassette, None]:
    """Async context manager for inline VCR usage in tests.

    This allows tests to use VCR inline without needing fixtures, useful for
    tests that need to control when recording/replaying starts and stops.

    Args:
        name: Name of the cassette file (e.g., "test_name.vcr").
        transport: Transport protocol: "stdio" or "sse".
        server_command: Command to start the server (for recording with stdio).
        server_args: Arguments to pass to server command (default: []).
        server_url: URL of the server (for recording with sse).
        match_strategy: Request matching strategy for replay.
        record: Whether to record new interactions (default: replay existing).
        cassette_dir: Directory for cassette files (default: "cassettes").

    Yields:
        VCRCassette: Object with .recording and .replayer attributes.

    Example:
        async with vcr_cassette(
            "my_test.vcr",
            transport="stdio",
            server_command="node server.js"
        ) as cassette:
            # Use cassette.replayer or cassette.recording
            response = cassette.replayer.handle_request(...)
    """
    cassette_dir_path = Path(cassette_dir)
    cassette_dir_path.mkdir(parents=True, exist_ok=True)
    cassette_path = cassette_dir_path / name

    if record:
        # Record mode
        if not server_command and not server_url:
            raise ValueError(
                "Either server_command (stdio) or server_url (sse) required for recording"
            )

        recorder = MCPRecorder(
            transport=transport,
            server_command=server_command,
            server_args=server_args or [],
            server_url=server_url,
        )

        cassette_obj = VCRCassette(
            recording=None,
            replayer=None,
            recorder=recorder,
        )

        # Start recording — the caller is responsible for stopping
        await recorder.start()

        try:
            yield cassette_obj
        finally:
            # Stop and save
            recording = await recorder.stop(str(cassette_path))
            replayer = MCPReplayer(recording, match_strategy=match_strategy)
            cassette_obj.recording = recording
            cassette_obj.replayer = replayer
    else:
        # Replay mode
        if not cassette_path.exists():
            raise FileNotFoundError(
                f"VCR cassette not found: {cassette_path}. "
                f"Record it first or use record=True."
            )

        recording = VCRRecording.load(str(cassette_path))
        replayer = MCPReplayer(recording, match_strategy=match_strategy)

        cassette_obj = VCRCassette(
            recording=recording,
            replayer=replayer,
            recorder=None,
        )

        yield cassette_obj


class VCRCassette:
    """Holder for VCR cassette resources (recording/replayer/recorder).

    Attributes:
        recording: The loaded VCRRecording (available in both modes).
        replayer: MCPReplayer for handling requests (replay mode).
        recorder: MCPRecorder for capturing interactions (record mode).
    """

    def __init__(
        self,
        recording: VCRRecording | None,
        replayer: MCPReplayer | None,
        recorder: MCPRecorder | None = None,
    ):
        """Initialize a VCR cassette.

        Args:
            recording: The loaded or to-be-loaded recording.
            replayer: The replayer instance.
            recorder: The recorder instance (optional, for record mode).
        """
        self.recording = recording
        self.replayer = replayer
        self.recorder = recorder
