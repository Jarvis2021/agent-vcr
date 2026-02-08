"""Agent VCR CLI interface for recording, replaying, and diffing MCP interactions."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any

# Demo requests sent automatically when --demo is used (Lab 1 / tutorial).
DEMO_RECORD_REQUESTS = [
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"tutorial","version":"1.0.0"}}}',
    '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"add","arguments":{"a":15,"b":27}}}',
    '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"multiply","arguments":{"a":6,"b":7}}}',
]

import click
from rich.console import Console
from rich.json import JSON
from rich.table import Table
from rich.syntax import Syntax

from agent_vcr.core.format import VCRRecording
from agent_vcr.diff import MCPDiff, MCPDiffResult
from agent_vcr.recorder import MCPRecorder
from agent_vcr.replayer import MCPReplayer

console = Console()

__version__ = "0.1.0"


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Agent VCR - Record, replay, and diff MCP JSON-RPC 2.0 interactions."""
    pass


@cli.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    required=True,
    help="Transport protocol: stdio or sse",
)
@click.option(
    "--server-command",
    default=None,
    help="Command to start the MCP server (for stdio transport)",
)
@click.option(
    "--server-args",
    multiple=True,
    default=[],
    help="Arguments to pass to the server command",
)
@click.option(
    "--server-url",
    default=None,
    help="URL of the MCP server (for sse transport)",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output path for the VCR recording",
)
@click.option(
    "--method-filter",
    multiple=True,
    default=[],
    help="Filter to only record specific methods (can be specified multiple times)",
)
@click.option(
    "--tag",
    "tags",
    multiple=True,
    help="Add tags to the recording (key=value, can be specified multiple times)",
)
@click.option(
    "--demo",
    is_flag=True,
    help="Send tutorial requests automatically and stop (no pasting). Stdio only.",
)
@click.option(
    "--pending-timeout",
    type=float,
    default=60.0,
    help="Evict pending requests with no response after this many seconds (0=disable). Default: 60.",
)
@click.option(
    "--max-interactions",
    type=int,
    default=0,
    help="Stop recording after this many interactions (0=unlimited). Default: 0.",
)
@click.option(
    "--session-id",
    default=None,
    help="Optional session id for multi-session correlation (see SCALING.md).",
)
@click.option(
    "--endpoint-id",
    default=None,
    help="Optional endpoint id for multi-MCP routing (e.g. filesystem, github).",
)
@click.option(
    "--agent-id",
    default=None,
    help="Optional agent id for agent-to-agent flows (e.g. search-agent).",
)
def record(
    transport: str,
    server_command: str | None,
    server_args: tuple[str, ...],
    server_url: str | None,
    output: str,
    method_filter: tuple[str, ...],
    tags: tuple[str, ...],
    demo: bool,
    pending_timeout: float,
    max_interactions: int,
    session_id: str | None,
    endpoint_id: str | None,
    agent_id: str | None,
) -> None:
    """Record MCP interactions to a VCR file.

    Example:
        agent-vcr record --transport stdio --server-command "node server.js" --output session.vcr
        agent-vcr record --transport stdio --server-command "python demo/servers/calculator_v1.py" -o out.vcr --demo
        agent-vcr record --transport sse --server-url http://localhost:3000/sse --output session.vcr
    """
    try:
        # Validate options
        if transport == "stdio" and not server_command:
            raise click.ClickException("--server-command is required for stdio transport")
        if transport == "sse" and not server_url:
            raise click.ClickException("--server-url is required for sse transport")
        if demo and transport != "stdio":
            raise click.ClickException("--demo is only supported with --transport stdio")

        # Parse tags
        tag_dict = {}
        for tag in tags:
            if "=" not in tag:
                raise click.ClickException(f"Invalid tag format: {tag}. Use key=value")
            key, value = tag.split("=", 1)
            tag_dict[key] = value

        # Parse server command — split "python demo/server.py" into
        # command="python" and args=["demo/server.py"] so that
        # asyncio.create_subprocess_exec receives them as separate arguments.
        parsed_command = server_command
        parsed_args = list(server_args)
        if server_command:
            parts = shlex.split(server_command)
            parsed_command = parts[0]
            parsed_args = parts[1:] + parsed_args

        # For --demo we feed client input from a pipe instead of terminal
        client_stdin_fd: int | None = None
        if demo:
            r_fd, w_fd = os.pipe()
            client_stdin_fd = r_fd

        # Create recorder
        recorder = MCPRecorder(
            transport=transport,
            server_command=parsed_command,
            server_args=parsed_args,
            server_url=server_url,
            metadata_tags=tag_dict,
            filter_methods=set(method_filter) if method_filter else None,
            client_stdin_fd=client_stdin_fd,
            pending_timeout_seconds=pending_timeout,
            max_interactions=max_interactions,
            session_id=session_id,
            endpoint_id=endpoint_id,
            agent_id=agent_id,
        )

        console.print(f"[bold green]Starting recording[/bold green]")
        console.print(f"  Transport: {transport}")
        if server_command:
            console.print(f"  Server: {server_command}")
        if server_url:
            console.print(f"  Server URL: {server_url}")
        console.print(f"  Output: {output}")
        if method_filter:
            console.print(f"  Methods: {', '.join(method_filter)}")
        if demo:
            console.print("  [dim]Demo mode: sending tutorial requests automatically[/dim]")
        console.print()
        if not demo:
            console.print("[yellow]Press Ctrl+C to stop recording[/yellow]")
        console.print()

        if demo:
            # Send demo requests on a pipe, then signal stop after a delay
            async def demo_driver(write_fd: int) -> None:
                await asyncio.sleep(1.5)
                for line in DEMO_RECORD_REQUESTS:
                    os.write(write_fd, (line + "\n").encode("utf-8"))
                try:
                    os.close(write_fd)
                except OSError:
                    pass
                await asyncio.sleep(4)
                recorder.request_stop()

            async def run_demo() -> None:
                task_record = asyncio.create_task(recorder.record(output))
                task_driver = asyncio.create_task(demo_driver(w_fd))
                await asyncio.gather(task_record, task_driver)

            asyncio.run(run_demo())
            console.print("[green]Demo recording saved.[/green]")
        else:
            # Run recording (interactive)
            asyncio.run(recorder.record(output))

    except click.ClickException:
        raise
    except KeyboardInterrupt:
        console.print("\n[yellow]Recording interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        raise click.ClickException(f"Recording failed: {e}")


@cli.command()
@click.option(
    "--file",
    "-f",
    required=True,
    type=click.Path(exists=True),
    help="Path to the VCR recording file",
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    required=True,
    help="Transport protocol: stdio or sse",
)
@click.option(
    "--match-strategy",
    type=click.Choice(["method_and_params", "method_only"]),
    default="method_and_params",
    help="Strategy for matching incoming requests to recorded interactions",
)
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind the replay server to (for sse transport)",
)
@click.option(
    "--port",
    type=int,
    default=3100,
    help="Port to bind the replay server to (for sse transport)",
)
def replay(
    file: str,
    transport: str,
    match_strategy: str,
    host: str,
    port: int,
) -> None:
    """Replay MCP interactions from a VCR file.

    Example:
        agent-vcr replay --file session.vcr --transport stdio
        agent-vcr replay --file session.vcr --transport sse --host 127.0.0.1 --port 3100
    """
    try:
        console.print(f"[bold green]Loading recording[/bold green]: {file}")

        # Load and validate recording
        replayer = MCPReplayer.from_file(file, match_strategy=match_strategy)

        console.print(f"[bold green]Loaded recording[/bold green]")
        console.print(f"  Interactions: {len(replayer.recording.session.interactions)}")
        console.print(f"  Match strategy: {match_strategy}")
        console.print()

        if transport == "stdio":
            console.print("[bold cyan]Starting replay server on stdio[/bold cyan]")
            console.print("[yellow]Waiting for requests...[/yellow]")
            asyncio.run(replayer.serve_stdio())
        elif transport == "sse":
            console.print(f"[bold cyan]Starting replay server[/bold cyan]")
            console.print(f"  URL: http://{host}:{port}/sse")
            console.print("[yellow]Waiting for requests...[/yellow]")
            asyncio.run(replayer.serve_sse(host, port))

    except KeyboardInterrupt:
        console.print("\n[yellow]Replay interrupted by user[/yellow]")
        sys.exit(0)
    except FileNotFoundError:
        raise click.ClickException(f"Recording file not found: {file}")
    except Exception as e:
        raise click.ClickException(f"Replay failed: {e}")


@cli.command()
@click.argument("baseline", type=click.Path(exists=True))
@click.argument("current", type=click.Path(exists=True))
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format for the diff report",
)
@click.option(
    "--fail-on-breaking",
    is_flag=True,
    help="Exit with code 1 if breaking changes are detected",
)
def diff(baseline: str, current: str, format: str, fail_on_breaking: bool) -> None:
    """Compare two VCR recordings and detect differences.

    Example:
        agent-vcr diff baseline.vcr current.vcr
        agent-vcr diff baseline.vcr current.vcr --format json --fail-on-breaking
    """
    try:
        console.print(f"[bold green]Loading recordings[/bold green]")
        console.print(f"  Baseline: {baseline}")
        console.print(f"  Current:  {current}")

        # Load recordings
        baseline_recording = VCRRecording.load(baseline)
        current_recording = VCRRecording.load(current)

        console.print()
        console.print("[bold cyan]Comparing interactions...[/bold cyan]")

        # Perform diff
        diff_result = MCPDiff.compare(baseline_recording, current_recording)

        # Output results
        if format == "json":
            _output_diff_json(diff_result)
        else:
            _output_diff_text(diff_result)

        # Handle exit code
        if fail_on_breaking and diff_result.breaking_changes:
            sys.exit(1)

    except FileNotFoundError as e:
        raise click.ClickException(f"Recording file not found: {e}")
    except Exception as e:
        raise click.ClickException(f"Diff failed: {e}")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--format",
    type=click.Choice(["text", "json", "table"]),
    default="text",
    help="Output format for inspection",
)
def inspect(file: str, format: str) -> None:
    """Inspect the contents of a VCR recording.

    Example:
        agent-vcr inspect session.vcr
        agent-vcr inspect session.vcr --format table
        agent-vcr inspect session.vcr --format json
    """
    try:
        console.print(f"[bold green]Loading recording[/bold green]: {file}")

        # Load recording
        recording = VCRRecording.load(file)

        console.print()

        if format == "json":
            _output_inspect_json(recording)
        elif format == "table":
            _output_inspect_table(recording)
        else:
            _output_inspect_text(recording)

    except FileNotFoundError:
        raise click.ClickException(f"Recording file not found: {file}")
    except Exception as e:
        raise click.ClickException(f"Inspection failed: {e}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Output path for the converted JSON file",
)
def convert(input_file: str, output: str) -> None:
    """Convert a VCR recording to plain JSON format.

    Example:
        agent-vcr convert session.vcr --output session.json
    """
    try:
        console.print(f"[bold green]Loading recording[/bold green]: {input_file}")

        # Load recording
        recording = VCRRecording.load(input_file)

        console.print(f"[bold green]Converting to JSON[/bold green]")

        # Convert to dict and write JSON
        output_data = _vcr_recording_to_dict(recording)

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        console.print(f"[bold green]Conversion successful[/bold green]")
        console.print(f"  Output: {output}")
        console.print(f"  Interactions: {len(recording.session.interactions)}")

    except FileNotFoundError:
        raise click.ClickException(f"Recording file not found: {input_file}")
    except Exception as e:
        raise click.ClickException(f"Conversion failed: {e}")


def _output_diff_text(diff_result: MCPDiffResult) -> None:
    """Output diff results in text format."""
    console.print()
    console.print(diff_result.summary())
    console.print()

    if diff_result.breaking_changes:
        console.print("[bold red]Breaking Changes Detected:[/bold red]")
        for change in diff_result.breaking_changes:
            console.print(f"  • {change}")
        console.print()

    if diff_result.is_identical:
        console.print("[bold green]✓ Recordings are identical[/bold green]")
    elif diff_result.is_compatible:
        console.print("[bold yellow]⚠ Recordings are compatible but differ[/bold yellow]")
    else:
        console.print("[bold red]✗ Recordings are incompatible[/bold red]")

    # Show detailed diff if not identical
    if not diff_result.is_identical:
        console.print()
        diff_result.print_detailed()


def _output_diff_json(diff_result: MCPDiffResult) -> None:
    """Output diff results in JSON format."""
    output = {
        "is_identical": diff_result.is_identical,
        "is_compatible": diff_result.is_compatible,
        "breaking_changes": diff_result.breaking_changes,
        "summary": diff_result.summary(),
    }
    console.print(JSON.from_str(json.dumps(output, indent=2)))


def _output_inspect_text(recording: VCRRecording) -> None:
    """Output recording inspection in text format."""
    console.print("[bold cyan]Metadata[/bold cyan]")
    console.print(f"  Version: {recording.metadata.version}")
    console.print(f"  Recorded: {recording.metadata.recorded_at}")
    console.print(f"  Tags: {json.dumps(recording.metadata.tags)}")

    console.print()
    console.print("[bold cyan]Statistics[/bold cyan]")
    console.print(f"  Total interactions: {len(recording.session.interactions)}")

    # Collect methods
    methods = {}
    for interaction in recording.session.interactions:
        method = interaction.request.method
        methods[method] = methods.get(method, 0) + 1

    console.print(f"  Methods used: {len(methods)}")
    for method, count in sorted(methods.items()):
        console.print(f"    • {method}: {count}")

    # Timeline
    if recording.session.interactions:
        console.print()
        console.print("[bold cyan]Timeline[/bold cyan]")
        for i, interaction in enumerate(recording.session.interactions[:10], 1):
            method = interaction.request.method
            console.print(f"  {i}. {method}")
        if len(recording.session.interactions) > 10:
            console.print(f"  ... and {len(recording.session.interactions) - 10} more")


def _output_inspect_json(recording: VCRRecording) -> None:
    """Output recording inspection in JSON format."""
    methods = {}
    for interaction in recording.session.interactions:
        method = interaction.request.method
        methods[method] = methods.get(method, 0) + 1

    output = {
        "metadata": {
            "version": recording.metadata.version,
            "recorded_at": str(recording.metadata.recorded_at),
            "tags": recording.metadata.tags,
        },
        "statistics": {
            "total_interactions": len(recording.session.interactions),
            "methods": methods,
        },
    }
    console.print(JSON.from_str(json.dumps(output, indent=2)))


def _output_inspect_table(recording: VCRRecording) -> None:
    """Output recording inspection in table format."""
    console.print("[bold cyan]Metadata[/bold cyan]")
    metadata_table = Table(show_header=False)
    metadata_table.add_row("Version", recording.metadata.version)
    metadata_table.add_row("Recorded", str(recording.metadata.recorded_at))
    metadata_table.add_row("Tags", json.dumps(recording.metadata.tags))
    console.print(metadata_table)

    console.print()
    console.print("[bold cyan]Interaction Methods[/bold cyan]")

    methods = {}
    for interaction in recording.session.interactions:
        method = interaction.request.method
        methods[method] = methods.get(method, 0) + 1

    table = Table(title="Methods Summary")
    table.add_column("Method", style="cyan")
    table.add_column("Count", style="magenta", justify="right")

    for method, count in sorted(methods.items()):
        table.add_row(method, str(count))

    console.print(table)

    console.print()
    console.print(f"[bold cyan]Total Interactions: {len(recording.session.interactions)}[/bold cyan]")


def _vcr_recording_to_dict(recording: VCRRecording) -> dict[str, Any]:
    """Convert a VCRRecording to a dictionary for JSON serialization."""
    return {
        "version": recording.metadata.version,
        "recorded_at": str(recording.metadata.recorded_at),
        "tags": recording.metadata.tags,
        "interactions": [
            {
                "request": interaction.request.model_dump(),
                "response": interaction.response.model_dump() if interaction.response else None,
                "timestamp": interaction.timestamp.isoformat() if interaction.timestamp else None,
            }
            for interaction in recording.session.interactions
        ],
    }


def main() -> None:
    """Entry point for the Agent VCR CLI."""
    cli()


if __name__ == "__main__":
    main()
