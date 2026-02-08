"""VCR file format — Pydantic models for .vcr recording files.

The .vcr format captures complete MCP sessions including:
- Session metadata (timestamp, transport, client/server info)
- Initialize handshake
- All request/response/notification interactions in sequence
- Timing information for each interaction
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class JSONRPCMessage(BaseModel):
    """Base class for all JSON-RPC 2.0 messages."""

    jsonrpc: Literal["2.0"] = "2.0"

    class Config:
        extra = "allow"


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class JSONRPCRequest(JSONRPCMessage):
    """JSON-RPC 2.0 request message."""

    id: Union[str, int, float]
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None


class JSONRPCResponse(JSONRPCMessage):
    """JSON-RPC 2.0 response message."""

    id: Union[str, int, float]
    result: Optional[Dict[str, Any]] = None
    error: Optional[JSONRPCError] = None

    @field_validator("result", "error", mode="before")
    @classmethod
    def validate_result_error(cls, v: Any) -> Any:
        """Ensure result and error are mutually exclusive."""
        return v


class JSONRPCNotification(JSONRPCMessage):
    """JSON-RPC 2.0 notification message (no id)."""

    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None


class VCRInteraction(BaseModel):
    """Single request/response interaction in the VCR recording."""

    sequence: int = Field(description="Interaction sequence number starting from 0")
    timestamp: datetime = Field(description="When this interaction occurred (ISO 8601)")
    direction: Literal["client_to_server", "server_to_client"] = Field(
        description="Direction of the primary message"
    )
    request: JSONRPCRequest = Field(description="The request message")
    response: Optional[JSONRPCResponse] = Field(
        None, description="The response message, if any"
    )
    notifications: List[JSONRPCNotification] = Field(
        default_factory=list, description="Any notifications that occurred"
    )
    latency_ms: float = Field(
        description="Time in milliseconds between request and response"
    )


class VCRMetadata(BaseModel):
    """Metadata about the VCR recording session."""

    version: str = Field(description="VCR format version")
    recorded_at: datetime = Field(description="When the recording was made (ISO 8601)")
    transport: Literal["stdio", "sse"] = Field(
        description="Transport mechanism used (stdio or SSE)"
    )
    client_info: Dict[str, Any] = Field(
        default_factory=dict, description="Client implementation details"
    )
    server_info: Dict[str, Any] = Field(
        default_factory=dict, description="Server implementation details"
    )
    server_command: Optional[str] = Field(
        None, description="Command used to start the server"
    )
    server_args: List[str] = Field(
        default_factory=list, description="Arguments passed to server"
    )
    tags: Dict[str, str] = Field(
        default_factory=dict, description="Arbitrary tags for organization"
    )


class VCRSession(BaseModel):
    """Complete MCP session including initialization and interactions."""

    initialize_request: JSONRPCRequest = Field(
        description="The initialize request message"
    )
    initialize_response: JSONRPCResponse = Field(
        description="The initialize response message with server capabilities"
    )
    capabilities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Server capabilities extracted from initialize response",
    )
    interactions: List[VCRInteraction] = Field(
        default_factory=list, description="Sequence of interactions after initialize"
    )


class VCRRecording(BaseModel):
    """Top-level VCR recording model."""

    format_version: str = Field(
        default="1.0.0", description="VCR format version"
    )
    metadata: VCRMetadata = Field(description="Recording metadata")
    session: VCRSession = Field(description="Recorded MCP session")

    def save(self, path: str) -> None:
        """Save the recording to a JSON file.

        Args:
            path: File path to save to (typically .vcr extension)

        Raises:
            IOError: If the file cannot be written
        """
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    self.model_dump(mode="json", by_alias=False),
                    f,
                    indent=2,
                    default=str,
                )
        except (IOError, OSError) as e:
            raise IOError(f"Failed to save VCR recording to {path}: {e}") from e

    @classmethod
    def load(cls, path: str) -> "VCRRecording":
        """Load a recording from a JSON file.

        Args:
            path: File path to load from

        Returns:
            VCRRecording instance

        Raises:
            IOError: If the file cannot be read
            ValueError: If the file contains invalid data
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.model_validate(data)
        except (IOError, OSError) as e:
            raise IOError(f"Failed to read VCR recording from {path}: {e}") from e
        except ValueError as e:
            raise ValueError(f"Invalid VCR recording format in {path}: {e}") from e

    def to_json(self) -> str:
        """Convert the recording to a JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps(
            self.model_dump(mode="json", by_alias=False),
            indent=2,
            default=str,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "VCRRecording":
        """Create a recording from a JSON string.

        Args:
            json_str: JSON string to parse

        Returns:
            VCRRecording instance

        Raises:
            ValueError: If the JSON is invalid or doesn't match the schema
        """
        try:
            data = json.loads(json_str)
            return cls.model_validate(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in VCR recording: {e}") from e
        except ValueError as e:
            raise ValueError(f"Invalid VCR recording format: {e}") from e

    def add_interaction(self, interaction: VCRInteraction) -> None:
        """Add a new interaction to the recording.

        Args:
            interaction: VCRInteraction to add
        """
        self.session.interactions.append(interaction)

    @property
    def duration(self) -> float:
        """Calculate total duration of the recorded session in seconds.

        Returns:
            Duration in seconds (0.0 if no interactions)
        """
        if not self.session.interactions:
            return 0.0

        first = self.session.interactions[0].timestamp
        last = self.session.interactions[-1].timestamp

        return (last - first).total_seconds()

    @property
    def interaction_count(self) -> int:
        """Get the number of interactions in the recording.

        Returns:
            Number of interactions
        """
        return len(self.session.interactions)
