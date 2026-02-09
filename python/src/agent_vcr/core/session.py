"""Session manager for tracking recording state and managing VCR lifecycle."""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from agent_vcr.core.format import (
    JSONRPCNotification,
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
    VCRMetadata,
    VCRRecording,
    VCRSession,
)


RecordingState = Literal["idle", "recording", "replaying"]


class SessionManager:
    """Manages VCR recording session lifecycle and state tracking.

    Tracks:
    - Current recording state (idle, recording, replaying)
    - Interaction sequence numbering
    - Session initialization handshake
    - Timing and latency information
    """

    def __init__(self) -> None:
        """Initialize the session manager in idle state."""
        self._state: RecordingState = "idle"
        self._current_recording: Optional[VCRRecording] = None
        self._interaction_counter = 0
        self._last_request_time: Optional[datetime] = None

    @property
    def is_recording(self) -> bool:
        """Check if currently recording.

        Returns:
            True if in recording state
        """
        return self._state == "recording"

    @property
    def is_replaying(self) -> bool:
        """Check if currently replaying.

        Returns:
            True if in replaying state
        """
        return self._state == "replaying"

    @property
    def current_state(self) -> RecordingState:
        """Get the current recording state.

        Returns:
            Current state (idle, recording, or replaying)
        """
        return self._state

    @property
    def current_recording(self) -> Optional[VCRRecording]:
        """Get the current VCR recording being built.

        Returns:
            VCRRecording if recording, None otherwise
        """
        return self._current_recording

    def start_recording(
        self,
        metadata: VCRMetadata,
        initialize_request: JSONRPCRequest,
        initialize_response: JSONRPCResponse,
        capabilities: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Start a new recording session.

        Creates a new VCRRecording with the provided metadata and initialization
        handshake. Subsequent calls to record_interaction() will add to this recording.

        Args:
            metadata: VCRMetadata with transport, client/server info, etc.
            initialize_request: The initialize request from the client
            initialize_response: The initialize response from the server
            capabilities: Server capabilities (extracted from response if needed)

        Raises:
            RuntimeError: If already recording
        """
        if self._state == "recording":
            raise RuntimeError("Already recording. Call stop_recording() first.")

        self._state = "recording"
        self._interaction_counter = 0
        self._last_request_time = None

        # Extract capabilities from response if not provided
        if capabilities is None:
            capabilities = {}
            if initialize_response.result:
                capabilities = initialize_response.result.get("capabilities", {})

        # Create the session with initialization messages
        session = VCRSession(
            initialize_request=initialize_request,
            initialize_response=initialize_response,
            capabilities=capabilities,
            interactions=[],
        )

        # Create the recording
        self._current_recording = VCRRecording(
            format_version="1.0.0",
            metadata=metadata,
            session=session,
        )

    def stop_recording(self) -> VCRRecording:
        """Stop recording and return the completed recording.

        Returns:
            The completed VCRRecording

        Raises:
            RuntimeError: If not currently recording
        """
        if self._state != "recording":
            raise RuntimeError(
                f"Not recording. Current state is '{self._state}'. "
                "Call start_recording() first."
            )

        if self._current_recording is None:
            raise RuntimeError("No recording in progress (internal error)")

        recording = self._current_recording
        self._state = "idle"
        self._current_recording = None
        self._interaction_counter = 0
        self._last_request_time = None

        return recording

    def record_interaction(
        self,
        request: JSONRPCRequest,
        response: Optional[JSONRPCResponse] = None,
        notifications: Optional[List[JSONRPCNotification]] = None,
        request_timestamp: Optional[float] = None,
    ) -> VCRInteraction:
        """Record a single request/response interaction.

        Args:
            request: The request message
            response: The response message (optional)
            notifications: List of notification messages (optional)
            request_timestamp: Optional Unix timestamp when the request was received (for accurate per-request latency).

        Returns:
            The created VCRInteraction

        Raises:
            RuntimeError: If not currently recording
            ValueError: If notifications is not a list
        """
        if self._state != "recording":
            raise RuntimeError(
                f"Not recording. Current state is '{self._state}'. "
                "Call start_recording() first."
            )

        if self._current_recording is None:
            raise RuntimeError("No recording in progress (internal error)")

        if notifications is None:
            notifications = []
        elif not isinstance(notifications, list):
            raise ValueError("notifications must be a list of JSONRPCNotification")

        # Calculate latency: per-request when request_timestamp given, else time since last request
        now = datetime.now()
        latency_ms = 0.0

        if response is not None:
            if request_timestamp is not None:
                latency_ms = (time.time() - request_timestamp) * 1000.0
            elif self._last_request_time is not None:
                delta = now - self._last_request_time
                latency_ms = delta.total_seconds() * 1000.0

        self._last_request_time = now

        # Determine direction (client_to_server for requests, server_to_client for responses)
        direction = "client_to_server" if response is None else "server_to_client"

        # Create the interaction
        interaction = VCRInteraction(
            sequence=self._interaction_counter,
            timestamp=now,
            direction=direction,
            request=request,
            response=response,
            notifications=notifications,
            latency_ms=latency_ms,
        )

        self._interaction_counter += 1
        self._current_recording.add_interaction(interaction)

        return interaction

    async def record_interaction_async(
        self,
        request: JSONRPCRequest,
        response: Optional[JSONRPCResponse] = None,
        notifications: Optional[List[JSONRPCNotification]] = None,
        request_timestamp: Optional[float] = None,
    ) -> VCRInteraction:
        """Record a single interaction asynchronously.

        This is a convenience wrapper around record_interaction() for async contexts.

        Args:
            request: The request message
            response: The response message (optional)
            notifications: List of notification messages (optional)
            request_timestamp: Optional Unix timestamp when the request was received

        Returns:
            The created VCRInteraction

        Raises:
            RuntimeError: If not currently recording
            ValueError: If notifications is not a list
        """
        return await asyncio.to_thread(
            self.record_interaction, request, response, notifications, request_timestamp
        )

    def reset(self) -> None:
        """Reset the session manager to idle state.

        Discards any current recording in progress.
        """
        self._state = "idle"
        self._current_recording = None
        self._interaction_counter = 0
        self._last_request_time = None

    def get_interaction_count(self) -> int:
        """Get the number of interactions recorded so far.

        Returns:
            Number of interactions in current recording, or 0 if not recording
        """
        if self._current_recording is None:
            return 0
        return self._current_recording.interaction_count

    def get_recorded_duration(self) -> float:
        """Get the duration of the current recording so far.

        Returns:
            Duration in seconds, or 0.0 if not recording
        """
        if self._current_recording is None:
            return 0.0
        return self._current_recording.duration
