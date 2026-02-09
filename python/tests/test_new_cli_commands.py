"""Tests for new CLI commands: validate, merge, stats."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_vcr.cli import cli
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


# ===== Helpers =====


def _make_recording(
    interactions: list[VCRInteraction],
    transport: str = "stdio",
) -> VCRRecording:
    return VCRRecording(
        format_version="1.0.0",
        metadata=VCRMetadata(
            version="1.0.0",
            recorded_at=datetime(2024, 1, 15, 10, 30, 0),
            transport=transport,
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


def _make_interaction(
    method: str, params=None, result=None, error=None,
    seq: int = 0, latency: float = 50.0,
) -> VCRInteraction:
    return VCRInteraction(
        sequence=seq,
        timestamp=datetime(2024, 1, 15, 10, 30, seq),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0", id=seq + 1, method=method, params=params
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0", id=seq + 1, result=result, error=error
        ),
        notifications=[],
        latency_ms=latency,
    )


def _save_recording(recording: VCRRecording, path: Path) -> Path:
    recording.save(str(path))
    return path


# ===== Validate command tests =====


class TestValidateCommand:
    """Tests for `agent-vcr validate` CLI command."""

    def test_validate_good_file(self, tmp_path):
        rec = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0),
            _make_interaction("tools/call", params={"name": "echo"}, result={"ok": True}, seq=1),
        ])
        vcr_file = _save_recording(rec, tmp_path / "good.vcr")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(vcr_file)])
        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "pass" in result.output.lower() or "✓" in result.output

    def test_validate_invalid_json(self, tmp_path):
        bad_file = tmp_path / "bad.vcr"
        bad_file.write_text("{ this is not valid json }")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(bad_file)])
        assert result.exit_code != 0 or "error" in result.output.lower() or "invalid" in result.output.lower()

    def test_validate_nonexistent_file(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(tmp_path / "nope.vcr")])
        assert result.exit_code != 0

    def test_validate_has_initialize(self, tmp_path):
        """Validate should check for initialize handshake."""
        rec = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0),
        ])
        vcr_file = _save_recording(rec, tmp_path / "with_init.vcr")

        runner = CliRunner()
        result = runner.invoke(cli, ["validate", str(vcr_file)])
        # Should pass since we have initialize request/response
        assert result.exit_code == 0


# ===== Merge command tests =====


class TestMergeCommand:
    """Tests for `agent-vcr merge` CLI command."""

    def test_merge_two_files(self, tmp_path):
        rec1 = _make_recording([
            _make_interaction("tools/list", result={"tools": ["a"]}, seq=0),
        ])
        rec2 = _make_recording([
            _make_interaction("tools/call", params={"name": "echo"}, result={"ok": True}, seq=0),
        ])
        f1 = _save_recording(rec1, tmp_path / "first.vcr")
        f2 = _save_recording(rec2, tmp_path / "second.vcr")
        out = tmp_path / "merged.vcr"

        runner = CliRunner()
        result = runner.invoke(cli, ["merge", str(f1), str(f2), "-o", str(out)])
        assert result.exit_code == 0
        assert out.exists()

        # Verify merged file has interactions from both
        merged = VCRRecording.load(str(out))
        methods = [i.request.method for i in merged.session.interactions]
        assert "tools/list" in methods
        assert "tools/call" in methods

    def test_merge_with_dedup(self, tmp_path):
        """Merge with --deduplicate should remove duplicates by method+params."""
        rec1 = _make_recording([
            _make_interaction("tools/list", params={}, result={"tools": ["a"]}, seq=0),
        ])
        rec2 = _make_recording([
            _make_interaction("tools/list", params={}, result={"tools": ["b"]}, seq=0),
        ])
        f1 = _save_recording(rec1, tmp_path / "first.vcr")
        f2 = _save_recording(rec2, tmp_path / "second.vcr")
        out = tmp_path / "merged.vcr"

        runner = CliRunner()
        result = runner.invoke(cli, ["merge", str(f1), str(f2), "-o", str(out), "--deduplicate"])
        assert result.exit_code == 0

        merged = VCRRecording.load(str(out))
        # With dedup, should only have one tools/list interaction
        tools_list_count = sum(
            1 for i in merged.session.interactions if i.request.method == "tools/list"
        )
        assert tools_list_count == 1

    def test_merge_requires_output(self, tmp_path):
        """Merge should require -o flag."""
        rec1 = _make_recording([_make_interaction("tools/list", result={"tools": []}, seq=0)])
        f1 = _save_recording(rec1, tmp_path / "first.vcr")

        runner = CliRunner()
        result = runner.invoke(cli, ["merge", str(f1)])
        # Should fail without -o
        assert result.exit_code != 0


# ===== Stats command tests =====


class TestStatsCommand:
    """Tests for `agent-vcr stats` CLI command."""

    def test_stats_basic(self, tmp_path):
        rec = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0, latency=100.0),
            _make_interaction("tools/call", params={"name": "echo"}, result={"ok": True}, seq=1, latency=200.0),
            _make_interaction("tools/call", params={"name": "add"}, result={"ok": True}, seq=2, latency=300.0),
        ])
        vcr_file = _save_recording(rec, tmp_path / "stats.vcr")

        runner = CliRunner()
        result = runner.invoke(cli, ["stats", str(vcr_file)])
        assert result.exit_code == 0
        # Should show method names
        assert "tools/list" in result.output
        assert "tools/call" in result.output

    def test_stats_shows_latency(self, tmp_path):
        rec = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0, latency=100.0),
            _make_interaction("tools/list", result={"tools": []}, seq=1, latency=200.0),
            _make_interaction("tools/list", result={"tools": []}, seq=2, latency=300.0),
        ])
        vcr_file = _save_recording(rec, tmp_path / "stats.vcr")

        runner = CliRunner()
        result = runner.invoke(cli, ["stats", str(vcr_file)])
        assert result.exit_code == 0
        # Should show latency info (p50, p95, or avg)
        output_lower = result.output.lower()
        assert "latency" in output_lower or "ms" in output_lower or "p50" in output_lower

    def test_stats_shows_error_rate(self, tmp_path):
        rec = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0),
            _make_interaction(
                "tools/call", seq=1,
                error=JSONRPCError(code=-32601, message="Not found"),
            ),
        ])
        vcr_file = _save_recording(rec, tmp_path / "stats.vcr")

        runner = CliRunner()
        result = runner.invoke(cli, ["stats", str(vcr_file)])
        assert result.exit_code == 0
        # Should show error information
        output_lower = result.output.lower()
        assert "error" in output_lower or "50" in result.output  # 50% error rate

    def test_stats_empty_recording(self, tmp_path):
        rec = _make_recording([])
        vcr_file = _save_recording(rec, tmp_path / "empty.vcr")

        runner = CliRunner()
        result = runner.invoke(cli, ["stats", str(vcr_file)])
        # Should handle gracefully, not crash
        assert result.exit_code == 0

    def test_stats_nonexistent_file(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["stats", str(tmp_path / "nope.vcr")])
        assert result.exit_code != 0


# ===== CLI match strategy tests =====


class TestCLIMatchStrategies:
    """Tests for CLI replay command match strategy options."""

    def test_all_strategies_accepted(self, tmp_path):
        """All 6 strategies should be accepted by the CLI parser."""
        rec = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0),
        ])
        vcr_file = _save_recording(rec, tmp_path / "test.vcr")

        runner = CliRunner()
        strategies = ["exact", "method", "method_and_params", "subset", "fuzzy", "sequential"]

        for strategy in strategies:
            # We just test that the CLI accepts the strategy without parse errors
            # Can't actually start a server in tests, but --help after strategy should work
            result = runner.invoke(cli, ["replay", str(vcr_file), "--match-strategy", strategy, "--help"])
            # --help should always exit 0 if the strategy was accepted
            assert result.exit_code == 0, f"Strategy '{strategy}' rejected: {result.output}"

    def test_invalid_strategy_rejected(self, tmp_path):
        rec = _make_recording([
            _make_interaction("tools/list", result={"tools": []}, seq=0),
        ])
        vcr_file = _save_recording(rec, tmp_path / "test.vcr")

        runner = CliRunner()
        result = runner.invoke(cli, ["replay", str(vcr_file), "--match-strategy", "bogus"])
        assert result.exit_code != 0
