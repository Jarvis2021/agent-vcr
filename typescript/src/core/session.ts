/**
 * Session management for VCR recording lifecycle.
 *
 * Manages state transitions: idle → recording → idle
 */

import {
  VCRRecording,
  VCRInteraction,
  VCRMetadata,
  JSONRPCRequest,
  JSONRPCResponse,
  JSONRPCNotification,
  createVCRRecording,
} from "./format.js";

type SessionState = "idle" | "recording";

/**
 * Manages the lifecycle of a VCR recording session.
 */
export class SessionManager {
  private state: SessionState = "idle";
  private recording: VCRRecording | null = null;
  private sequenceNumber = 0;
  private lastTimestamp: Date | null = null;

  /**
   * Start a new recording session.
   */
  startRecording(
    metadata: Partial<VCRMetadata>,
    initRequest: JSONRPCRequest,
    initResponse: JSONRPCResponse
  ): void {
    if (this.state === "recording") {
      throw new Error("Recording already in progress");
    }

    this.recording = createVCRRecording(metadata, initRequest, initResponse);
    this.sequenceNumber = 0;
    this.lastTimestamp = new Date();
    this.state = "recording";
  }

  /**
   * Record a single request/response interaction.
   */
  recordInteraction(
    request: JSONRPCRequest,
    response: JSONRPCResponse | null,
    notifications: JSONRPCNotification[] = []
  ): void {
    if (this.state !== "recording") {
      throw new Error("No recording in progress");
    }

    if (!this.recording) {
      throw new Error("Recording not initialized");
    }

    const now = new Date();
    const latencyMs = this.lastTimestamp
      ? now.getTime() - this.lastTimestamp.getTime()
      : 0;

    const interaction: VCRInteraction = {
      sequence: this.sequenceNumber++,
      timestamp: now.toISOString(),
      direction: "client_to_server",
      request,
      response: response ?? undefined,
      notifications,
      latency_ms: latencyMs,
    };

    this.recording.session.interactions.push(interaction);
    this.lastTimestamp = now;
  }

  /**
   * Stop recording and return the completed recording.
   */
  stopRecording(): VCRRecording {
    if (this.state !== "recording") {
      throw new Error("No recording in progress");
    }

    if (!this.recording) {
      throw new Error("Recording not initialized");
    }

    const completed = this.recording;
    this.recording = null;
    this.state = "idle";
    this.sequenceNumber = 0;
    this.lastTimestamp = null;

    return completed;
  }

  /**
   * Check if currently recording.
   */
  isRecording(): boolean {
    return this.state === "recording";
  }

  /**
   * Get the current recording (if any).
   */
  getCurrentRecording(): VCRRecording | null {
    return this.recording;
  }

  /**
   * Reset the session manager to idle state.
   */
  reset(): void {
    this.state = "idle";
    this.recording = null;
    this.sequenceNumber = 0;
    this.lastTimestamp = null;
  }
}
