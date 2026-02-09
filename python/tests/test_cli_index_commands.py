"""CLI tests for index, search, and diff-batch commands."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run agent-vcr CLI. Prefer python -m agent_vcr.cli from repo."""
    cmd = [sys.executable, "-m", "agent_vcr.cli"] + args
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_cli_index_builds_index(tmp_path, sample_recording):
    """agent-vcr index <dir> -o index.json produces index file."""
    sample_recording.save(str(tmp_path / "rec.vcr"))
    result = _run_cli(["index", str(tmp_path), "-o", str(tmp_path / "index.json")])
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert (tmp_path / "index.json").exists()
    data = json.loads((tmp_path / "index.json").read_text())
    assert "recordings" in data
    assert len(data["recordings"]) == 1


def test_cli_search_filters_by_method(tmp_path, sample_recording):
    """agent-vcr search index.json --method X returns matching entries."""
    sample_recording.save(str(tmp_path / "rec.vcr"))
    _run_cli(["index", str(tmp_path), "-o", str(tmp_path / "index.json")])
    result = _run_cli(["search", str(tmp_path / "index.json"), "--method", "tools/list"])
    assert result.returncode == 0
    assert "rec.vcr" in result.stdout or "rec" in result.stdout


def test_cli_diff_batch_runs_on_pairs(tmp_path, sample_recording):
    """agent-vcr diff-batch pairs.json runs diff for each pair."""
    base_vcr = tmp_path / "base.vcr"
    cur_vcr = tmp_path / "current.vcr"
    sample_recording.save(str(base_vcr))
    sample_recording.save(str(cur_vcr))
    pairs = {"pairs": [{"baseline": str(base_vcr), "current": str(cur_vcr)}]}
    (tmp_path / "pairs.json").write_text(json.dumps(pairs))
    result = _run_cli(["diff-batch", str(tmp_path / "pairs.json")])
    assert result.returncode == 0
    assert "Identical" in result.stdout or "identical" in result.stdout.lower()


def test_cli_diff_batch_fail_on_breaking(tmp_path, sample_recording):
    """agent-vcr diff-batch --fail-on-breaking exits 1 when breaking changes exist."""
    from agent_vcr.core.format import VCRRecording

    base_vcr = tmp_path / "base.vcr"
    cur_vcr = tmp_path / "current.vcr"
    sample_recording.save(str(base_vcr))
    # Current has one fewer interaction (removed = breaking)
    cur = VCRRecording.load(str(base_vcr))
    cur.session.interactions = cur.session.interactions[: max(0, len(cur.session.interactions) - 1)]
    cur.save(str(cur_vcr))
    pairs = {"pairs": [{"baseline": str(base_vcr), "current": str(cur_vcr)}]}
    (tmp_path / "pairs.json").write_text(json.dumps(pairs))
    result = _run_cli(["diff-batch", str(tmp_path / "pairs.json"), "--fail-on-breaking"])
    # Should exit non-zero when there are breaking changes
    assert result.returncode != 0
