"""Project manifest for multi-session recordings (docs/scaling.md).

A manifest lists multiple .vcr files with endpoint_id (and optional session_id)
so the replay orchestrator and diff can work on a set of sessions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

MANIFEST_VERSION = "1.0"


def load_manifest(path: str | Path) -> list[dict[str, Any]]:
    """Load a project manifest file.

    Args:
        path: Path to manifest JSON (e.g. project.json).

    Returns:
        List of recording entries: [ {"endpoint_id": str, "session_id": str|None, "path": str}, ... ]

    Raises:
        IOError: If file cannot be read
        ValueError: If manifest format is invalid
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    version = data.get("version", "1.0")
    recordings = data.get("recordings", [])
    if not isinstance(recordings, list):
        raise ValueError("Manifest 'recordings' must be a list")
    out: list[dict[str, Any]] = []
    for i, entry in enumerate(recordings):
        if not isinstance(entry, dict):
            raise ValueError(f"Manifest recordings[{i}] must be an object")
        path_val = entry.get("path")
        if not path_val:
            raise ValueError(f"Manifest recordings[{i}] must have 'path'")
        out.append({
            "endpoint_id": entry.get("endpoint_id", ""),
            "session_id": entry.get("session_id"),
            "path": str(path_val),
        })
    return out


def save_manifest(path: str | Path, recordings: list[dict[str, Any]]) -> None:
    """Save a project manifest file.

    Args:
        path: Output path for manifest JSON.
        recordings: List of {"endpoint_id": str, "session_id": str|None, "path": str}.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": MANIFEST_VERSION,
        "recordings": recordings,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def manifest_from_directory(
    directory: str | Path,
    pattern: str = "*.vcr",
    endpoint_from_name: bool = True,
) -> list[dict[str, Any]]:
    """Build a manifest from a directory of .vcr files.

    Optionally loads each file's metadata to get endpoint_id/session_id;
    otherwise uses filename stem as endpoint_id.

    Args:
        directory: Directory to scan.
        pattern: Glob for files (default *.vcr).
        endpoint_from_name: If True, use file stem as endpoint_id when metadata lacks it.

    Returns:
        List of recording entries for save_manifest().
    """
    from agent_vcr.core.format import VCRRecording

    directory = Path(directory)
    entries: list[dict[str, Any]] = []
    for fpath in sorted(directory.glob(pattern)):
        try:
            rec = VCRRecording.load(str(fpath))
            endpoint_id = rec.metadata.endpoint_id or (fpath.stem if endpoint_from_name else "")
            session_id = rec.metadata.session_id
            entries.append({
                "endpoint_id": endpoint_id,
                "session_id": session_id,
                "path": str(fpath.resolve()),
            })
        except Exception:
            # Fallback: no metadata, use stem
            entries.append({
                "endpoint_id": fpath.stem if endpoint_from_name else "",
                "session_id": None,
                "path": str(fpath.resolve()),
            })
    return entries


def load_record_config(path: str | Path) -> list[dict[str, Any]]:
    """Load a multi-session record config (for record --project).

    Config JSON: { "recordings": [ { "endpoint_id", "session_id"?, "transport", "server_command"?, "server_args"?, "server_url"?, "output" }, ... ] }

    Returns:
        List of recording config entries.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    recordings = data.get("recordings", [])
    if not isinstance(recordings, list):
        raise ValueError("Config 'recordings' must be a list")
    out: list[dict[str, Any]] = []
    for i, entry in enumerate(recordings):
        if not isinstance(entry, dict):
            raise ValueError(f"Config recordings[{i}] must be an object")
        transport = entry.get("transport", "stdio")
        output = entry.get("output")
        if not output:
            raise ValueError(f"Config recordings[{i}] must have 'output'")
        if transport == "stdio" and not entry.get("server_command"):
            raise ValueError(f"Config recordings[{i}] (stdio) must have 'server_command'")
        if transport == "sse" and not entry.get("server_url"):
            raise ValueError(f"Config recordings[{i}] (sse) must have 'server_url'")
        out.append(dict(entry))
    return out


__all__ = [
    "load_manifest",
    "save_manifest",
    "load_record_config",
    "manifest_from_directory",
    "MANIFEST_VERSION",
]
