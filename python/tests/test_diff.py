"""Tests for MCPDiff — comparing two VCR recordings."""

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
from agent_vcr.diff import MCPDiff, MCPDiffResult, ModifiedInteraction


# ===== Fixture Helpers =====


def create_recording(
    method: str,
    params=None,
    result=None,
    error=None,
) -> VCRRecording:
    """Helper to create a simple recording with one interaction."""
    init_req = JSONRPCRequest(
        jsonrpc="2.0", id=1, method="initialize"
    )
    init_resp = JSONRPCResponse(
        jsonrpc="2.0", id=1, result={"capabilities": {}}
    )

    interaction = VCRInteraction(
        sequence=0,
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0", id=2, method=method, params=params
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0", id=2, result=result, error=error
        ),
        latency_ms=10.0,
    )

    session = VCRSession(
        initialize_request=init_req,
        initialize_response=init_resp,
        interactions=[interaction],
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


# ===== ModifiedInteraction Tests =====


class TestModifiedInteraction:
    """Tests for ModifiedInteraction objects."""

    def test_compatible_same_success(self):
        """Two successful responses are compatible."""
        mod = ModifiedInteraction(
            method="test",
            baseline_request={"method": "test", "params": {"a": 1}},
            current_request={"method": "test", "params": {"a": 1}},
            baseline_response={"result": {"value": 1}},
            current_response={"result": {"value": 2}},
        )

        assert mod.is_compatible

    def test_compatible_success_to_error(self):
        """Changing from success to error is incompatible."""
        mod = ModifiedInteraction(
            method="test",
            baseline_request={"method": "test", "params": {}},
            current_request={"method": "test", "params": {}},
            baseline_response={"result": {"value": 1}},
            current_response={"error": {"code": -32603, "message": "Error"}},
        )

        assert not mod.is_compatible

    def test_compatible_error_to_success(self):
        """Changing from error to success is incompatible."""
        mod = ModifiedInteraction(
            method="test",
            baseline_request={"method": "test", "params": {}},
            current_request={"method": "test", "params": {}},
            baseline_response={"error": {"code": -32603, "message": "Error"}},
            current_response={"result": {"value": 1}},
        )

        assert not mod.is_compatible

    def test_compatible_same_error(self):
        """Two error responses are compatible."""
        mod = ModifiedInteraction(
            method="test",
            baseline_request={"method": "test", "params": {}},
            current_request={"method": "test", "params": {}},
            baseline_response={"error": {"code": -32603, "message": "Error1"}},
            current_response={"error": {"code": -32603, "message": "Error2"}},
        )

        assert mod.is_compatible

    def test_missing_result_field(self):
        """Missing result field in success response is incompatible."""
        mod = ModifiedInteraction(
            method="test",
            baseline_request={"method": "test", "params": {}},
            current_request={"method": "test", "params": {}},
            baseline_response={"result": {"value": 1}},
            current_response={},  # Missing result
        )

        assert not mod.is_compatible

    def test_to_dict(self):
        """ModifiedInteraction serializes to dict."""
        mod = ModifiedInteraction(
            method="test",
            baseline_request={"method": "test", "params": {}},
            current_request={"method": "test", "params": {}},
            baseline_response={"result": {"value": 1}},
            current_response={"result": {"value": 2}},
            request_diff={"values_changed": {}},
            response_diff={"values_changed": {}},
        )

        d = mod.to_dict()
        assert d["method"] == "test"
        assert d["is_compatible"] is True
        assert d["request_diff"] is not None


# ===== MCPDiffResult Tests =====


class TestMCPDiffResult:
    """Tests for MCPDiffResult objects."""

    def test_identical_summary(self):
        """Summary for identical recordings."""
        result = MCPDiffResult(is_identical=True, is_compatible=True)
        summary = result.summary()

        assert "identical" in summary.lower()

    def test_with_additions(self):
        """Summary with added interactions."""
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        interaction = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=init_req,
            response=init_resp,
            latency_ms=0.0,
        )

        result = MCPDiffResult(
            is_identical=False,
            is_compatible=True,
            added_interactions=[interaction],
        )

        summary = result.summary()
        assert "Added interactions: 1" in summary

    def test_with_removals(self):
        """Summary with removed interactions."""
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        interaction = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=init_req,
            response=init_resp,
            latency_ms=0.0,
        )

        result = MCPDiffResult(
            is_identical=False,
            is_compatible=True,
            removed_interactions=[interaction],
        )

        summary = result.summary()
        assert "Removed interactions: 1" in summary

    def test_with_breaking_changes(self):
        """Summary with breaking changes."""
        result = MCPDiffResult(
            is_identical=False,
            is_compatible=False,
            breaking_changes=[
                "Method removed: tools/list",
                "Response format changed in tools/call",
            ],
        )

        summary = result.summary()
        assert "INCOMPATIBLE" in summary
        assert "Breaking changes:" in summary
        assert "Method removed: tools/list" in summary

    def test_to_dict(self):
        """MCPDiffResult serializes to dict."""
        result = MCPDiffResult(
            is_identical=True,
            is_compatible=True,
        )

        d = result.to_dict()
        assert d["is_identical"] is True
        assert d["is_compatible"] is True


# ===== MCPDiff.compare Tests =====


class TestMCPDiffCompare:
    """Tests for MCPDiff.compare method."""

    def test_identical_recordings(self):
        """Identical recordings produce identical diff."""
        recording1 = create_recording(
            "tools/list", result={"tools": []}
        )
        recording2 = create_recording(
            "tools/list", result={"tools": []}
        )

        result = MCPDiff.compare(recording1, recording2)

        assert result.is_identical
        assert result.is_compatible

    def test_added_interaction(self):
        """Recording with additional interaction."""
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        baseline_session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
            interactions=[],
        )

        baseline = VCRRecording(
            format_version="1.0.0",
            metadata=VCRMetadata(
                version="1.0.0",
                recorded_at=datetime.now(),
                transport="stdio",
            ),
            session=baseline_session,
        )

        current = create_recording("tools/list", result={"tools": []})

        result = MCPDiff.compare(baseline, current)

        assert not result.is_identical
        assert len(result.added_interactions) == 1

    def test_removed_interaction(self):
        """Recording with fewer interactions."""
        baseline = create_recording("tools/list", result={"tools": []})

        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        current_session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
            interactions=[],
        )

        current = VCRRecording(
            format_version="1.0.0",
            metadata=VCRMetadata(
                version="1.0.0",
                recorded_at=datetime.now(),
                transport="stdio",
            ),
            session=current_session,
        )

        result = MCPDiff.compare(baseline, current)

        assert not result.is_identical
        assert len(result.removed_interactions) == 1

    def test_modified_response(self):
        """Interaction with modified response."""
        baseline = create_recording(
            "tools/list",
            result={"tools": [{"name": "tool1"}]},
        )

        current = create_recording(
            "tools/list",
            result={"tools": [{"name": "tool2"}]},
        )

        result = MCPDiff.compare(baseline, current)

        assert not result.is_identical
        assert len(result.modified_interactions) > 0

    def test_compare_with_file_paths(
        self, tmp_path: Path
    ):
        """Compare with file paths."""
        recording1 = create_recording(
            "tools/list", result={"tools": []}
        )
        recording2 = create_recording(
            "tools/list", result={"tools": []}
        )

        file1 = tmp_path / "recording1.vcr"
        file2 = tmp_path / "recording2.vcr"

        recording1.save(str(file1))
        recording2.save(str(file2))

        result = MCPDiff.compare(str(file1), str(file2))

        assert result.is_identical

    def test_compare_baseline_recording_object(self):
        """Compare with baseline as object."""
        baseline = create_recording(
            "tools/list", result={"tools": []}
        )
        current = create_recording(
            "tools/list", result={"tools": []}
        )

        result = MCPDiff.compare(baseline, current)

        assert result.is_identical

    def test_compare_method_added(self):
        """New method in current is breaking change."""
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        baseline_session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
            interactions=[],
        )

        baseline = VCRRecording(
            format_version="1.0.0",
            metadata=VCRMetadata(
                version="1.0.0",
                recorded_at=datetime.now(),
                transport="stdio",
            ),
            session=baseline_session,
        )

        current = create_recording(
            "tools/list", result={"tools": []}
        )

        result = MCPDiff.compare(baseline, current)

        assert not result.is_compatible
        assert any("New method added" in change for change in result.breaking_changes)

    def test_compare_method_removed(self):
        """Method in baseline but not current is breaking change."""
        baseline = create_recording(
            "tools/list", result={"tools": []}
        )

        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={}
        )

        current_session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
            interactions=[],
        )

        current = VCRRecording(
            format_version="1.0.0",
            metadata=VCRMetadata(
                version="1.0.0",
                recorded_at=datetime.now(),
                transport="stdio",
            ),
            session=current_session,
        )

        result = MCPDiff.compare(baseline, current)

        assert not result.is_compatible
        assert any("Method removed" in change for change in result.breaking_changes)

    def test_compare_error_to_success(self):
        """Error changing to success is breaking."""
        baseline = create_recording(
            "test",
            error=JSONRPCError(code=-32603, message="Error"),
        )

        current = create_recording(
            "test",
            result={"value": 1},
        )

        result = MCPDiff.compare(baseline, current)

        assert not result.is_compatible

    def test_compare_success_to_error(self):
        """Success changing to error is breaking."""
        baseline = create_recording(
            "test",
            result={"value": 1},
        )

        current = create_recording(
            "test",
            error=JSONRPCError(code=-32603, message="Error"),
        )

        result = MCPDiff.compare(baseline, current)

        assert not result.is_compatible


# ===== MCPDiff File Loading Tests =====


class TestMCPDiffLoadRecording:
    """Tests for loading recordings from files."""

    def test_load_recording_from_file(
        self, tmp_path: Path
    ):
        """Load recording from file."""
        recording = create_recording(
            "tools/list", result={"tools": []}
        )

        vcr_file = tmp_path / "test.vcr"
        recording.save(str(vcr_file))

        loaded = MCPDiff._load_recording(str(vcr_file))

        assert loaded.session.interactions[0].request.method == "tools/list"

    def test_load_recording_missing_file(self):
        """Load from missing file raises error."""
        with pytest.raises(FileNotFoundError):
            MCPDiff._load_recording("/nonexistent/file.vcr")

    def test_load_recording_path_object(
        self, tmp_path: Path
    ):
        """Load with Path object."""
        recording = create_recording(
            "tools/list", result={"tools": []}
        )

        vcr_file = tmp_path / "test.vcr"
        recording.save(str(vcr_file))

        loaded = MCPDiff._load_recording(vcr_file)

        assert loaded is not None


# ===== MCPDiff Matching Tests =====


class TestMCPDiffMatching:
    """Tests for finding matching interactions."""

    def test_find_matching_interaction_exact(self):
        """Find interaction with exact method and params."""
        interaction = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0",
                id=1,
                method="test",
                params={"key": "value"},
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0", id=1, result={}
            ),
            latency_ms=0.0,
        )

        candidates = [interaction]

        match = MCPDiff._find_matching_interaction(interaction, candidates)

        assert match == interaction

    def test_find_matching_interaction_no_match(self):
        """No match returns None."""
        interaction1 = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0",
                id=1,
                method="test1",
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0", id=1, result={}
            ),
            latency_ms=0.0,
        )

        interaction2 = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0",
                id=1,
                method="test2",
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0", id=1, result={}
            ),
            latency_ms=0.0,
        )

        candidates = [interaction2]

        match = MCPDiff._find_matching_interaction(interaction1, candidates)

        assert match is None

    def test_find_matching_interaction_params_different(self):
        """Different params means no match."""
        interaction1 = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0",
                id=1,
                method="test",
                params={"a": 1},
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0", id=1, result={}
            ),
            latency_ms=0.0,
        )

        interaction2 = VCRInteraction(
            sequence=0,
            timestamp=datetime.now(),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0",
                id=1,
                method="test",
                params={"a": 2},
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0", id=1, result={}
            ),
            latency_ms=0.0,
        )

        candidates = [interaction2]

        match = MCPDiff._find_matching_interaction(interaction1, candidates)

        assert match is None


# ===== Integration Tests =====


class TestMCPDiffIntegration:
    """Integration tests for MCPDiff."""

    def test_round_trip_with_files(
        self, tmp_path: Path
    ):
        """Save, load, compare recordings."""
        recording1 = create_recording(
            "tools/list", result={"tools": []}
        )
        recording2 = create_recording(
            "tools/list", result={"tools": []}
        )

        file1 = tmp_path / "rec1.vcr"
        file2 = tmp_path / "rec2.vcr"

        recording1.save(str(file1))
        recording2.save(str(file2))

        result = MCPDiff.compare(str(file1), str(file2))

        assert result.is_identical

    def test_complex_diff_scenario(self):
        """Complex diff with multiple changes."""
        init_req = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="initialize"
        )
        init_resp = JSONRPCResponse(
            jsonrpc="2.0", id=1, result={"capabilities": {}}
        )

        # Baseline with 3 interactions
        baseline_interactions = [
            VCRInteraction(
                sequence=0,
                timestamp=datetime(2024, 1, 15, 10, 30, 0),
                direction="client_to_server",
                request=JSONRPCRequest(
                    jsonrpc="2.0", id=2, method="tools/list"
                ),
                response=JSONRPCResponse(
                    jsonrpc="2.0", id=2, result={"tools": []}
                ),
                latency_ms=10.0,
            ),
            VCRInteraction(
                sequence=1,
                timestamp=datetime(2024, 1, 15, 10, 30, 1),
                direction="client_to_server",
                request=JSONRPCRequest(
                    jsonrpc="2.0", id=3, method="tools/call"
                ),
                response=JSONRPCResponse(
                    jsonrpc="2.0", id=3, result={"status": "ok"}
                ),
                latency_ms=10.0,
            ),
            VCRInteraction(
                sequence=2,
                timestamp=datetime(2024, 1, 15, 10, 30, 2),
                direction="client_to_server",
                request=JSONRPCRequest(
                    jsonrpc="2.0", id=4, method="resources/list"
                ),
                response=JSONRPCResponse(
                    jsonrpc="2.0", id=4, result={"resources": []}
                ),
                latency_ms=10.0,
            ),
        ]

        baseline = VCRRecording(
            format_version="1.0.0",
            metadata=VCRMetadata(
                version="1.0.0",
                recorded_at=datetime.now(),
                transport="stdio",
            ),
            session=VCRSession(
                initialize_request=init_req,
                initialize_response=init_resp,
                interactions=baseline_interactions,
            ),
        )

        # Current with 2 interactions (removed one, modified one, added one)
        current_interactions = [
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
                    result={"tools": [{"name": "new_tool"}]},
                ),
                latency_ms=10.0,
            ),
            VCRInteraction(
                sequence=1,
                timestamp=datetime(2024, 1, 15, 10, 30, 1),
                direction="client_to_server",
                request=JSONRPCRequest(
                    jsonrpc="2.0", id=5, method="logging/set_level"
                ),
                response=JSONRPCResponse(
                    jsonrpc="2.0", id=5, result={}
                ),
                latency_ms=10.0,
            ),
        ]

        current = VCRRecording(
            format_version="1.0.0",
            metadata=VCRMetadata(
                version="1.0.0",
                recorded_at=datetime.now(),
                transport="stdio",
            ),
            session=VCRSession(
                initialize_request=init_req,
                initialize_response=init_resp,
                interactions=current_interactions,
            ),
        )

        result = MCPDiff.compare(baseline, current)

        # Should detect all changes
        assert not result.is_identical
        assert len(result.modified_interactions) > 0
        assert len(result.removed_interactions) > 0
        assert len(result.added_interactions) > 0
