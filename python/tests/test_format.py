"""Tests for VCR format models (JSON-RPC and VCR recording structures)."""

from datetime import datetime
from pathlib import Path

import pytest

from agent_vcr.core.format import (
    JSONRPCError,
    JSONRPCMessage,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
    VCRRecording,
    VCRSession,
)


# ===== JSONRPCMessage Tests =====


class TestJSONRPCMessage:
    """Tests for JSONRPCMessage base class."""

    def test_jsonrpc_version(self):
        """Verify jsonrpc field defaults to 2.0."""
        msg = JSONRPCMessage()
        assert msg.jsonrpc == "2.0"

    def test_extra_fields_allowed(self):
        """Verify extra fields are allowed in messages."""
        msg = JSONRPCMessage(extra_field="value")
        assert msg.extra_field == "value"


# ===== JSONRPCError Tests =====


class TestJSONRPCError:
    """Tests for JSONRPCError objects."""

    def test_error_creation_minimal(self):
        """Create error with code and message only."""
        error = JSONRPCError(code=-32600, message="Invalid Request")
        assert error.code == -32600
        assert error.message == "Invalid Request"
        assert error.data is None

    def test_error_creation_with_data(self):
        """Create error with additional data."""
        error = JSONRPCError(
            code=-32603,
            message="Internal error",
            data={"details": "something went wrong"},
        )
        assert error.code == -32603
        assert error.message == "Internal error"
        assert error.data == {"details": "something went wrong"}

    def test_error_model_dump(self):
        """Verify error can be serialized."""
        error = JSONRPCError(code=-32601, message="Method not found")
        data = error.model_dump()
        assert data["code"] == -32601
        assert data["message"] == "Method not found"


# ===== JSONRPCRequest Tests =====


class TestJSONRPCRequest:
    """Tests for JSONRPCRequest messages."""

    def test_request_minimal(self):
        """Create minimal request with required fields."""
        req = JSONRPCRequest(jsonrpc="2.0", id=1, method="test")
        assert req.jsonrpc == "2.0"
        assert req.id == 1
        assert req.method == "test"
        assert req.params is None

    def test_request_with_dict_params(self):
        """Create request with dict params."""
        req = JSONRPCRequest(
            jsonrpc="2.0",
            id=2,
            method="tools/call",
            params={"name": "echo", "arguments": {"text": "hello"}},
        )
        assert req.params["name"] == "echo"

    def test_request_with_list_params(self):
        """Create request with list params."""
        req = JSONRPCRequest(
            jsonrpc="2.0",
            id=3,
            method="batch_call",
            params=["call1", "call2"],
        )
        assert req.params == ["call1", "call2"]

    def test_request_with_string_id(self):
        """Request can use string IDs."""
        req = JSONRPCRequest(
            jsonrpc="2.0", id="request-abc", method="test"
        )
        assert req.id == "request-abc"

    def test_request_with_float_id(self):
        """Request can use float IDs."""
        req = JSONRPCRequest(jsonrpc="2.0", id=1.5, method="test")
        assert req.id == 1.5

    def test_request_serialization(self):
        """Request can be serialized to dict."""
        req = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="initialize",
            params={"capabilities": {}},
        )
        data = req.model_dump()
        assert data["method"] == "initialize"
        assert data["params"]["capabilities"] == {}


# ===== JSONRPCResponse Tests =====


class TestJSONRPCResponse:
    """Tests for JSONRPCResponse messages."""

    def test_response_with_result(self):
        """Create response with result."""
        resp = JSONRPCResponse(
            jsonrpc="2.0",
            id=1,
            result={"status": "ok"},
        )
        assert resp.id == 1
        assert resp.result == {"status": "ok"}
        assert resp.error is None

    def test_response_with_error(self):
        """Create response with error."""
        resp = JSONRPCResponse(
            jsonrpc="2.0",
            id=2,
            error=JSONRPCError(code=-32603, message="Internal error"),
        )
        assert resp.id == 2
        assert resp.result is None
        assert resp.error.code == -32603

    def test_response_null_result(self):
        """Response can have null result."""
        resp = JSONRPCResponse(jsonrpc="2.0", id=3, result=None)
        assert resp.result is None

    def test_response_serialization(self):
        """Response can be serialized."""
        resp = JSONRPCResponse(
            jsonrpc="2.0",
            id=1,
            result={"tools": []},
        )
        data = resp.model_dump()
        assert data["id"] == 1
        assert data["result"]["tools"] == []


# ===== JSONRPCNotification Tests =====


class TestJSONRPCNotification:
    """Tests for JSONRPCNotification messages."""

    def test_notification_no_id(self):
        """Notification must not have an id field."""
        notif = JSONRPCNotification(
            jsonrpc="2.0",
            method="notification/test",
            params={"key": "value"},
        )
        assert notif.method == "notification/test"
        assert notif.params == {"key": "value"}
        assert not hasattr(notif, "id")

    def test_notification_with_empty_params(self):
        """Notification can have empty params."""
        notif = JSONRPCNotification(
            jsonrpc="2.0",
            method="notification/ping",
        )
        assert notif.method == "notification/ping"
        assert notif.params is None


# ===== VCRInteraction Tests =====


class TestVCRInteraction:
    """Tests for VCRInteraction objects."""

    def test_interaction_creation(self):
        """Create a basic interaction."""
        req = JSONRPCRequest(jsonrpc="2.0", id=1, method="tools/list")
        resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={"tools": []}
        )
        ts = datetime(2024, 1, 15, 10, 30, 1)

        interaction = VCRInteraction(
            sequence=0,
            timestamp=ts,
            direction="client_to_server",
            request=req,
            response=resp,
            latency_ms=50.0,
        )

        assert interaction.sequence == 0
        assert interaction.timestamp == ts
        assert interaction.direction == "client_to_server"
        assert interaction.latency_ms == 50.0

    def test_interaction_with_notifications(self):
        """Interaction can include notifications."""
        req = JSONRPCRequest(jsonrpc="2.0", id=1, method="test")
        resp = JSONRPCResponse(jsonrpc="2.0", id=1, result={})
        notif = JSONRPCNotification(
            jsonrpc="2.0",
            method="progress",
            params={"value": 50},
        )

        interaction = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=req,
            response=resp,
            notifications=[notif],
            latency_ms=25.0,
        )

        assert len(interaction.notifications) == 1
        assert interaction.notifications[0].method == "progress"

    def test_interaction_without_response(self):
        """Interaction without response is valid."""
        req = JSONRPCRequest(jsonrpc="2.0", id=1, method="notification_send")

        interaction = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=req,
            response=None,
            latency_ms=0.0,
        )

        assert interaction.response is None

    def test_interaction_server_to_client(self):
        """Interaction can be server_to_client direction."""
        req = JSONRPCRequest(jsonrpc="2.0", id=1, method="test")
        resp = JSONRPCResponse(jsonrpc="2.0", id=1, result={})

        interaction = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="server_to_client",
            request=req,
            response=resp,
            latency_ms=10.0,
        )

        assert interaction.direction == "server_to_client"


# ===== VCRMetadata Tests =====


class TestVCRMetadata:
    """Tests for VCRMetadata objects."""

    def test_metadata_creation(self):
        """Create metadata with required fields."""
        ts = datetime(2024, 1, 15, 10, 30, 0)
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=ts,
            transport="stdio",
        )

        assert metadata.version == "1.0.0"
        assert metadata.recorded_at == ts
        assert metadata.transport == "stdio"
        assert metadata.client_info == {}
        assert metadata.server_info == {}

    def test_metadata_with_all_fields(self):
        """Create metadata with all optional fields."""
        ts = datetime.now()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=ts,
            transport="sse",
            client_info={"name": "test-client", "version": "1.0"},
            server_info={"name": "test-server", "version": "2.0"},
            server_command="python -m server",
            server_args=["--debug", "--port", "3000"],
            tags={"env": "test", "type": "unit"},
        )

        assert metadata.transport == "sse"
        assert metadata.client_info["name"] == "test-client"
        assert metadata.server_command == "python -m server"
        assert len(metadata.server_args) == 3
        assert metadata.tags["env"] == "test"

    def test_metadata_transport_validation(self):
        """Transport must be stdio or sse."""
        # Valid transports should not raise
        VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="sse",
        )

        # Invalid transport should raise
        with pytest.raises(Exception):
            VCRMetadata(
                version="1.0.0",
                recorded_at=datetime.now(),
                transport="invalid",  # type: ignore
            )


# ===== VCRSession Tests =====


class TestVCRSession:
    """Tests for VCRSession objects."""

    def test_session_creation(self):
        """Create basic session with init messages."""
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={"capabilities": {}}
        )

        session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
        )

        assert session.initialize_request == init_req
        assert session.initialize_response == init_resp
        assert session.interactions == []

    def test_session_with_interactions(self):
        """Session can contain multiple interactions."""
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
                    jsonrpc="2.0", id=2, method="tools/list"
                ),
                response=JSONRPCResponse(
                    jsonrpc="2.0", id=2, result={"tools": []}
                ),
                latency_ms=50.0,
            ),
        ]

        session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
            interactions=interactions,
        )

        assert len(session.interactions) == 1
        assert session.interactions[0].request.method == "tools/list"

    def test_session_with_capabilities(self):
        """Session stores server capabilities."""
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={"capabilities": {}}
        )

        session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
            capabilities={"tools": {}, "resources": {}},
        )

        assert "tools" in session.capabilities
        assert "resources" in session.capabilities


# ===== VCRRecording Tests =====


class TestVCRRecording:
    """Tests for VCRRecording (top-level) objects."""

    def test_recording_creation(self, sample_recording: VCRRecording):
        """Create a complete recording."""
        assert sample_recording.format_version == "1.0.0"
        assert sample_recording.metadata is not None
        assert sample_recording.session is not None

    def test_recording_save_and_load(
        self, sample_recording: VCRRecording, tmp_path: Path
    ):
        """Save recording to file and load it back."""
        vcr_file = tmp_path / "test.vcr"
        sample_recording.save(str(vcr_file))

        assert vcr_file.exists()

        loaded = VCRRecording.load(str(vcr_file))
        assert loaded.format_version == sample_recording.format_version
        assert (
            loaded.session.initialize_request.method
            == sample_recording.session.initialize_request.method
        )

    def test_recording_save_atomic(self, sample_recording: VCRRecording, tmp_path: Path):
        """Save uses atomic write (temp then replace); no .tmp left behind."""
        vcr_file = tmp_path / "session.vcr"
        sample_recording.save(str(vcr_file))

        assert vcr_file.exists()
        tmp_file = tmp_path / "session.vcr.tmp"
        assert not tmp_file.exists(), "atomic save must replace temp; .tmp should not remain"

        loaded = VCRRecording.load(str(vcr_file))
        assert loaded.model_dump(mode="json") == sample_recording.model_dump(mode="json")

    def test_recording_to_json(self, sample_recording: VCRRecording):
        """Convert recording to JSON string."""
        json_str = sample_recording.to_json()
        assert isinstance(json_str, str)
        assert "format_version" in json_str
        assert "metadata" in json_str

    def test_recording_from_json(
        self, sample_recording: VCRRecording
    ):
        """Create recording from JSON string."""
        json_str = sample_recording.to_json()
        loaded = VCRRecording.from_json(json_str)

        assert loaded.format_version == sample_recording.format_version
        assert (
            len(loaded.session.interactions)
            == len(sample_recording.session.interactions)
        )

    def test_recording_add_interaction(
        self, sample_recording: VCRRecording
    ):
        """Add interaction to recording."""
        initial_count = len(sample_recording.session.interactions)

        new_interaction = VCRInteraction(
            sequence=100,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0", id=999, method="new_method"
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0", id=999, result={}
            ),
            latency_ms=10.0,
        )

        sample_recording.add_interaction(new_interaction)

        assert (
            len(sample_recording.session.interactions)
            == initial_count + 1
        )

    def test_recording_duration(
        self, sample_recording: VCRRecording
    ):
        """Calculate duration of recording."""
        duration = sample_recording.duration
        assert isinstance(duration, float)
        assert duration > 0

    def test_recording_empty_duration(self, empty_recording: VCRRecording):
        """Empty recording has zero duration."""
        assert empty_recording.duration == 0.0

    def test_recording_interaction_count(
        self, sample_recording: VCRRecording
    ):
        """Get interaction count."""
        count = sample_recording.interaction_count
        assert count == 3

    def test_recording_empty_interaction_count(
        self, empty_recording: VCRRecording
    ):
        """Empty recording has zero interactions."""
        assert empty_recording.interaction_count == 0

    def test_recording_save_invalid_path(self, sample_recording: VCRRecording):
        """Save to invalid path raises IOError."""
        invalid_path = "/nonexistent/directory/file.vcr"
        with pytest.raises(IOError):
            sample_recording.save(invalid_path)

    def test_recording_load_missing_file(self):
        """Load from missing file raises FileNotFoundError."""
        with pytest.raises(IOError):
            VCRRecording.load("/nonexistent/file.vcr")

    def test_recording_from_json_invalid(self):
        """Invalid JSON raises ValueError."""
        invalid_json = "not valid json"
        with pytest.raises(ValueError):
            VCRRecording.from_json(invalid_json)

    def test_recording_from_json_invalid_format(self):
        """Invalid VCR format raises ValueError."""
        invalid_vcr = '{"key": "value"}'
        with pytest.raises(ValueError):
            VCRRecording.from_json(invalid_vcr)


# ===== Integration Tests =====


class TestVCRRecordingIntegration:
    """Integration tests across multiple format classes."""

    def test_full_round_trip(self, sample_recording: VCRRecording, tmp_path: Path):
        """Full save/load/JSON round trip."""
        # Save to file
        vcr_file = tmp_path / "roundtrip.vcr"
        sample_recording.save(str(vcr_file))

        # Load from file
        loaded_file = VCRRecording.load(str(vcr_file))

        # Convert to JSON and back
        json_str = loaded_file.to_json()
        loaded_json = VCRRecording.from_json(json_str)

        # Verify structure is preserved
        assert (
            loaded_json.session.initialize_request.method
            == sample_recording.session.initialize_request.method
        )
        assert (
            len(loaded_json.session.interactions)
            == len(sample_recording.session.interactions)
        )
        assert loaded_json.metadata.transport == sample_recording.metadata.transport
