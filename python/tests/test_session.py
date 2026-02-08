"""Tests for SessionManager lifecycle and state management."""

import asyncio
from datetime import datetime

import pytest

from agent_vcr.core.format import (
    JSONRPCError,
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
)
from agent_vcr.core.session import SessionManager


# ===== SessionManager Initialization Tests =====


class TestSessionManagerInit:
    """Tests for SessionManager initialization."""

    def test_init_idle_state(self):
        """SessionManager starts in idle state."""
        manager = SessionManager()
        assert manager.current_state == "idle"
        assert not manager.is_recording
        assert not manager.is_replaying

    def test_init_no_recording(self):
        """New manager has no current recording."""
        manager = SessionManager()
        assert manager.current_recording is None

    def test_init_zero_interactions(self):
        """New manager reports zero interactions."""
        manager = SessionManager()
        assert manager.get_interaction_count() == 0

    def test_init_zero_duration(self):
        """New manager reports zero duration."""
        manager = SessionManager()
        assert manager.get_recorded_duration() == 0.0


# ===== Recording Lifecycle Tests =====


class TestSessionManagerRecordingLifecycle:
    """Tests for start/stop recording lifecycle."""

    def test_start_recording(self):
        """Start recording transitions to recording state."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={"capabilities": {}}
        )

        manager.start_recording(metadata, init_req, init_resp)

        assert manager.current_state == "recording"
        assert manager.is_recording
        assert manager.current_recording is not None

    def test_start_recording_sets_recording(self):
        """Recording object is created on start."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime(2024, 1, 15, 10, 30),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={"capabilities": {}}
        )

        manager.start_recording(metadata, init_req, init_resp)

        recording = manager.current_recording
        assert recording is not None
        assert recording.metadata == metadata
        assert recording.session.initialize_request == init_req

    def test_start_recording_extracts_capabilities(self):
        """Capabilities extracted from response if not provided."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0",
            id=1,
            result={"capabilities": {"tools": {}, "resources": {}}},
        )

        manager.start_recording(metadata, init_req, init_resp)

        recording = manager.current_recording
        assert recording is not None
        assert "tools" in recording.session.capabilities
        assert "resources" in recording.session.capabilities

    def test_start_recording_with_explicit_capabilities(self):
        """Explicit capabilities override response extraction."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0",
            id=1,
            result={"capabilities": {"tools": {}}},
        )

        explicit_caps = {"logging": {}}
        manager.start_recording(
            metadata, init_req, init_resp, capabilities=explicit_caps
        )

        recording = manager.current_recording
        assert recording is not None
        assert recording.session.capabilities == explicit_caps

    def test_start_recording_already_recording(self):
        """Cannot start recording if already recording."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        manager.start_recording(metadata, init_req, init_resp)

        with pytest.raises(RuntimeError, match="Already recording"):
            manager.start_recording(metadata, init_req, init_resp)

    def test_stop_recording(self):
        """Stop recording transitions to idle state."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        manager.start_recording(metadata, init_req, init_resp)
        recording = manager.stop_recording()

        assert manager.current_state == "idle"
        assert not manager.is_recording
        assert manager.current_recording is None
        assert recording is not None

    def test_stop_recording_not_recording(self):
        """Cannot stop recording if not recording."""
        manager = SessionManager()

        with pytest.raises(RuntimeError, match="Not recording"):
            manager.stop_recording()

    def test_stop_recording_returns_recording(self):
        """Stop recording returns the completed recording."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        manager.start_recording(metadata, init_req, init_resp)
        recording = manager.stop_recording()

        assert recording.metadata == metadata
        assert recording.format_version == "1.0.0"


# ===== Interaction Recording Tests =====


class TestSessionManagerRecordInteraction:
    """Tests for recording individual interactions."""

    def _setup_recording(self, manager: SessionManager) -> None:
        """Helper to set up a recording session."""
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )
        manager.start_recording(metadata, init_req, init_resp)

    def test_record_interaction_basic(self):
        """Record a basic request/response interaction."""
        manager = SessionManager()
        self._setup_recording(manager)

        req = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="tools/list"
        )
        resp = JSONRPCResponse(
            jsonrpc="2.0", id=2, result={"tools": []}
        )

        interaction = manager.record_interaction(req, resp)

        assert interaction.sequence == 0
        assert interaction.request == req
        assert interaction.response == resp
        assert interaction.direction == "server_to_client"

    def test_record_interaction_increments_sequence(self):
        """Each interaction gets incremented sequence number."""
        manager = SessionManager()
        self._setup_recording(manager)

        for i in range(3):
            req = JSONRPCRequest(
                jsonrpc="2.0", id=i + 2, method="test"
            )
            resp = JSONRPCResponse(
                jsonrpc="2.0", id=i + 2, result={}
            )
            interaction = manager.record_interaction(req, resp)
            assert interaction.sequence == i

    def test_record_interaction_sets_direction(self):
        """Direction set to server_to_client if response provided."""
        manager = SessionManager()
        self._setup_recording(manager)

        req = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="test"
        )
        resp = JSONRPCResponse(
            jsonrpc="2.0", id=2, result={}
        )

        interaction = manager.record_interaction(req, resp)
        assert interaction.direction == "server_to_client"

    def test_record_interaction_no_response_direction(self):
        """Direction set to client_to_server if no response."""
        manager = SessionManager()
        self._setup_recording(manager)

        req = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="notification"
        )

        interaction = manager.record_interaction(req, None)
        assert interaction.direction == "client_to_server"

    def test_record_interaction_with_notifications(self):
        """Record interaction with notifications."""
        manager = SessionManager()
        self._setup_recording(manager)

        req = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="test"
        )
        resp = JSONRPCResponse(
            jsonrpc="2.0", id=2, result={}
        )
        notif = JSONRPCNotification(
            jsonrpc="2.0",
            method="progress",
            params={"value": 50},
        )

        interaction = manager.record_interaction(req, resp, [notif])

        assert len(interaction.notifications) == 1
        assert interaction.notifications[0].method == "progress"

    def test_record_interaction_latency_calculation(self):
        """Latency calculated between requests."""
        manager = SessionManager()
        self._setup_recording(manager)

        req1 = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="test"
        )
        resp1 = JSONRPCResponse(
            jsonrpc="2.0", id=2, result={}
        )

        # First interaction has zero latency (no previous request)
        interaction1 = manager.record_interaction(req1, resp1)
        assert interaction1.latency_ms == 0.0

        # Small delay before second interaction
        import time
        time.sleep(0.01)  # 10ms

        req2 = JSONRPCRequest(
            jsonrpc="2.0", id=3, method="test"
        )
        resp2 = JSONRPCResponse(
            jsonrpc="2.0", id=3, result={}
        )

        interaction2 = manager.record_interaction(req2, resp2)
        # Latency should be > 10ms
        assert interaction2.latency_ms > 5.0

    def test_record_interaction_not_recording(self):
        """Cannot record interaction if not recording."""
        manager = SessionManager()

        req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="test"
        )
        resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        with pytest.raises(RuntimeError, match="Not recording"):
            manager.record_interaction(req, resp)

    def test_record_interaction_invalid_notifications(self):
        """Notifications must be a list."""
        manager = SessionManager()
        self._setup_recording(manager)

        req = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="test"
        )
        resp = JSONRPCResponse(
            jsonrpc="2.0", id=2, result={}
        )

        with pytest.raises(ValueError, match="notifications must be a list"):
            manager.record_interaction(req, resp, "not a list")  # type: ignore

    def test_record_interaction_adds_to_recording(self):
        """Recorded interactions added to session."""
        manager = SessionManager()
        self._setup_recording(manager)

        req = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="test"
        )
        resp = JSONRPCResponse(
            jsonrpc="2.0", id=2, result={}
        )

        manager.record_interaction(req, resp)

        assert manager.get_interaction_count() == 1

        manager.record_interaction(req, resp)

        assert manager.get_interaction_count() == 2


# ===== Async Interaction Recording Tests =====


class TestSessionManagerAsyncRecordInteraction:
    """Tests for async interaction recording."""

    def _setup_recording(self, manager: SessionManager) -> None:
        """Helper to set up a recording session."""
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )
        manager.start_recording(metadata, init_req, init_resp)

    @pytest.mark.asyncio
    async def test_record_interaction_async(self):
        """Record interaction asynchronously."""
        manager = SessionManager()
        self._setup_recording(manager)

        req = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="test"
        )
        resp = JSONRPCResponse(
            jsonrpc="2.0", id=2, result={}
        )

        interaction = await manager.record_interaction_async(req, resp)

        assert interaction.sequence == 0
        assert interaction.request == req

    @pytest.mark.asyncio
    async def test_record_interaction_async_not_recording(self):
        """Cannot record async interaction if not recording."""
        manager = SessionManager()

        req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="test"
        )
        resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        with pytest.raises(RuntimeError):
            await manager.record_interaction_async(req, resp)


# ===== State Query Tests =====


class TestSessionManagerStateQueries:
    """Tests for state queries and counters."""

    def test_get_interaction_count_idle(self):
        """Interaction count zero when idle."""
        manager = SessionManager()
        assert manager.get_interaction_count() == 0

    def test_get_interaction_count_recording(self):
        """Interaction count reflects recorded interactions."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        manager.start_recording(metadata, init_req, init_resp)

        for i in range(3):
            req = JSONRPCRequest(
                jsonrpc="2.0", id=i + 2, method="test"
            )
            resp = JSONRPCResponse(
                jsonrpc="2.0", id=i + 2, result={}
            )
            manager.record_interaction(req, resp)

        assert manager.get_interaction_count() == 3

    def test_get_recorded_duration_empty(self):
        """Duration zero for empty recording."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        manager.start_recording(metadata, init_req, init_resp)

        assert manager.get_recorded_duration() == 0.0

    def test_get_recorded_duration_with_interactions(self):
        """Duration calculated correctly with interactions."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        manager.start_recording(metadata, init_req, init_resp)

        # Record interaction at t=0
        req1 = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="test1"
        )
        resp1 = JSONRPCResponse(
            jsonrpc="2.0", id=2, result={}
        )
        manager.record_interaction(req1, resp1)

        # Small delay
        import time
        time.sleep(0.02)

        # Record interaction at t=20ms
        req2 = JSONRPCRequest(
            jsonrpc="2.0", id=3, method="test2"
        )
        resp2 = JSONRPCResponse(
            jsonrpc="2.0", id=3, result={}
        )
        manager.record_interaction(req2, resp2)

        duration = manager.get_recorded_duration()
        assert duration > 0.01  # At least 10ms


# ===== Reset Tests =====


class TestSessionManagerReset:
    """Tests for reset functionality."""

    def test_reset_from_recording(self):
        """Reset from recording state returns to idle."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        manager.start_recording(metadata, init_req, init_resp)
        manager.reset()

        assert manager.current_state == "idle"
        assert manager.current_recording is None

    def test_reset_clears_recording(self):
        """Reset discards current recording."""
        manager = SessionManager()
        metadata = VCRMetadata(
            version="1.0.0",
            recorded_at=datetime.now(),
            transport="stdio",
        )
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        manager.start_recording(metadata, init_req, init_resp)

        for i in range(3):
            req = JSONRPCRequest(
                jsonrpc="2.0", id=i + 2, method="test"
            )
            resp = JSONRPCResponse(
                jsonrpc="2.0", id=i + 2, result={}
            )
            manager.record_interaction(req, resp)

        manager.reset()

        assert manager.get_interaction_count() == 0
        assert manager.get_recorded_duration() == 0.0

    def test_reset_idempotent(self):
        """Reset can be called multiple times safely."""
        manager = SessionManager()
        manager.reset()
        manager.reset()

        assert manager.current_state == "idle"
