"""MCPDiff — Compare two VCR recordings and produce a structured diff.

Useful for regression testing: record a baseline, make changes, record again,
then diff to see exactly what changed in the MCP communication.

Usage:
    diff = MCPDiff.compare("baseline.vcr", "current.vcr")
    print(diff.summary())
    diff.print_detailed()

    # Check for regressions:
    assert diff.is_compatible, f"Breaking changes detected: {diff.breaking_changes}"
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    from deepdiff import DeepDiff
except ImportError:
    raise ImportError(
        "deepdiff is required for MCPDiff. Install with: pip install deepdiff"
    )

try:
    from rich.console import Console
    from rich.table import Table
except ImportError:
    raise ImportError(
        "rich is required for MCPDiff. Install with: pip install rich"
    )

from agent_vcr.core.format import VCRInteraction, VCRRecording

logger = logging.getLogger(__name__)


@dataclass
class ModifiedInteraction:
    """Represents a modified interaction between two recordings.

    Attributes:
        method: The RPC method name
        baseline_request: Request from baseline recording
        current_request: Request from current recording
        baseline_response: Response from baseline recording
        current_response: Response from current recording
        request_diff: DeepDiff of requests (None if identical)
        response_diff: DeepDiff of responses (None if identical)
    """

    method: str
    baseline_request: dict[str, Any]
    current_request: dict[str, Any]
    baseline_response: dict[str, Any]
    current_response: dict[str, Any]
    request_diff: Optional[dict[str, Any]] = None
    response_diff: Optional[dict[str, Any]] = None

    @property
    def is_compatible(self) -> bool:
        """Check if the modification is backwards compatible.

        A modification is compatible if:
        - The method name is the same
        - The response status hasn't changed (success -> error or vice versa)
        - No required response fields are missing in current

        Returns:
            True if the modification is backwards compatible
        """
        # Check if both are errors or both are successes
        baseline_is_error = "error" in self.baseline_response
        current_is_error = "error" in self.current_response

        if baseline_is_error != current_is_error:
            return False

        # If baseline was success, current must still have result
        if not baseline_is_error and "result" not in self.current_response:
            return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation of the modification
        """
        return {
            "method": self.method,
            "baseline_request": self.baseline_request,
            "current_request": self.current_request,
            "baseline_response": self.baseline_response,
            "current_response": self.current_response,
            "request_diff": self.request_diff,
            "response_diff": self.response_diff,
            "is_compatible": self.is_compatible,
        }


@dataclass
class MCPDiffResult:
    """Result of comparing two VCR recordings.

    Attributes:
        is_identical: True if recordings are identical
        is_compatible: True if no breaking changes detected
        added_interactions: Interactions in current but not baseline
        removed_interactions: Interactions in baseline but not current
        modified_interactions: Interactions with same method but different content
        breaking_changes: Human-readable list of breaking changes
        baseline_recording: The baseline VCRRecording
        current_recording: The current VCRRecording
    """

    is_identical: bool
    is_compatible: bool
    added_interactions: list[VCRInteraction] = field(default_factory=list)
    removed_interactions: list[VCRInteraction] = field(default_factory=list)
    modified_interactions: list[ModifiedInteraction] = field(default_factory=list)
    breaking_changes: list[str] = field(default_factory=list)
    baseline_recording: Optional[VCRRecording] = None
    current_recording: Optional[VCRRecording] = None

    def summary(self) -> str:
        """Generate a concise text summary of the diff.

        Returns:
            Multi-line string summary
        """
        lines = []

        if self.is_identical:
            lines.append("Recordings are identical.")
            return "\n".join(lines)

        lines.append("Differences detected:")
        lines.append(f"  Added interactions: {len(self.added_interactions)}")
        lines.append(f"  Removed interactions: {len(self.removed_interactions)}")
        lines.append(f"  Modified interactions: {len(self.modified_interactions)}")

        if self.is_compatible:
            lines.append("\nStatus: COMPATIBLE (no breaking changes)")
        else:
            lines.append("\nStatus: INCOMPATIBLE (breaking changes detected)")
            lines.append("\nBreaking changes:")
            for change in self.breaking_changes:
                lines.append(f"  - {change}")

        return "\n".join(lines)

    def print_detailed(self, use_pager: bool = False) -> None:
        """Print a detailed, richly formatted diff output.

        Args:
            use_pager: If True, use system pager for output
        """
        console = Console(record=use_pager)

        if self.is_identical:
            console.print("[green]✓[/green] Recordings are identical")
            if use_pager:
                self._show_pager(console)
            return

        console.print("[bold]Diff Summary[/bold]")
        summary_table = Table(show_header=True, header_style="bold magenta")
        summary_table.add_column("Category")
        summary_table.add_column("Count")

        summary_table.add_row("Added", str(len(self.added_interactions)))
        summary_table.add_row("Removed", str(len(self.removed_interactions)))
        summary_table.add_row("Modified", str(len(self.modified_interactions)))

        console.print(summary_table)

        # Added interactions
        if self.added_interactions:
            console.print("\n[bold green]Added Interactions[/bold green]")
            added_table = Table(show_header=True, header_style="bold")
            added_table.add_column("Method")
            added_table.add_column("ID")

            for interaction in self.added_interactions:
                if interaction.request:
                    method = interaction.request.method
                    msg_id = str(interaction.request.id or "—")
                    added_table.add_row(method, msg_id)

            console.print(added_table)

        # Removed interactions
        if self.removed_interactions:
            console.print("\n[bold red]Removed Interactions[/bold red]")
            removed_table = Table(show_header=True, header_style="bold")
            removed_table.add_column("Method")
            removed_table.add_column("ID")

            for interaction in self.removed_interactions:
                if interaction.request:
                    method = interaction.request.method
                    msg_id = str(interaction.request.id or "—")
                    removed_table.add_row(method, msg_id)

            console.print(removed_table)

        # Modified interactions
        if self.modified_interactions:
            console.print("\n[bold yellow]Modified Interactions[/bold yellow]")
            modified_table = Table(show_header=True, header_style="bold")
            modified_table.add_column("Method")
            modified_table.add_column("Request Changed")
            modified_table.add_column("Response Changed")
            modified_table.add_column("Compatible")

            for mod in self.modified_interactions:
                req_changed = "Yes" if mod.request_diff else "No"
                resp_changed = "Yes" if mod.response_diff else "No"
                compatible = "[green]Yes[/green]" if mod.is_compatible else "[red]No[/red]"
                modified_table.add_row(mod.method, req_changed, resp_changed, compatible)

            console.print(modified_table)

        # Breaking changes
        if self.breaking_changes:
            console.print("\n[bold red]Breaking Changes[/bold red]")
            for change in self.breaking_changes:
                console.print(f"  [red]✗[/red] {change}")
        else:
            console.print("\n[bold green]No breaking changes detected[/bold green]")

        if use_pager:
            self._show_pager(console)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary.

        Returns:
            Dictionary representation of the diff result
        """
        return {
            "is_identical": self.is_identical,
            "is_compatible": self.is_compatible,
            "added_count": len(self.added_interactions),
            "removed_count": len(self.removed_interactions),
            "modified_count": len(self.modified_interactions),
            "added_interactions": [
                {
                    "method": i.request.method if i.request else "unknown",
                    "interaction": i.model_dump(),
                }
                for i in self.added_interactions
            ],
            "removed_interactions": [
                {
                    "method": i.request.method if i.request else "unknown",
                    "interaction": i.model_dump(),
                }
                for i in self.removed_interactions
            ],
            "modified_interactions": [m.to_dict() for m in self.modified_interactions],
            "breaking_changes": self.breaking_changes,
        }

    def _show_pager(self, console: Console) -> None:
        """Display console output in system pager.

        Args:
            console: Rich console with recorded output
        """
        try:
            console.pager()
        except Exception:
            # Pager not available, just print
            pass


class MCPDiff:
    """Utility for comparing two VCR recordings."""

    @classmethod
    def compare(
        cls,
        baseline: str | Path | VCRRecording,
        current: str | Path | VCRRecording,
        ignore_params: bool = False,
    ) -> MCPDiffResult:
        """Compare two VCR recordings and produce a diff.

        Args:
            baseline: Path to baseline .vcr file or VCRRecording object
            current: Path to current .vcr file or VCRRecording object
            ignore_params: If True, match by method name only

        Returns:
            MCPDiffResult with comparison results

        Raises:
            FileNotFoundError: If file paths don't exist
            ValueError: If recordings are invalid
        """
        # Load recordings
        if isinstance(baseline, (str, Path)):
            baseline_recording = cls._load_recording(baseline)
        else:
            baseline_recording = baseline

        if isinstance(current, (str, Path)):
            current_recording = cls._load_recording(current)
        else:
            current_recording = current

        logger.info(
            f"Comparing recordings: "
            f"{len(baseline_recording.session.interactions)} baseline vs "
            f"{len(current_recording.session.interactions)} current"
        )

        # Extract and index interactions
        baseline_interactions = baseline_recording.session.interactions
        current_interactions = current_recording.session.interactions

        # Build indices by method name
        baseline_by_method: dict[str, list[VCRInteraction]] = {}
        for interaction in baseline_interactions:
            method = interaction.request.method if interaction.request else "unknown"
            if method not in baseline_by_method:
                baseline_by_method[method] = []
            baseline_by_method[method].append(interaction)

        current_by_method: dict[str, list[VCRInteraction]] = {}
        for interaction in current_interactions:
            method = interaction.request.method if interaction.request else "unknown"
            if method not in current_by_method:
                current_by_method[method] = []
            current_by_method[method].append(interaction)

        # Compare
        added = []
        removed = []
        modified = []
        breaking_changes = []

        # Find added and modified
        for method, current_list in current_by_method.items():
            baseline_list = baseline_by_method.get(method, [])

            if not baseline_list:
                # All are added
                added.extend(current_list)
                breaking_changes.append(f"New method added: {method}")
            else:
                # Compare each interaction
                baseline_matched = set()
                for current_interaction in current_list:
                    match = cls._find_matching_interaction(
                        current_interaction, baseline_list
                    )
                    if match:
                        baseline_matched.add(id(match))
                        diff = cls._diff_interactions(match, current_interaction)
                        if diff:
                            modified.append(diff)
                            if not diff.is_compatible:
                                breaking_changes.append(
                                    f"Breaking change in {method}: {diff}"
                                )
                    else:
                        added.append(current_interaction)

                # Find removed
                for baseline_interaction in baseline_list:
                    if id(baseline_interaction) not in baseline_matched:
                        removed.append(baseline_interaction)

        # Find removed methods
        for method, baseline_list in baseline_by_method.items():
            if method not in current_by_method:
                removed.extend(baseline_list)
                breaking_changes.append(f"Method removed: {method}")

        is_identical = (
            not added and not removed and not modified and not breaking_changes
        )
        is_compatible = not breaking_changes

        result = MCPDiffResult(
            is_identical=is_identical,
            is_compatible=is_compatible,
            added_interactions=added,
            removed_interactions=removed,
            modified_interactions=modified,
            breaking_changes=breaking_changes,
            baseline_recording=baseline_recording,
            current_recording=current_recording,
        )

        logger.info(
            f"Diff complete: identical={is_identical}, compatible={is_compatible}"
        )

        return result

    @staticmethod
    def _load_recording(path: str | Path) -> VCRRecording:
        """Load a VCR recording from file.

        Args:
            path: Path to .vcr file

        Returns:
            VCRRecording object

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"VCR file not found: {path}")

        with open(path) as f:
            data = json.load(f)

        return VCRRecording.model_validate(data)

    @staticmethod
    def _find_matching_interaction(
        interaction: VCRInteraction, candidates: list[VCRInteraction]
    ) -> Optional[VCRInteraction]:
        """Find a matching interaction in a list.

        Matches by request method and params.

        Args:
            interaction: Interaction to match
            candidates: List of candidate interactions

        Returns:
            Matching interaction or None
        """
        if not interaction.request:
            return None

        for candidate in candidates:
            if not candidate.request:
                continue

            if (
                candidate.request.method == interaction.request.method
                and candidate.request.params == interaction.request.params
            ):
                return candidate

        return None

    @staticmethod
    def _diff_interactions(
        baseline: VCRInteraction, current: VCRInteraction
    ) -> Optional[ModifiedInteraction]:
        """Compute a detailed diff between two interactions.

        Args:
            baseline: Baseline interaction
            current: Current interaction

        Returns:
            ModifiedInteraction if they differ, None if identical
        """
        request_diff = None
        response_diff = None

        # Compare requests
        if baseline.request and current.request:
            baseline_req = {
                "method": baseline.request.method,
                "params": baseline.request.params,
            }
            current_req = {
                "method": current.request.method,
                "params": current.request.params,
            }
            if baseline_req != current_req:
                request_diff = DeepDiff(baseline_req, current_req).to_dict()

        # Compare responses
        if baseline.response and current.response:
            baseline_resp = {}
            if hasattr(baseline.response, "result"):
                baseline_resp["result"] = baseline.response.result
            if hasattr(baseline.response, "error"):
                baseline_resp["error"] = baseline.response.error

            current_resp = {}
            if hasattr(current.response, "result"):
                current_resp["result"] = current.response.result
            if hasattr(current.response, "error"):
                current_resp["error"] = current.response.error

            if baseline_resp != current_resp:
                response_diff = DeepDiff(baseline_resp, current_resp).to_dict()

        # Return if any differences
        if request_diff or response_diff:
            return ModifiedInteraction(
                method=baseline.request.method if baseline.request else "unknown",
                baseline_request={
                    "method": baseline.request.method if baseline.request else None,
                    "params": baseline.request.params if baseline.request else None,
                },
                current_request={
                    "method": current.request.method if current.request else None,
                    "params": current.request.params if current.request else None,
                },
                baseline_response=(
                    {
                        k: v
                        for k, v in {
                            "result": getattr(baseline.response, "result", None),
                            "error": getattr(baseline.response, "error", None),
                        }.items()
                        if v is not None
                    }
                    if baseline.response
                    else {}
                ),
                current_response=(
                    {
                        k: v
                        for k, v in {
                            "result": getattr(current.response, "result", None),
                            "error": getattr(current.response, "error", None),
                        }.items()
                        if v is not None
                    }
                    if current.response
                    else {}
                ),
                request_diff=request_diff,
                response_diff=response_diff,
            )

        return None


__all__ = ["MCPDiff", "MCPDiffResult", "ModifiedInteraction"]
