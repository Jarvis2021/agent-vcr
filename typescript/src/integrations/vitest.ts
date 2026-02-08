/**
 * Vitest integration for Agent VCR
 *
 * Provides fixtures and utilities for using VCR recordings in Vitest tests.
 */

import { MCPRecorder, MCPReplayer } from "../index.js";
import { VCRRecording } from "../core/format.js";
import { MatchStrategy } from "../core/matcher.js";

export interface VCRCassetteOptions {
  name: string;
  dir?: string;
  recordMode?: "once" | "new_episodes" | "all";
  matchStrategy?: MatchStrategy;
  strict?: boolean;
}

/**
 * VCR cassette context manager for Vitest tests.
 */
export class VCRCassette {
  private recorder: MCPRecorder | null = null;
  private replayer: MCPReplayer | null = null;
  private options: VCRCassetteOptions;
  private cassettePath: string;

  constructor(options: VCRCassetteOptions) {
    this.options = {
      dir: "fixtures/cassettes",
      recordMode: "once",
      matchStrategy: "method_and_params",
      strict: false,
      ...options,
    };
    this.cassettePath = `${this.options.dir}/${this.options.name}.vcr`;
  }

  /**
   * Start the cassette (load existing or prepare to record).
   */
  async use(serverConfig?: {
    command: string;
    args?: string[];
    transport?: "stdio" | "sse";
  }): Promise<MCPReplayer> {
    const fs = await import("fs/promises");

    // Check if cassette exists
    let exists = false;
    try {
      await fs.access(this.cassettePath);
      exists = true;
    } catch {
      exists = false;
    }

    if (exists && this.options.recordMode === "once") {
      // Load and replay existing cassette
      this.replayer = await MCPReplayer.fromFile(
        this.cassettePath,
        this.options.matchStrategy,
        this.options.strict
      );
      return this.replayer;
    }

    if (!serverConfig) {
      throw new Error(
        "Server config required for recording mode, but no cassette exists"
      );
    }

    // Record new cassette
    this.recorder = new MCPRecorder({
      transport: serverConfig.transport || "stdio",
      command: serverConfig.command,
      args: serverConfig.args,
    });

    await this.recorder.start();

    // Return a replayer that will be populated after recording
    throw new Error(
      "Recording mode not yet supported in Vitest integration - use CLI to record cassettes"
    );
  }

  /**
   * Stop and save the cassette.
   */
  async eject(): Promise<void> {
    if (this.recorder) {
      const recording = await this.recorder.stop();
      await this.recorder.save(recording, this.cassettePath);
      this.recorder = null;
    }

    if (this.replayer) {
      this.replayer.reset();
      this.replayer = null;
    }
  }

  /**
   * Get the current replayer instance.
   */
  getReplayer(): MCPReplayer | null {
    return this.replayer;
  }
}

/**
 * Vitest helper to use a VCR cassette in a test.
 */
export async function useVCRCassette(
  options: VCRCassetteOptions,
  serverConfig?: {
    command: string;
    args?: string[];
    transport?: "stdio" | "sse";
  }
): Promise<{ replayer: MCPReplayer; cassette: VCRCassette }> {
  const cassette = new VCRCassette(options);
  const replayer = await cassette.use(serverConfig);

  return { replayer, cassette };
}

/**
 * Create a Vitest fixture for VCR cassettes.
 */
export function createVCRFixture() {
  return {
    vcr: async (
      { task }: { task: { name: string } },
      use: (cassette: VCRCassette) => Promise<void>
    ) => {
      const cassette = new VCRCassette({
        name: task.name.replace(/\s+/g, "-").toLowerCase(),
        dir: "tests/fixtures/cassettes",
      });

      await use(cassette);
      await cassette.eject();
    },
  };
}

/**
 * Custom Vitest matcher for VCR recordings.
 */
export function expectRecordingToMatch(
  received: VCRRecording,
  expected: VCRRecording
): void {
  const receivedInteractions = received.session.interactions.length;
  const expectedInteractions = expected.session.interactions.length;

  if (receivedInteractions !== expectedInteractions) {
    throw new Error(
      `Expected ${expectedInteractions} interactions, received ${receivedInteractions}`
    );
  }

  // Compare method signatures
  for (let i = 0; i < receivedInteractions; i++) {
    const r = received.session.interactions[i];
    const e = expected.session.interactions[i];

    if (r.request.method !== e.request.method) {
      throw new Error(
        `Interaction ${i}: expected method ${e.request.method}, received ${r.request.method}`
      );
    }
  }
}

// Example usage in a Vitest test:
//
// import { describe, it, expect } from 'vitest';
// import { useVCRCassette } from '@agent-vcr/vitest';
//
// describe('My MCP client', () => {
//   it('should handle requests correctly', async () => {
//     const { replayer, cassette } = await useVCRCassette({
//       name: 'my-test-cassette',
//       dir: 'tests/fixtures/cassettes',
//     });
//
//     try {
//       const response = replayer.handleRequest({
//         jsonrpc: '2.0',
//         id: 1,
//         method: 'tools/list',
//       });
//
//       expect(response).toBeDefined();
//     } finally {
//       await cassette.eject();
//     }
//   });
// });
