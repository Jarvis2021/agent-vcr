"""Tests for bug fixes — shlex.split, Ctrl+C empty recording, diff formatting.

These tests cover edge cases that caused real crashes found during hands-on testing:
  1. --server-command "python demo/server.py" treated as single executable path
  2. Ctrl+C before any MCP client connects → RuntimeError in stop_recording()
  3. Breaking change diff message printing <ModifiedInteraction object at 0x...>
"""

from __future__ import annotations

import json
import shlex
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_vcr.core.format import (
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
    VCRRecording,
    VCRSession,
)
from agent_vcr.core.session import SessionManager
from agent_vcr.diff import MCPDiff, MCPDiffResult, ModifiedInteraction
from agent_vcr.recorder import MCPRecorder, _make_empty_recording


# ===== 1. shlex.split command parsing (cli.py fix) =====


class TestShlexCommandParsing:
    """Tests for the shlex.split() fix in cli.py.

    The CLI receives --server-command as a single string like
    "python demo/servers/calculator_v1.py". This must be split into
    command="python" + args=["demo/servers/calculator_v1.py"] before
    being passed to asyncio.create_subprocess_exec.
    """

    def test_simple_command_splits_correctly(self):
        """'python demo/server.py' → ['python', 'demo/server.py']."""
        cmd = "python demo/servers/calculator_v1.py"
        parts = shlex.split(cmd)
        assert parts[0] == "python"
        assert parts[1:] == ["demo/servers/calculator_v1.py"]

    def test_command_with_spaces_in_path(self):
        """Quoted paths with spaces are handled correctly."""
        cmd = 'python "my project/server.py"'
        parts = shlex.split(cmd)
        assert parts[0] == "python"
        assert parts[1:] == ["my project/server.py"]

    def test_command_with_multiple_args(self):
        """Multiple arguments are all split correctly."""
        cmd = "node server.js --port 3000 --debug"
        parts = shlex.split(cmd)
        assert parts[0] == "node"
        assert parts[1:] == ["server.js", "--port", "3000", "--debug"]

    def test_single_command_no_args(self):
        """A single command without args produces one-element list."""
        cmd = "python3"
        parts = shlex.split(cmd)
        assert parts == ["python3"]
        assert parts[1:] == []

    def test_cli_record_merges_parsed_args_with_server_args(self):
        """Parsed args from --server-command are prepended to --server-args."""
        server_command = "python demo/server.py"
        server_args = ("--verbose",)  # Click gives tuple

        parts = shlex.split(server_command)
        parsed_command = parts[0]
        parsed_args = parts[1:] + list(server_args)

        assert parsed_command == "python"
        assert parsed_args == ["demo/server.py", "--verbose"]

    def test_recorder_receives_split_command(self):
        """MCPRecorder receives the executable, not the full string."""
        # Simulate what cli.py does after the fix
        server_command = "python demo/servers/calculator_v1.py"
        parts = shlex.split(server_command)

        recorder = MCPRecorder(
            transport="stdio",
            server_command=parts[0],
            server_args=parts[1:],
        )

        assert recorder.server_command == "python"
        assert recorder.server_args == ["demo/servers/calculator_v1.py"]


# ===== 2. Ctrl+C before initialize → empty recording (recorder.py fix) =====


class TestEmptyRecording:
    """Tests for the _make_empty_recording() fix in recorder.py.

    When a user presses Ctrl+C before any MCP client sends an 'initialize'
    request, SessionManager is still in 'idle' state. The recorder must
    handle this gracefully instead of crashing.
    """

    def test_make_empty_recording_returns_valid_recording(self):
        """_make_empty_recording produces a valid VCRRecording."""
        recorder = MCPRecorder(
            transport="stdio",
            server_command="python",
            server_args=["server.py"],
        )
        recorder._recording_start_time = datetime.now().timestamp()

        recording = _make_empty_recording(recorder)

        assert isinstance(recording, VCRRecording)
        assert recording.format_version == "1.0.0"
        assert recording.session.interactions == []
        assert recording.session.initialize_request.method == "initialize"
        assert recording.session.initialize_response.result == {"capabilities": {}}

    def test_make_empty_recording_preserves_metadata(self):
        """Empty recording includes correct transport and tag metadata."""
        recorder = MCPRecorder(
            transport="stdio",
            server_command="python",
            server_args=["server.py"],
            metadata_tags={"env": "test", "version": "1.0"},
        )
        recorder._recording_start_time = datetime.now().timestamp()

        recording = _make_empty_recording(recorder)

        assert recording.metadata.transport == "stdio"
        assert recording.metadata.tags == {"env": "test", "version": "1.0"}
        assert recording.metadata.server_command == "python"
        assert recording.metadata.server_args == ["server.py"]

    def test_make_empty_recording_serializes_to_json(self):
        """Empty recording can be serialized to JSON without errors."""
        recorder = MCPRecorder(
            transport="stdio",
            server_command="python",
            server_args=["server.py"],
        )
        recorder._recording_start_time = datetime.now().timestamp()

        recording = _make_empty_recording(recorder)
        json_str = json.dumps(
            recording.model_dump(mode="json"), indent=2, default=str
        )

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["format_version"] == "1.0.0"
        assert parsed["session"]["interactions"] == []

    def test_make_empty_recording_saves_to_file(self, tmp_path):
        """Empty recording can be saved and loaded back from file."""
        recorder = MCPRecorder(
            transport="stdio",
            server_command="python",
            server_args=["server.py"],
        )
        recorder._recording_start_time = datetime.now().timestamp()

        recording = _make_empty_recording(recorder)

        out_path = tmp_path / "empty.vcr"
        recording.save(str(out_path))

        # Load it back
        loaded = VCRRecording.load(str(out_path))
        assert loaded.session.interactions == []
        assert loaded.session.initialize_request.method == "initialize"

    def test_session_manager_idle_state_is_detected(self):
        """SessionManager starts in idle state, not recording."""
        sm = SessionManager()
        assert sm.current_state == "idle"
        assert not sm.is_recording

    def test_recorder_stop_uses_empty_recording_when_idle(self):
        """When session never started, stop() returns empty recording (not crash)."""
        recorder = MCPRecorder(
            transport="stdio",
            server_command="python",
            server_args=["server.py"],
        )
        # Manually set state as if start() was called but no initialize received
        recorder._is_recording = True
        recorder._recording_start_time = datetime.now().timestamp()
        recorder._transport = MagicMock()
        recorder._transport.stop = AsyncMock()

        # stop() should NOT raise RuntimeError
        import asyncio

        recording = asyncio.get_event_loop().run_until_complete(
            recorder.stop(str(Path("/tmp/test_empty.vcr")))
        )

        assert isinstance(recording, VCRRecording)
        assert recording.session.interactions == []


# ===== 3. Diff breaking change message formatting (diff.py fix) =====


class TestDiffBreakingChangeFormatting:
    """Tests for the breaking change message fix in diff.py.

    Previously, breaking change messages contained {diff} which printed
    as '<ModifiedInteraction object at 0x...>' because the dataclass
    has no __str__. Now it prints readable details.
    """

    def test_breaking_change_message_is_readable(self):
        """Breaking change messages contain field names, not object repr."""
        # Create two recordings with incompatible changes
        init_req = JSONRPCRequest(jsonrpc="2.0", id=0, method="initialize", params={})
        init_resp = JSONRPCResponse(jsonrpc="2.0", id=0, result={"capabilities": {}})

        baseline_interaction = VCRInteraction(
            sequence=0,
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0", id=1, method="tools/call",
                params={"name": "echo", "arguments": {"text": "hi"}},
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0", id=1,
                result={"content": [{"type": "text", "text": "hi"}]},
            ),
            notifications=[],
            latency_ms=10.0,
        )

        current_interaction = VCRInteraction(
            sequence=0,
            timestamp=datetime(2024, 1, 1, 0, 0, 1),
            direction="client_to_server",
            request=JSONRPCRequest(
                jsonrpc="2.0", id=1, method="tools/call",
                params={"name": "echo", "arguments": {"text": "hi"}},
            ),
            response=JSONRPCResponse(
                jsonrpc="2.0", id=1,
                error={"code": -32601, "message": "Method not found"},
            ),
            notifications=[],
            latency_ms=10.0,
        )

        baseline_session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
            capabilities={},
            interactions=[baseline_interaction],
        )
        current_session = VCRSession(
            initialize_request=init_req,
            initialize_response=init_resp,
            capabilities={},
            interactions=[current_interaction],
        )

        metadata = VCRMetadata(
            version="1.0", recorded_at=datetime(2024, 1, 1), transport="stdio",
        )

        baseline = VCRRecording(
            format_version="1.0.0", metadata=metadata, session=baseline_session,
        )
        current = VCRRecording(
            format_version="1.0.0", metadata=metadata, session=current_session,
        )

        result = MCPDiff.compare(baseline, current)

        # Should NOT contain object repr like '<ModifiedInteraction'
        for change in result.breaking_changes:
            assert "<ModifiedInteraction" not in change
            assert "object at 0x" not in change

        # Should contain useful info
        assert any("request_changed=" in c or "response_changed=" in c
                    for c in result.breaking_changes)

    def test_modified_interaction_to_dict_works(self):
        """ModifiedInteraction.to_dict() produces serializable output."""
        mod = ModifiedInteraction(
            method="tools/call",
            baseline_request={"method": "tools/call", "params": {}},
            current_request={"method": "tools/call", "params": {"new": True}},
            baseline_response={"result": {"ok": True}},
            current_response={"error": {"code": -1, "message": "fail"}},
            request_diff={"values_changed": {"root['params']": {"new_value": {"new": True}}}},
            response_diff={"type_changes": {}},
        )

        d = mod.to_dict()
        assert d["method"] == "tools/call"
        assert d["is_compatible"] is False  # success→error is breaking
        # Should be JSON-serializable
        json.dumps(d)


# ===== 4. stdio.py assert → RuntimeError =====


class TestStdioTransportGuard:
    """Test that stdio transport raises RuntimeError instead of AssertionError."""

    def test_read_messages_raises_runtime_error_not_assert(self):
        """_read_messages raises RuntimeError if process not started."""
        from agent_vcr.transport.stdio import StdioTransport

        transport = StdioTransport(
            server_command="python",
            server_args=["server.py"],
        )
        # _process is None — calling _read_messages should raise RuntimeError
        import asyncio

        with pytest.raises(RuntimeError, match="server process not started"):
            asyncio.get_event_loop().run_until_complete(transport._read_messages())
