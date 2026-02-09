"""Index many .vcr files for fast search (SCALING.md Phase 3).

Builds a JSON index of path, endpoint_id, agent_id, recorded_at, methods, interaction_count
so you can search by method, endpoint, agent, or date without loading every file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

INDEX_VERSION = "1.0"


def build_index(
    directory: str | Path,
    output_path: str | Path,
    pattern: str = "*.vcr",
) -> int:
    """Scan directory for .vcr files and write a JSON index.

    Args:
        directory: Directory to scan.
        output_path: Path for index JSON.
        pattern: Glob for files (default *.vcr).

    Returns:
        Number of recordings indexed.
    """
    from agent_vcr.core.format import VCRRecording

    directory = Path(directory)
    output_path = Path(output_path)
    entries: list[dict[str, Any]] = []
    for fpath in sorted(directory.glob(pattern)):
        try:
            rec = VCRRecording.load(str(fpath))
            methods = list({i.request.method for i in rec.session.interactions})
            entries.append({
                "path": str(fpath.resolve()),
                "endpoint_id": rec.metadata.endpoint_id,
                "agent_id": rec.metadata.agent_id,
                "session_id": rec.metadata.session_id,
                "recorded_at": str(rec.metadata.recorded_at),
                "methods": methods,
                "interaction_count": len(rec.session.interactions),
            })
        except Exception:
            continue
    data = {"version": INDEX_VERSION, "recordings": entries}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return len(entries)


def load_index(path: str | Path) -> list[dict[str, Any]]:
    """Load an index file.

    Returns:
        List of index entries (path, endpoint_id, agent_id, recorded_at, methods, interaction_count).
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("recordings", [])


def search_index(
    index_path: str | Path,
    method: Optional[str] = None,
    endpoint_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Search index by method, endpoint_id, or agent_id.

    Args:
        index_path: Path to index JSON.
        method: If set, only entries that recorded this method.
        endpoint_id: If set, only entries with this endpoint_id.
        agent_id: If set, only entries with this agent_id.

    Returns:
        Matching index entries.
    """
    entries = load_index(index_path)
    out = []
    for e in entries:
        if method is not None and method not in e.get("methods", []):
            continue
        if endpoint_id is not None and e.get("endpoint_id") != endpoint_id:
            continue
        if agent_id is not None and e.get("agent_id") != agent_id:
            continue
        out.append(e)
    return out


__all__ = ["build_index", "load_index", "search_index", "INDEX_VERSION"]
