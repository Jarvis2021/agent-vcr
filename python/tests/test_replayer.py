"""Tests for MCPReplayer request handling (without SSE/network)."""

from datetime import datetime
from pathlib import Path

import pytest

from agent_vcr.core.format import (
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
    VCRRecording,
    VCRSession,
)
from agent_vcr.replayer import MCPReplayer


# ===== Fixtures for Replayer Tests =====


@pytest.fixture
def simple_recording() -> VCRRecording:
    """Simple recording with basic interactions."""
    init_req = JSONRPCRequest(
        jsonrpc="2.0", id=1, method="initialize"
    )
    init_resp = JSONRPCResponse(
        jsonrpc="2.0", id=1, result={"capabilities": {}}
    )

    interactions = [
        VCRInteraction(
            sequence=0,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0", id=2, method="tools/list"
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0",
                id=2,
                result={
                    "tools": [
                        {"name": "echo", "description": "Echo tool"}
                    ]
                },
            ),
            latency_ms=50.0,
        ),
        VCRInteraction(
            sequence=1,
            timestamp=datetime(2024, 1, 15, 10, 30, 1),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0",
                id=3,
                method="tools/call",
                params={"name": "echo", "arguments": {"text": "hello"}},
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0",
                id=3,
                result={"content": [{"type": "text", "text": "hello"}]},
            ),
            latency_ms=25.0,
        ),
    ]

    session = VCRSession(
        initialize_request=init_req,
        initialize_response=init_resp,
        capabilities={"tools": {}},
        interactions=interactions,
    )

    return VCRRecording(
        format_version="1.0.0",
        metadata=VCRMetadata(
            version="1.0.0",
            recorded_at=datetime(2024, 1, 15, 10, 30),
            transport="stdio",
        ),
        session=session,
    )


@pytest.fixture
def error_response_recording() -> VCRRecording:
    """Recording with error response."""
    init_req = JSONRPCRequest(
        jsonrpc="2.0", id=1, method="initialize"
    )
    init_resp = JSONRPCResponse(
        jsonrpc="2.0", id=1, result={"capabilities": {}}
    )

    interactions = [
        VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0",
                id=2,
                method="tools/call",
                params={"name": "nonexistent"},
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0",
                id=2,
                error=JSONRPCError(
                    code=-32601, message="Method not found"
                ),
            ),
            latency_ms=10.0,
        ),
    ]

    session = VCRSession(
        initialize_request=init_req,
        initialize_response=init_resp,
        interactions=interactions,
    )

    return VCRRecording(
        format_version="1.0.0",
        metadata=VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        ),
        session=session,
    )


# ===== MCPReplayer Initialization Tests =====


class TestMCPReplayerInit:
    """Tests for MCPReplayer initialization."""

    def test_init_default_strategy(self, simple_recording: VCRRecording):
        """Default strategy is method_and_params."""
        replayer = MCPReplayer(simple_recording)
        assert replayer.match_strategy == "method_and_params"

    def test_init_with_strategy(self, simple_recording: VCRRecording):
        """Can specify matching strategy."""
        for strategy in ["exact", "method", "method_and_params", "fuzzy", "sequential"]:
            replayer = MCPReplayer(simple_recording, match_strategy=strategy)
            assert replayer.match_strategy == strategy

    def test_init_invalid_strategy(self, simple_recording: VCRRecording):
        """Invalid strategy raises ValueError."""
        with pytest.raises(ValueError):
            MCPReplayer(simple_recording, match_strategy="invalid")  # type: ignore

    def test_init_loads_interactions(self, simple_recording: VCRRecording):
        """Interactions are loaded from recording."""
        replayer = MCPReplayer(simple_recording)
        assert len(replayer._interactions) == 2

    def test_init_stores_recording(self, simple_recording: VCRRecording):
        """Recording is stored."""
        replayer = MCPReplayer(simple_recording)
        assert replayer.recording == simple_recording


# ===== MCPReplayer.from_file Tests =====


class TestMCPReplayerFromFile:
    """Tests for loading recordings from file."""

    def test_from_file_loads_recording(
        self, simple_recording: VCRRecording, tmp_path: Path
    ):
        """from_file loads recording from .vcr file."""
        vcr_file = tmp_path / "test.vcr"
        simple_recording.save(str(vcr_file))

        replayer = MCPReplayer.from_file(str(vcr_file))

        assert replayer.recording == simple_recording
        assert len(replayer._interactions) == 2

    def test_from_file_missing_file(self):
        """from_file raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            MCPReplayer.from_file("/nonexistent/file.vcr")

    def test_from_file_with_strategy(
        self, simple_recording: VCRRecording, tmp_path: Path
    ):
        """from_file accepts match_strategy parameter."""
        vcr_file = tmp_path / "test.vcr"
        simple_recording.save(str(vcr_file))

        replayer = MCPReplayer.from_file(
            str(vcr_file), match_strategy="fuzzy"
        )

        assert replayer.match_strategy == "fuzzy"

    def test_from_file_with_path_object(
        self, simple_recording: VCRRecording, tmp_path: Path
    ):
        """from_file accepts Path objects."""
        vcr_file = tmp_path / "test.vcr"
        simple_recording.save(str(vcr_file))

        replayer = MCPReplayer.from_file(vcr_file)

        assert replayer.recording == simple_recording


# ===== MCPReplayer.handle_request Tests =====


class TestMCPReplayerHandleRequest:
    """Tests for request handling."""

    def test_handle_request_basic(self, simple_recording: VCRRecording):
        """Handle basic matching request."""
        replayer = MCPReplayer(simple_recording)

        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }

        response = replayer.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert "tools" in response["result"]

    def test_handle_request_with_params(self, simple_recording: VCRRecording):
        """Handle request with parameters."""
        replayer = MCPReplayer(simple_recording)

        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"text": "hello"}},
        }

        response = replayer.handle_request(request)

        assert response["id"] == 3
        assert "result" in response

    def test_handle_request_no_match(self, simple_recording: VCRRecording):
        """Handle request with no matching interaction returns JSON-RPC error, not None."""
        replayer = MCPReplayer(simple_recording)

        request = {
            "jsonrpc": "2.0",
            "id": 999,
            "method": "nonexistent/method",
        }

        response = replayer.handle_request(request)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 999
        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "No recorded interaction matching" in response["error"]["message"]
        assert "result" not in response

    def test_handle_request_error_response(
        self, error_response_recording: VCRRecording
    ):
        """Handle request that returns error."""
        replayer = MCPReplayer(error_response_recording)

        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "nonexistent"},
        }

        response = replayer.handle_request(request)

        assert "error" in response
        assert response["error"]["code"] == -32601

    def test_handle_request_result_field(
        self, simple_recording: VCRRecording
    ):
        """Response includes result field when present."""
        replayer = MCPReplayer(simple_recording)

        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }

        response = replayer.handle_request(request)

        assert "result" in response
        assert response["result"] is not None

    def test_handle_request_error_field(
        self, error_response_recording: VCRRecording
    ):
        """Response includes error field when present."""
        replayer = MCPReplayer(error_response_recording)

        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "nonexistent"},
        }

        response = replayer.handle_request(request)

        assert "error" in response
        assert response["error"] is not None

    def test_handle_request_sequential_strategy(
        self, simple_recording: VCRRecording
    ):
        """Sequential strategy returns interactions in order."""
        replayer = MCPReplayer(
            simple_recording, match_strategy="sequential"
        )

        # First request matches first interaction
        response1 = replayer.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "anything",
            }
        )
        assert "tools" in response1.get("result", {})

        # Second request matches second interaction
        response2 = replayer.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "anything_else",
            }
        )
        assert "content" in response2.get("result", {})

    def test_handle_request_preserves_id(
        self, simple_recording: VCRRecording
    ):
        """Response uses request ID even if different from recorded."""
        replayer = MCPReplayer(simple_recording)

        request = {
            "jsonrpc": "2.0",
            "id": 9999,
            "method": "tools/list",
        }

        response = replayer.handle_request(request)

        assert response["id"] == 9999


# ===== Response Override Tests =====


class TestMCPReplayerResponseOverride:
    """Tests for response override functionality."""

    def test_set_response_override(self, simple_recording: VCRRecording):
        """Can set response override."""
        replayer = MCPReplayer(simple_recording)

        override_response = {
            "jsonrpc": "2.0",
            "id": 999,
            "result": {"custom": "response"},
        }

        replayer.set_response_override(999, override_response)

        request = {
            "jsonrpc": "2.0",
            "id": 999,
            "method": "any_method",
        }

        response = replayer.handle_request(request)

        assert response == override_response

    def test_override_consumed_on_use(self, simple_recording: VCRRecording):
        """Override is consumed after use."""
        replayer = MCPReplayer(simple_recording)

        override_response = {
            "jsonrpc": "2.0",
            "id": 999,
            "result": {"custom": "response"},
        }

        replayer.set_response_override(999, override_response)

        request = {
            "jsonrpc": "2.0",
            "id": 999,
            "method": "any",
        }

        # First call uses override
        response1 = replayer.handle_request(request)
        assert response1 == override_response

        # Second call no longer uses override (consumed)
        response2 = replayer.handle_request(request)
        assert response2 != override_response

    def test_multiple_overrides(self, simple_recording: VCRRecording):
        """Can set multiple overrides."""
        replayer = MCPReplayer(simple_recording)

        replayer.set_response_override(
            1, {"jsonrpc": "2.0", "id": 1, "result": {"value": 1}}
        )
        replayer.set_response_override(
            2, {"jsonrpc": "2.0", "id": 2, "result": {"value": 2}}
        )

        response1 = replayer.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "any"}
        )
        assert response1["result"]["value"] == 1

        response2 = replayer.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "any"}
        )
        assert response2["result"]["value"] == 2

    def test_clear_response_overrides(self, simple_recording: VCRRecording):
        """Can clear all overrides."""
        replayer = MCPReplayer(simple_recording)

        replayer.set_response_override(
            999, {"jsonrpc": "2.0", "id": 999, "result": {}}
        )

        replayer.clear_response_overrides()

        request = {
            "jsonrpc": "2.0",
            "id": 999,
            "method": "tools/list",
        }

        response = replayer.handle_request(request)

        # Should fall back to normal matching
        assert "error" not in response or "tools" in response.get(
            "result", {}
        )


# ===== Empty and Edge Case Tests =====


class TestMCPReplayerEdgeCases:
    """Tests for edge cases and empty recordings."""

    def test_empty_interactions(self):
        """Replayer with no interactions."""
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
            interactions=[],
        )

        recording = VCRRecording(
            format_version="1.0.0",
            metadata=VCRMetadata(
                version="1.0.0",
                recorded_at=datetime.now(),
                transport="stdio",
            ),
            session=session,
        )

        replayer = MCPReplayer(recording)

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "test",
        }

        response = replayer.handle_request(request)

        assert "error" in response

    def test_request_without_params(self, simple_recording: VCRRecording):
        """Handle request without params field."""
        replayer = MCPReplayer(simple_recording)

        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            # No params field
        }

        response = replayer.handle_request(request)

        assert response["jsonrpc"] == "2.0"

    def test_request_without_id(self, simple_recording: VCRRecording):
        """Handle request without id."""
        replayer = MCPReplayer(simple_recording)

        request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            # No id field
        }

        response = replayer.handle_request(request)

        assert response["jsonrpc"] == "2.0"

    def test_null_params(self, simple_recording: VCRRecording):
        """Handle request with null params."""
        replayer = MCPReplayer(simple_recording)

        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": None,
        }

        response = replayer.handle_request(request)

        assert "result" in response or "error" in response


# ===== Matching Strategy Tests =====


class TestMCPReplayerStrategies:
    """Tests for different matching strategies."""

    def test_method_strategy(self, simple_recording: VCRRecording):
        """Method-only matching strategy."""
        replayer = MCPReplayer(
            simple_recording, match_strategy="method"
        )

        # Request with different params still matches
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"different": "params"},
        }

        response = replayer.handle_request(request)

        # Should find the tools/call interaction
        assert "content" in response.get("result", {})

    def test_exact_strategy(self, simple_recording: VCRRecording):
        """Exact matching strategy."""
        replayer = MCPReplayer(
            simple_recording, match_strategy="exact"
        )

        # Exact match works
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"text": "hello"}},
        }

        response = replayer.handle_request(request)

        assert "content" in response.get("result", {})

    def test_fuzzy_strategy(self, simple_recording: VCRRecording):
        """Fuzzy matching strategy."""
        replayer = MCPReplayer(
            simple_recording, match_strategy="fuzzy"
        )

        # Subset of params matches
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "echo"},
        }

        response = replayer.handle_request(request)

        # Should match the recorded interaction
        assert "content" in response.get("result", {})
