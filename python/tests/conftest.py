"""Shared fixtures and test utilities for Agent VCR tests."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

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


# ===== JSON-RPC Message Fixtures =====


@pytest.fixture
def sample_init_request() -> JSONRPCRequest:
    """Sample initialize request (MCP standard)."""
    return JSONRPCRequest(
        jsonrpc="2.0",
        id=1,
        method="initialize",
        params={
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {
                    "listChanged": True,
                },
                "sampling": {},
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0",
            },
        },
    )


@pytest.fixture
def sample_init_response() -> JSONRPCResponse:
    """Sample initialize response with server capabilities."""
    return JSONRPCResponse(
        jsonrpc="2.0",
        id=1,
        result={
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
                "logging": {},
            },
            "serverInfo": {
                "name": "test-server",
                "version": "1.0.0",
            },
        },
    )


@pytest.fixture
def sample_metadata() -> VCRMetadata:
    """Sample VCR metadata."""
    return VCRMetadata(
        version="1.0.0",
        recorded_at=datetime(2024, 1, 15, 10, 30, 0),
        transport="stdio",
        client_info={
            "name": "test-client",
            "version": "1.0.0",
        },
        server_info={
            "name": "test-server",
            "version": "1.0.0",
        },
        server_command="python -m test_server",
        server_args=["--debug"],
        tags={
            "environment": "test",
            "test_type": "unit",
        },
    )


# ===== Interaction Fixtures =====


@pytest.fixture
def sample_interaction() -> VCRInteraction:
    """Sample VCR interaction for tools/list request."""
    return VCRInteraction(
        sequence=0,
        timestamp=datetime(2024, 1, 15, 10, 30, 1),
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
                        "name": "echo",
                        "description": "Echo tool",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                            },
                        },
                    },
                ],
            },
        ),
        notifications=[],
        latency_ms=50.0,
    )


@pytest.fixture
def sample_tool_call_interaction() -> VCRInteraction:
    """Sample VCR interaction for tools/call request."""
    return VCRInteraction(
        sequence=1,
        timestamp=datetime(2024, 1, 15, 10, 30, 2),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=3,
            method="tools/call",
            params={
                "name": "echo",
                "arguments": {"text": "hello"},
            },
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=3,
            result={
                "content": [
                    {
                        "type": "text",
                        "text": "hello",
                    },
                ],
            },
        ),
        notifications=[],
        latency_ms=25.0,
    )


@pytest.fixture
def sample_resource_list_interaction() -> VCRInteraction:
    """Sample VCR interaction for resources/list request."""
    return VCRInteraction(
        sequence=2,
        timestamp=datetime(2024, 1, 15, 10, 30, 3),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=4,
            method="resources/list",
            params={},
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=4,
            result={
                "resources": [
                    {
                        "uri": "file:///tmp/test.txt",
                        "name": "Test File",
                        "mimeType": "text/plain",
                    },
                ],
            },
        ),
        notifications=[],
        latency_ms=15.0,
    )


@pytest.fixture
def sample_error_interaction() -> VCRInteraction:
    """Sample VCR interaction with error response."""
    return VCRInteraction(
        sequence=3,
        timestamp=datetime(2024, 1, 15, 10, 30, 4),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=5,
            method="tools/call",
            params={
                "name": "nonexistent",
                "arguments": {},
            },
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=5,
            error=JSONRPCError(
                code=-32601,
                message="Method not found",
            ),
        ),
        notifications=[],
        latency_ms=10.0,
    )


@pytest.fixture
def sample_interaction_with_notifications() -> VCRInteraction:
    """Sample VCR interaction with notifications."""
    return VCRInteraction(
        sequence=4,
        timestamp=datetime(2024, 1, 15, 10, 30, 5),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=6,
            method="tools/list",
            params={},
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=6,
            result={"tools": []},
        ),
        notifications=[
            JSONRPCNotification(
                jsonrpc="2.0",
                method="notifications/progress",
                params={
                    "progressToken": "abc123",
                    "progress": 50,
                    "total": 100,
                },
            ),
            JSONRPCNotification(
                jsonrpc="2.0",
                method="notifications/progress",
                params={
                    "progressToken": "abc123",
                    "progress": 100,
                    "total": 100,
                },
            ),
        ],
        latency_ms=100.0,
    )


# ===== Session Fixtures =====


@pytest.fixture
def sample_session(
    sample_init_request: JSONRPCRequest,
    sample_init_response: JSONRPCResponse,
    sample_interaction: VCRInteraction,
    sample_tool_call_interaction: VCRInteraction,
    sample_resource_list_interaction: VCRInteraction,
) -> VCRSession:
    """Sample VCR session with initialize and multiple interactions."""
    return VCRSession(
        initialize_request=sample_init_request,
        initialize_response=sample_init_response,
        capabilities={
            "tools": {},
            "resources": {},
            "logging": {},
        },
        interactions=[
            sample_interaction,
            sample_tool_call_interaction,
            sample_resource_list_interaction,
        ],
    )


@pytest.fixture
def empty_session(
    sample_init_request: JSONRPCRequest,
    sample_init_response: JSONRPCResponse,
) -> VCRSession:
    """VCR session with no interactions."""
    return VCRSession(
        initialize_request=sample_init_request,
        initialize_response=sample_init_response,
        capabilities={
            "tools": {},
            "resources": {},
        },
        interactions=[],
    )


# ===== Recording Fixtures =====


@pytest.fixture
def sample_recording(
    sample_metadata: VCRMetadata,
    sample_session: VCRSession,
) -> VCRRecording:
    """Complete VCR recording with metadata and session."""
    return VCRRecording(
        format_version="1.0.0",
        metadata=sample_metadata,
        session=sample_session,
    )


@pytest.fixture
def empty_recording(
    sample_metadata: VCRMetadata,
    empty_session: VCRSession,
) -> VCRRecording:
    """VCR recording with no interactions."""
    return VCRRecording(
        format_version="1.0.0",
        metadata=sample_metadata,
        session=empty_session,
    )


@pytest.fixture
def sample_recording_file(tmp_path: Path, sample_recording: VCRRecording) -> Path:
    """Save a sample recording to a temporary file and return the path."""
    vcr_file = tmp_path / "sample.vcr"
    sample_recording.save(str(vcr_file))
    return vcr_file


@pytest.fixture
def empty_recording_file(tmp_path: Path, empty_recording: VCRRecording) -> Path:
    """Save an empty recording to a temporary file and return the path."""
    vcr_file = tmp_path / "empty.vcr"
    empty_recording.save(str(vcr_file))
    return vcr_file


# ===== Complex Recording Fixtures for Testing =====


@pytest.fixture
def multi_interaction_recording(
    sample_metadata: VCRMetadata,
    sample_init_request: JSONRPCRequest,
    sample_init_response: JSONRPCResponse,
    sample_interaction: VCRInteraction,
    sample_tool_call_interaction: VCRInteraction,
    sample_resource_list_interaction: VCRInteraction,
    sample_error_interaction: VCRInteraction,
    sample_interaction_with_notifications: VCRInteraction,
) -> VCRRecording:
    """Recording with many different types of interactions."""
    session = VCRSession(
        initialize_request=sample_init_request,
        initialize_response=sample_init_response,
        capabilities={},
        interactions=[
            sample_interaction,
            sample_tool_call_interaction,
            sample_resource_list_interaction,
            sample_error_interaction,
            sample_interaction_with_notifications,
        ],
    )
    return VCRRecording(
        format_version="1.0.0",
        metadata=sample_metadata,
        session=session,
    )


@pytest.fixture
def recording_with_error_response(
    sample_metadata: VCRMetadata,
    sample_init_request: JSONRPCRequest,
    sample_init_response: JSONRPCResponse,
    sample_error_interaction: VCRInteraction,
) -> VCRRecording:
    """Recording focused on error responses."""
    session = VCRSession(
        initialize_request=sample_init_request,
        initialize_response=sample_init_response,
        capabilities={},
        interactions=[sample_error_interaction],
    )
    return VCRRecording(
        format_version="1.0.0",
        metadata=sample_metadata,
        session=session,
    )


# ===== Helper Functions =====


@pytest.fixture
def create_recording(
    sample_metadata: VCRMetadata,
    sample_init_request: JSONRPCRequest,
    sample_init_response: JSONRPCResponse,
) -> Any:
    """Factory fixture for creating custom recordings."""

    def _create(interactions: List[VCRInteraction]) -> VCRRecording:
        session = VCRSession(
            initialize_request=sample_init_request,
            initialize_response=sample_init_response,
            capabilities={},
            interactions=interactions,
        )
        return VCRRecording(
            format_version="1.0.0",
            metadata=sample_metadata,
            session=session,
        )

    return _create


@pytest.fixture
def create_request() -> Any:
    """Factory fixture for creating JSON-RPC requests."""

    def _create(
        method: str,
        params: Any = None,
        msg_id: int = 1,
    ) -> JSONRPCRequest:
        return JSONRPCRequest(
            jsonrpc="2.0",
            id=msg_id,
            method=method,
            params=params,
        )

    return _create


@pytest.fixture
def create_response() -> Any:
    """Factory fixture for creating JSON-RPC responses."""

    def _create(
        result: Any = None,
        error: JSONRPCError | None = None,
        msg_id: int = 1,
    ) -> JSONRPCResponse:
        return JSONRPCResponse(
            jsonrpc="2.0",
            id=msg_id,
            result=result,
            error=error,
        )

    return _create
