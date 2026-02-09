"""Tests for enhanced diff engine: deep compatibility, type checks, latency comparison."""

from datetime import datetime

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
from agent_vcr.diff import MCPDiff, ModifiedInteraction


# ===== Helpers =====

def _make_interaction(
    method: str,
    params=None,
    result=None,
    error=None,
    seq: int = 0,
    latency: float = 50.0,
) -> VCRInteraction:
    response = JSONRPCResponse(
        jsonrpc="2.0",
        id=seq + 1,
        result=result,
        error=error,
    )
    return VCRInteraction(
        sequence=seq,
        timestamp=datetime(2024, 1, 15, 10, 30, seq),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0", id=seq + 1, method=method, params=params
        ),
        response=response,
        notifications=[],
        latency_ms=latency,
    )


def _modified_from_interactions(
    baseline: VCRInteraction, current: VCRInteraction
) -> ModifiedInteraction:
    """Build ModifiedInteraction from two VCRInteractions (same API as MCPDiff._diff_interactions)."""
    def req_dict(i: VCRInteraction) -> dict:
        if not i.request:
            return {}
        return {"method": i.request.method, "params": i.request.params}

    def resp_dict(i: VCRInteraction) -> dict:
        if not i.response:
            return {}
        d = {}
        if i.response.result is not None:
            d["result"] = i.response.result
        if i.response.error is not None:
            err = i.response.error
            d["error"] = err.model_dump(exclude_none=True) if hasattr(err, "model_dump") else {"code": getattr(err, "code", None), "message": getattr(err, "message", None)}
        return d

    return ModifiedInteraction(
        method=baseline.request.method if baseline.request else "unknown",
        baseline_request=req_dict(baseline),
        current_request=req_dict(current),
        baseline_response=resp_dict(baseline),
        current_response=resp_dict(current),
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


# ===== Deep field compatibility tests =====


class TestCheckFieldsCompatible:
    """Tests for ModifiedInteraction._check_fields_compatible()."""

    def test_identical_dicts_compatible(self):
        assert ModifiedInteraction._check_fields_compatible(
            {"a": 1, "b": "hello"}, {"a": 1, "b": "hello"}
        ) is True

    def test_added_field_is_compatible(self):
        """Adding a new field is non-breaking."""
        assert ModifiedInteraction._check_fields_compatible(
            {"a": 1}, {"a": 1, "b": 2}
        ) is True

    def test_removed_field_is_breaking(self):
        """Removing a field that existed in baseline is breaking."""
        assert ModifiedInteraction._check_fields_compatible(
            {"a": 1, "b": 2}, {"a": 1}
        ) is False

    def test_type_change_int_to_string_is_breaking(self):
        """Changing a field's type is breaking."""
        assert ModifiedInteraction._check_fields_compatible(
            {"count": 42}, {"count": "42"}
        ) is False

    def test_type_change_string_to_int_is_breaking(self):
        assert ModifiedInteraction._check_fields_compatible(
            {"count": "42"}, {"count": 42}
        ) is False

    def test_type_change_dict_to_list_is_breaking(self):
        assert ModifiedInteraction._check_fields_compatible(
            {"data": {"key": "val"}}, {"data": [1, 2, 3]}
        ) is False

    def test_none_to_value_is_compatible(self):
        """None in baseline, non-None in current — type check is skipped."""
        assert ModifiedInteraction._check_fields_compatible(
            {"x": None}, {"x": 42}
        ) is True

    def test_value_to_none_is_compatible(self):
        """Non-None in baseline, None in current — type check is skipped."""
        assert ModifiedInteraction._check_fields_compatible(
            {"x": 42}, {"x": None}
        ) is True

    def test_nested_dict_compatible(self):
        """Nested dicts are checked recursively."""
        assert ModifiedInteraction._check_fields_compatible(
            {"outer": {"inner": 1, "deep": {"leaf": "a"}}},
            {"outer": {"inner": 1, "deep": {"leaf": "a"}, "extra": True}},
        ) is True

    def test_nested_dict_removed_field_breaking(self):
        """Removing a nested field is breaking."""
        assert ModifiedInteraction._check_fields_compatible(
            {"outer": {"inner": 1, "deep": {"leaf": "a"}}},
            {"outer": {"inner": 1, "deep": {}}},
        ) is False

    def test_nested_type_change_is_breaking(self):
        """Type change in nested dict is breaking."""
        assert ModifiedInteraction._check_fields_compatible(
            {"outer": {"count": 42}},
            {"outer": {"count": "forty-two"}},
        ) is False

    def test_empty_dicts_compatible(self):
        assert ModifiedInteraction._check_fields_compatible({}, {}) is True

    def test_empty_baseline_always_compatible(self):
        """Empty baseline means nothing can be removed."""
        assert ModifiedInteraction._check_fields_compatible(
            {}, {"a": 1, "b": 2}
        ) is True


# ===== Error code compatibility tests =====


class TestErrorCodeCompatibility:
    """Tests for error code changes in is_compatible."""

    def test_same_error_code_compatible(self):
        baseline = _make_interaction(
            "tools/call", params={"name": "x"}, seq=0,
            error=JSONRPCError(code=-32601, message="Not found"),
        )
        current = _make_interaction(
            "tools/call", params={"name": "x"}, seq=0,
            error=JSONRPCError(code=-32601, message="Not found — updated msg"),
        )
        mod = _modified_from_interactions(baseline, current)
        assert mod.is_compatible is True

    def test_different_error_code_is_breaking(self):
        baseline = _make_interaction(
            "tools/call", params={"name": "x"}, seq=0,
            error=JSONRPCError(code=-32601, message="Not found"),
        )
        current = _make_interaction(
            "tools/call", params={"name": "x"}, seq=0,
            error=JSONRPCError(code=-32603, message="Internal error"),
        )
        mod = _modified_from_interactions(baseline, current)
        assert mod.is_compatible is False

    def test_success_to_error_is_breaking(self):
        baseline = _make_interaction(
            "tools/call", params={"name": "x"}, seq=0,
            result={"content": []},
        )
        current = _make_interaction(
            "tools/call", params={"name": "x"}, seq=0,
            error=JSONRPCError(code=-32601, message="Not found"),
        )
        mod = _modified_from_interactions(baseline, current)
        assert mod.is_compatible is False

    def test_error_to_success_is_breaking(self):
        baseline = _make_interaction(
            "tools/call", params={"name": "x"}, seq=0,
            error=JSONRPCError(code=-32601, message="Not found"),
        )
        current = _make_interaction(
            "tools/call", params={"name": "x"}, seq=0,
            result={"content": []},
        )
        mod = _modified_from_interactions(baseline, current)
        assert mod.is_compatible is False


# ===== Deep is_compatible integration tests =====


class TestDeepIsCompatible:
    """Tests for enhanced is_compatible with field-level checking."""

    def test_added_result_field_is_compatible(self):
        baseline = _make_interaction(
            "tools/list", result={"tools": [{"name": "echo"}]}, seq=0
        )
        current = _make_interaction(
            "tools/list",
            result={"tools": [{"name": "echo"}], "nextCursor": "abc"},
            seq=0,
        )
        mod = _modified_from_interactions(baseline, current)
        assert mod.is_compatible is True

    def test_removed_result_field_is_breaking(self):
        baseline = _make_interaction(
            "tools/list",
            result={"tools": [{"name": "echo"}], "nextCursor": "abc"},
            seq=0,
        )
        current = _make_interaction(
            "tools/list", result={"tools": [{"name": "echo"}]}, seq=0
        )
        mod = _modified_from_interactions(baseline, current)
        assert mod.is_compatible is False

    def test_type_change_in_result_is_breaking(self):
        baseline = _make_interaction(
            "tools/list", result={"count": 5}, seq=0
        )
        current = _make_interaction(
            "tools/list", result={"count": "five"}, seq=0
        )
        mod = _modified_from_interactions(baseline, current)
        assert mod.is_compatible is False


# ===== Latency comparison tests =====


class TestLatencyComparison:
    """Tests for MCPDiff.compare() with compare_latency=True."""

    def test_no_latency_regression(self):
        baseline_int = _make_interaction("tools/list", result={"tools": []}, seq=0, latency=100.0)
        current_int = _make_interaction("tools/list", result={"tools": []}, seq=0, latency=120.0)
        baseline_rec = _make_recording([baseline_int])
        current_rec = _make_recording([current_int])

        diff = MCPDiff.compare(baseline_rec, current_rec, compare_latency=True)
        # 120ms vs 100ms is only 1.2x — below default 2x threshold
        for mod in diff.modified_interactions:
            assert mod.is_compatible is True

    def test_latency_regression_detected(self):
        baseline_int = _make_interaction("tools/list", result={"tools": []}, seq=0, latency=100.0)
        current_int = _make_interaction("tools/list", result={"tools": []}, seq=0, latency=800.0)
        baseline_rec = _make_recording([baseline_int])
        current_rec = _make_recording([current_int])

        diff = MCPDiff.compare(
            baseline_rec, current_rec,
            compare_latency=True,
            latency_threshold_factor=2.0,
            latency_threshold_ms=500.0,
        )
        # 800ms vs 100ms = 8x increase AND >500ms increase → breaking
        assert diff.is_compatible is False

    def test_latency_regression_below_absolute_threshold(self):
        """Even if factor is >2x, if absolute increase < threshold_ms, it's OK."""
        baseline_int = _make_interaction("tools/list", result={"tools": []}, seq=0, latency=10.0)
        current_int = _make_interaction("tools/list", result={"tools": []}, seq=0, latency=30.0)
        baseline_rec = _make_recording([baseline_int])
        current_rec = _make_recording([current_int])

        diff = MCPDiff.compare(
            baseline_rec, current_rec,
            compare_latency=True,
            latency_threshold_factor=2.0,
            latency_threshold_ms=500.0,
        )
        # 3x factor but only 20ms increase — below 500ms absolute threshold
        assert diff.is_compatible is True

    def test_latency_not_checked_by_default(self):
        """Without compare_latency=True, huge latency increase is ignored."""
        baseline_int = _make_interaction("tools/list", result={"tools": []}, seq=0, latency=10.0)
        current_int = _make_interaction("tools/list", result={"tools": []}, seq=0, latency=10000.0)
        baseline_rec = _make_recording([baseline_int])
        current_rec = _make_recording([current_int])

        diff = MCPDiff.compare(baseline_rec, current_rec, compare_latency=False)
        # Same result, so compatible — latency is ignored
        assert diff.is_compatible is True
