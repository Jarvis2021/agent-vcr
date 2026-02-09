"""Tests for indexer: build_index, load_index, search_index."""

from datetime import datetime

import pytest

from agent_vcr.core.format import (
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
    VCRRecording,
    VCRSession,
)
from agent_vcr.indexer import build_index, load_index, search_index


def _recording(path: str, endpoint_id: str | None, methods: list[str]) -> VCRRecording:
    meta = VCRMetadata(
        version="1.0.0",
        recorded_at=datetime(2024, 1, 15, 10, 0, 0),
        transport="stdio",
        endpoint_id=endpoint_id,
    )
    init_req = JSONRPCRequest(jsonrpc="2.0", id=0, method="initialize", params={})
    init_res = JSONRPCResponse(jsonrpc="2.0", id=0, result={"protocolVersion": "2024-11-05"})
    interactions = [
        VCRInteraction(
            sequence=i,
            timestamp=datetime(2024, 1, 15, 10, 0, i + 1),
            direction="client_to_server",
            request=JSONRPCRequest(jsonrpc="2.0", id=i + 1, method=m, params={}),
            response=JSONRPCResponse(jsonrpc="2.0", id=i + 1, result={}),
            latency_ms=10.0,
        )
        for i, m in enumerate(methods)
    ]
    session = VCRSession(
        initialize_request=init_req,
        initialize_response=init_res,
        interactions=interactions,
    )
    return VCRRecording(metadata=meta, session=session)


def test_build_index(tmp_path):
    """build_index scans directory and writes JSON index."""
    r1 = _recording("a.vcr", "ep1", ["initialize", "tools/list"])
    r1.save(str(tmp_path / "a.vcr"))
    r2 = _recording("b.vcr", "ep2", ["initialize", "tools/call"])
    r2.save(str(tmp_path / "b.vcr"))

    out = tmp_path / "index.json"
    count = build_index(tmp_path, out)
    assert count == 2
    assert out.exists()
    data = out.read_text()
    assert "a.vcr" in data or "a" in data
    assert "tools/list" in data
    assert "tools/call" in data


def test_load_index(tmp_path, sample_recording):
    """load_index returns list of entries."""
    sample_recording.save(str(tmp_path / "s.vcr"))
    build_index(tmp_path, tmp_path / "idx.json")
    entries = load_index(tmp_path / "idx.json")
    assert len(entries) == 1
    e = entries[0]
    assert "path" in e
    assert "methods" in e
    assert "interaction_count" in e


def test_search_index_by_method(tmp_path):
    """search_index filters by method."""
    r1 = _recording("a.vcr", "ep1", ["initialize", "tools/list"])
    r2 = _recording("b.vcr", "ep2", ["initialize", "resources/list"])
    r1.save(str(tmp_path / "a.vcr"))
    r2.save(str(tmp_path / "b.vcr"))
    build_index(tmp_path, tmp_path / "idx.json")

    matches = search_index(tmp_path / "idx.json", method="tools/list")
    assert len(matches) == 1
    assert "tools/list" in matches[0]["methods"]

    matches = search_index(tmp_path / "idx.json", method="resources/list")
    assert len(matches) == 1
    assert "resources/list" in matches[0]["methods"]

    matches = search_index(tmp_path / "idx.json", method="nonexistent")
    assert len(matches) == 0


def test_search_index_by_endpoint_id(tmp_path):
    """search_index filters by endpoint_id."""
    r1 = _recording("a.vcr", "filesystem", ["initialize"])
    r2 = _recording("b.vcr", "github", ["initialize"])
    r1.save(str(tmp_path / "a.vcr"))
    r2.save(str(tmp_path / "b.vcr"))
    build_index(tmp_path, tmp_path / "idx.json")

    matches = search_index(tmp_path / "idx.json", endpoint_id="filesystem")
    assert len(matches) == 1
    assert matches[0]["endpoint_id"] == "filesystem"

    matches = search_index(tmp_path / "idx.json", endpoint_id="github")
    assert len(matches) == 1
    assert matches[0]["endpoint_id"] == "github"


def test_search_index_by_agent_id(tmp_path):
    """search_index filters by agent_id."""
    r1 = _recording("a.vcr", "ep1", ["initialize"])
    r2 = _recording("b.vcr", "ep2", ["initialize"])
    r1.metadata.agent_id = "agent-a"
    r2.metadata.agent_id = "agent-b"
    r1.save(str(tmp_path / "a.vcr"))
    r2.save(str(tmp_path / "b.vcr"))
    build_index(tmp_path, tmp_path / "idx.json")

    matches = search_index(tmp_path / "idx.json", agent_id="agent-a")
    assert len(matches) == 1
    assert matches[0]["agent_id"] == "agent-a"

    matches = search_index(tmp_path / "idx.json", agent_id="agent-b")
    assert len(matches) == 1
    assert matches[0]["agent_id"] == "agent-b"

    matches = search_index(tmp_path / "idx.json", agent_id="nonexistent")
    assert len(matches) == 0
