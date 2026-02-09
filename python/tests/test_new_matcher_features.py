"""Tests for enhanced matcher: thread safety, usage tracking, subset rename."""

import threading
from datetime import datetime
from typing import List

import pytest

from agent_vcr.core.format import (
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
)
from agent_vcr.core.matcher import RequestMatcher, _STRATEGY_ALIASES


# ===== Helpers =====


def _make_interaction(
    method: str, params=None, result=None, seq: int = 0
) -> VCRInteraction:
    return VCRInteraction(
        sequence=seq,
        timestamp=datetime(2024, 1, 15, 10, 30, seq % 60),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0", id=seq + 1, method=method, params=params
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0", id=seq + 1, result=result or {"ok": True}
        ),
        notifications=[],
        latency_ms=50.0,
    )


def _make_request(method: str, params=None) -> JSONRPCRequest:
    return JSONRPCRequest(jsonrpc="2.0", id=99, method=method, params=params)


# ===== Fuzzy → Subset alias tests =====


class TestSubsetAlias:
    """Verify the fuzzy → subset backward-compatible rename."""

    def test_fuzzy_alias_resolves_to_subset(self):
        matcher = RequestMatcher(strategy="fuzzy")
        assert matcher.strategy == "subset"

    def test_subset_strategy_accepted(self):
        matcher = RequestMatcher(strategy="subset")
        assert matcher.strategy == "subset"

    def test_alias_dict_contains_fuzzy(self):
        assert "fuzzy" in _STRATEGY_ALIASES
        assert _STRATEGY_ALIASES["fuzzy"] == "subset"

    def test_fuzzy_matching_works_with_alias(self):
        """Fuzzy alias should use subset matching logic."""
        matcher = RequestMatcher(strategy="fuzzy")
        interactions = [
            _make_interaction("tools/call", params={"name": "echo", "args": {"x": 1}}, seq=0),
        ]
        # Subset: request params are a subset of recorded params
        req = _make_request("tools/call", params={"name": "echo"})
        matches = matcher.find_all_matches(req, interactions)
        assert len(matches) == 1

    def test_subset_matching_rejects_superset_request(self):
        """Request with extra params should NOT match recorded interaction."""
        matcher = RequestMatcher(strategy="subset")
        interactions = [
            _make_interaction("tools/call", params={"name": "echo"}, seq=0),
        ]
        req = _make_request("tools/call", params={"name": "echo", "extra": True})
        matches = matcher.find_all_matches(req, interactions)
        assert len(matches) == 0


# ===== Concurrent usage tracking tests =====


class TestConcurrentUsageTracking:
    """Tests for duplicate request handling via usage counts."""

    def test_duplicate_requests_get_different_responses(self):
        """Two identical requests should get different interactions when available."""
        matcher = RequestMatcher(strategy="method_and_params")
        interactions = [
            _make_interaction("tools/list", params={}, result={"tools": ["a"]}, seq=0),
            _make_interaction("tools/list", params={}, result={"tools": ["b"]}, seq=1),
        ]
        req = _make_request("tools/list", params={})

        first = matcher.find_match(req, interactions)
        second = matcher.find_match(req, interactions)

        assert first is not None
        assert second is not None
        # They should be different interactions
        assert first.sequence != second.sequence

    def test_third_duplicate_cycles_back(self):
        """When all interactions are used equally, cycle back to least-used."""
        matcher = RequestMatcher(strategy="method_and_params")
        interactions = [
            _make_interaction("tools/list", params={}, result={"tools": ["a"]}, seq=0),
            _make_interaction("tools/list", params={}, result={"tools": ["b"]}, seq=1),
        ]
        req = _make_request("tools/list", params={})

        r1 = matcher.find_match(req, interactions)
        r2 = matcher.find_match(req, interactions)
        r3 = matcher.find_match(req, interactions)

        assert r1 is not None and r2 is not None and r3 is not None
        # r3 should cycle back to same as r1 (both used once, picks first min)
        assert r3.sequence == r1.sequence

    def test_single_match_always_returns_same(self):
        """With only one matching interaction, always returns it."""
        matcher = RequestMatcher(strategy="method_and_params")
        interactions = [
            _make_interaction("tools/list", params={}, seq=0),
        ]
        req = _make_request("tools/list", params={})

        r1 = matcher.find_match(req, interactions)
        r2 = matcher.find_match(req, interactions)

        assert r1 is not None and r2 is not None
        assert r1.sequence == r2.sequence

    def test_usage_tracking_reset(self):
        """reset() clears usage counts."""
        matcher = RequestMatcher(strategy="method_and_params")
        interactions = [
            _make_interaction("tools/list", params={}, result={"tools": ["a"]}, seq=0),
            _make_interaction("tools/list", params={}, result={"tools": ["b"]}, seq=1),
        ]
        req = _make_request("tools/list", params={})

        first_before = matcher.find_match(req, interactions)
        matcher.reset()
        first_after = matcher.find_match(req, interactions)

        # After reset, should start fresh — same first pick
        assert first_before is not None and first_after is not None
        assert first_before.sequence == first_after.sequence


# ===== Thread safety tests =====


class TestThreadSafety:
    """Tests for thread-safe matcher operations."""

    def test_sequential_thread_safety(self):
        """Sequential strategy should be safe under concurrent access."""
        matcher = RequestMatcher(strategy="sequential")
        interactions = [
            _make_interaction(f"method_{i}", seq=i) for i in range(100)
        ]

        results: list[VCRInteraction] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker():
            try:
                for _ in range(10):
                    req = _make_request("any")
                    match = matcher.find_match(req, interactions)
                    if match:
                        with lock:
                            results.append(match)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        # All 100 interactions should be consumed exactly once
        assert len(results) == 100
        sequences = sorted(r.sequence for r in results)
        assert sequences == list(range(100))

    def test_concurrent_find_match_no_crashes(self):
        """find_match with usage tracking should not crash under concurrency."""
        matcher = RequestMatcher(strategy="method_and_params")
        interactions = [
            _make_interaction("tools/list", params={}, seq=i) for i in range(5)
        ]

        results: list[VCRInteraction] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker():
            try:
                for _ in range(20):
                    req = _make_request("tools/list", params={})
                    match = matcher.find_match(req, interactions)
                    if match:
                        with lock:
                            results.append(match)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        # All 200 requests should have gotten a match
        assert len(results) == 200


# ===== Reset method tests =====


class TestReset:
    """Tests for reset() method."""

    def test_reset_clears_sequential_index(self):
        matcher = RequestMatcher(strategy="sequential")
        interactions = [_make_interaction(f"m{i}", seq=i) for i in range(5)]
        req = _make_request("any")

        # Use up some interactions
        matcher.find_match(req, interactions)
        matcher.find_match(req, interactions)

        matcher.reset()

        # After reset, should start from beginning
        result = matcher.find_match(req, interactions)
        assert result is not None
        assert result.sequence == 0

    def test_reset_clears_usage_counts(self):
        matcher = RequestMatcher(strategy="method")
        interactions = [
            _make_interaction("tools/list", seq=0),
            _make_interaction("tools/list", seq=1),
        ]
        req = _make_request("tools/list")

        # Use first interaction
        r1 = matcher.find_match(req, interactions)

        matcher.reset()

        # After reset, usage counts cleared — should pick same as first time
        r2 = matcher.find_match(req, interactions)
        assert r1 is not None and r2 is not None
        assert r1.sequence == r2.sequence

    def test_reset_sequential_index_alias(self):
        """reset_sequential_index() should work as alias for reset()."""
        matcher = RequestMatcher(strategy="sequential")
        interactions = [_make_interaction(f"m{i}", seq=i) for i in range(3)]
        req = _make_request("any")

        matcher.find_match(req, interactions)
        matcher.find_match(req, interactions)

        matcher.reset_sequential_index()

        result = matcher.find_match(req, interactions)
        assert result is not None
        assert result.sequence == 0
