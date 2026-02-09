"""Tests for enhanced replayer: latency simulation, notification replay."""

import asyncio
import time
from datetime import datetime

import pytest

from agent_vcr.core.format import (
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
    VCRRecording,
    VCRSession,
)
from agent_vcr.replayer import MCPReplayer


# ===== Helpers =====


def _make_interaction(
    method: str,
    params=None,
    result=None,
    seq: int = 0,
    latency: float = 50.0,
    notifications=None,
) -> VCRInteraction:
    return VCRInteraction(
        sequence=seq,
        timestamp=datetime(2024, 1, 15, 10, 30, seq),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0", id=seq + 1, method=method, params=params
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0", id=seq + 1, result=result or {"ok": True}
        ),
        notifications=notifications or [],
        latency_ms=latency,
    )


def _make_recording(interactions: list[VCRInteraction]) -> VCRRecording:
    return VCRRecording(
        format_version="1.0.0",
        metadata=VCRMetadata(
            version="1.0.0",
            recorded_at=datetime(2024, 1, 15, 10, 30, 0),
            transport="stdio",
            client_info={"name": "test", "version": "1.0"},
            server_info={"name": "server", "version": "1.0"},
        ),
        session=VCRSession(
            initialize_request=JSONRPCRequest(
                jsonrpc="2.0", id=0, method="initialize", params={}
            ),
            initialize_response=JSONRPCResponse(
                jsonrpc="2.0", id=0, result={"protocolVersion": "2024-11-05"}
            ),
            capabilities={},
            interactions=interactions,
        ),
    )


# ===== Latency simulation tests =====


class TestLatencySimulation:
    """Tests for replayer latency simulation feature."""

    def test_replayer_accepts_latency_params(self):
        recording = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0, latency=100.0),
        ])
        replayer = MCPReplayer(
            recording,
            simulate_latency=True,
            latency_multiplier=0.5,
        )
        assert replayer.simulate_latency is True
        assert replayer.latency_multiplier == 0.5

    def test_latency_defaults_off(self):
        recording = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0),
        ])
        replayer = MCPReplayer(recording)
        assert replayer.simulate_latency is False
        assert replayer.latency_multiplier == 1.0

    @pytest.mark.asyncio
    async     def test_handle_request_async_with_latency(self):
        """handle_request_async should delay when simulate_latency=True."""
        recording = _make_recording([
            _make_interaction("tools/list", params={}, result={"tools": []}, seq=0, latency=200.0),
        ])
        replayer = MCPReplayer(
            recording,
            simulate_latency=True,
            latency_multiplier=1.0,
        )

        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        start = time.monotonic()
        response = await replayer.handle_request_async(request)
        elapsed = time.monotonic() - start

        assert response is not None
        # Should have waited ~200ms (allow some tolerance)
        assert elapsed >= 0.15, f"Expected >=150ms delay, got {elapsed*1000:.0f}ms"

    @pytest.mark.asyncio
    async     def test_handle_request_async_with_multiplier(self):
        """Latency multiplier scales the delay."""
        recording = _make_recording([
            _make_interaction("tools/list", params={}, result={"tools": []}, seq=0, latency=400.0),
        ])
        replayer = MCPReplayer(
            recording,
            simulate_latency=True,
            latency_multiplier=0.25,  # 400ms * 0.25 = 100ms
        )

        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        start = time.monotonic()
        response = await replayer.handle_request_async(request)
        elapsed = time.monotonic() - start

        assert response is not None
        # 400 * 0.25 = 100ms, allow tolerance
        assert elapsed >= 0.07, f"Expected >=70ms delay, got {elapsed*1000:.0f}ms"
        assert elapsed < 0.35, f"Expected <350ms, got {elapsed*1000:.0f}ms (multiplier not applied?)"

    @pytest.mark.asyncio
    async def test_handle_request_async_no_latency(self):
        """Without simulate_latency, response should be near-instant."""
        recording = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0, latency=5000.0),
        ])
        replayer = MCPReplayer(
            recording,
            simulate_latency=False,
        )

        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        start = time.monotonic()
        response = await replayer.handle_request_async(request)
        elapsed = time.monotonic() - start

        assert response is not None
        # Should be nearly instant, definitely less than 1 second
        assert elapsed < 1.0, f"Expected instant, got {elapsed*1000:.0f}ms"

    def test_handle_request_sync_still_works(self):
        """Sync handle_request should still work without latency."""
        recording = _make_recording([
            _make_interaction("tools/list", params={}, result={"tools": []}, seq=0),
        ])
        replayer = MCPReplayer(recording)

        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        response = replayer.handle_request(request)
        assert response is not None
        assert "result" in response


# ===== Notification replay tests =====


class TestNotificationReplay:
    """Tests for notification retrieval from replayer."""

    def test_get_notifications_for_request(self):
        """get_notifications_for_request returns stored notifications."""
        notifications = [
            JSONRPCNotification(
                jsonrpc="2.0",
                method="notifications/progress",
                params={"progressToken": "t1", "progress": 50, "total": 100},
            ),
            JSONRPCNotification(
                jsonrpc="2.0",
                method="notifications/progress",
                params={"progressToken": "t1", "progress": 100, "total": 100},
            ),
        ]
        recording = _make_recording([
            _make_interaction(
                "tools/call",
                params={"name": "slow_tool"},
                result={"content": []},
                seq=0,
                notifications=notifications,
            ),
        ])
        replayer = MCPReplayer(recording)

        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "slow_tool"}}
        notifs = replayer.get_notifications_for_request(request)
        assert len(notifs) == 2
        assert notifs[0]["method"] == "notifications/progress"
        assert notifs[1]["params"]["progress"] == 100

    def test_no_notifications_returns_empty(self):
        """Request with no notifications returns empty list."""
        recording = _make_recording([
            _make_interaction("tools/list", params={}, result={"tools": []}, seq=0),
        ])
        replayer = MCPReplayer(recording)

        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        notifs = replayer.get_notifications_for_request(request)
        assert notifs == []

    def test_notifications_match_correct_interaction(self):
        """Notifications are associated with the right interaction."""
        notifs_a = [
            JSONRPCNotification(
                jsonrpc="2.0", method="notifications/progress",
                params={"progressToken": "a", "progress": 100, "total": 100},
            ),
        ]
        notifs_b = [
            JSONRPCNotification(
                jsonrpc="2.0", method="notifications/resources/updated",
                params={"uri": "file:///tmp/data.txt"},
            ),
        ]
        recording = _make_recording([
            _make_interaction(
                "tools/call", params={"name": "tool_a"}, result={"ok": True},
                seq=0, notifications=notifs_a,
            ),
            _make_interaction(
                "tools/call", params={"name": "tool_b"}, result={"ok": True},
                seq=1, notifications=notifs_b,
            ),
        ])
        replayer = MCPReplayer(recording)

        req_a = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "tool_a"}}
        req_b = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "tool_b"}}

        notifs_for_a = replayer.get_notifications_for_request(req_a)
        notifs_for_b = replayer.get_notifications_for_request(req_b)

        assert len(notifs_for_a) == 1
        assert notifs_for_a[0]["params"]["progressToken"] == "a"

        assert len(notifs_for_b) == 1
        assert notifs_for_b[0]["method"] == "notifications/resources/updated"


# ===== SSE replayer configuration tests =====


class TestSSEReplayerConfig:
    """Tests for SSE replay configuration (no actual HTTP needed)."""

    def test_replayer_has_sse_clients_list(self):
        recording = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0),
        ])
        replayer = MCPReplayer(recording)
        assert hasattr(replayer, "_sse_clients")
        assert isinstance(replayer._sse_clients, list)
        assert len(replayer._sse_clients) == 0

    def test_replayer_match_strategy_passed_through(self):
        recording = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0),
        ])
        replayer = MCPReplayer(recording, match_strategy="method")
        assert replayer._matcher.strategy == "method"

    def test_replayer_fuzzy_strategy_resolves(self):
        recording = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0),
        ])
        replayer = MCPReplayer(recording, match_strategy="fuzzy")
        assert replayer._matcher.strategy == "subset"
