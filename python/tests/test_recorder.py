"""Tests for MCPRecorder."""

import time

import pytest

from agent_vcr.core.format import JSONRPCRequest
from agent_vcr.recorder import MCPRecorder


class TestRecorderPendingEviction:
    """Tests for pending request timeout/eviction."""

    def test_evict_stale_pending_requests_removes_old_entries(self):
        """Stale pending requests are evicted when _evict_stale_pending_requests is called."""
        recorder = MCPRecorder(
            transport="stdio",
            server_command="true",
            server_args=[],
            pending_timeout_seconds=1.0,
        )
        req = JSONRPCRequest(jsonrpc="2.0", id=42, method="test", params={})
        recorder._pending_requests[42] = req
        recorder._pending_request_times[42] = time.time() - 10.0  # 10s ago

        recorder._evict_stale_pending_requests()

        assert 42 not in recorder._pending_requests
        assert 42 not in recorder._pending_request_times

    def test_evict_stale_pending_requests_keeps_recent_entries(self):
        """Recent pending requests are not evicted."""
        recorder = MCPRecorder(
            transport="stdio",
            server_command="true",
            server_args=[],
            pending_timeout_seconds=10.0,
        )
        req = JSONRPCRequest(jsonrpc="2.0", id=1, method="test", params={})
        recorder._pending_requests[1] = req
        recorder._pending_request_times[1] = time.time() - 1.0  # 1s ago

        recorder._evict_stale_pending_requests()

        assert 1 in recorder._pending_requests
        assert 1 in recorder._pending_request_times

