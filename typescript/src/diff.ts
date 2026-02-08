/**
 * MCP Diff — compare two VCR recordings and detect breaking changes.
 *
 * Identifies added, removed, and modified interactions between recordings.
 */

import { promises as fs } from "fs";
import { VCRRecording, VCRInteraction, loadVCRRecording } from "./core/format.js";

export interface DiffChange {
  type: "added" | "removed" | "modified";
  method: string;
  baseline?: VCRInteraction;
  current?: VCRInteraction;
  details?: string;
  breaking: boolean;
}

export interface DiffResult {
  added: DiffChange[];
  removed: DiffChange[];
  modified: DiffChange[];
  breaking_changes: DiffChange[];
  summary: {
    total_changes: number;
    breaking_count: number;
    added_count: number;
    removed_count: number;
    modified_count: number;
  };
}

/**
 * Compare two VCR recordings and identify changes.
 */
export class MCPDiff {
  /**
   * Compare two recordings and return differences.
   */
  static compare(baseline: VCRRecording, current: VCRRecording): DiffResult {
    const added: DiffChange[] = [];
    const removed: DiffChange[] = [];
    const modified: DiffChange[] = [];
    const breaking: DiffChange[] = [];

    // Index interactions by method
    const baselineByMethod = this.indexByMethod(baseline);
    const currentByMethod = this.indexByMethod(current);

    // Find added and modified interactions
    for (const [method, currentInteractions] of currentByMethod.entries()) {
      const baselineInteractions = baselineByMethod.get(method) || [];

      if (baselineInteractions.length === 0) {
        // Method is new (potentially breaking)
        for (const interaction of currentInteractions) {
          const change: DiffChange = {
            type: "added",
            method,
            current: interaction,
            breaking: false,
          };
          added.push(change);
        }
        continue;
      }

      // Compare interactions for this method
      for (const currentInteraction of currentInteractions) {
        const matchingBaseline = this.findMatchingInteraction(
          currentInteraction,
          baselineInteractions
        );

        if (!matchingBaseline) {
          // New interaction for existing method
          const change: DiffChange = {
            type: "added",
            method,
            current: currentInteraction,
            breaking: false,
          };
          added.push(change);
          continue;
        }

        // Compare request and response
        const requestDiff = this.deepDiff(
          matchingBaseline.request,
          currentInteraction.request
        );
        const responseDiff = this.deepDiff(
          matchingBaseline.response,
          currentInteraction.response
        );

        if (requestDiff.length > 0 || responseDiff.length > 0) {
          const isBreaking = this.isBreakingChange(
            matchingBaseline,
            currentInteraction
          );

          const change: DiffChange = {
            type: "modified",
            method,
            baseline: matchingBaseline,
            current: currentInteraction,
            details: this.formatDiffDetails(requestDiff, responseDiff),
            breaking: isBreaking,
          };

          modified.push(change);

          if (isBreaking) {
            breaking.push(change);
          }
        }
      }
    }

    // Find removed interactions
    for (const [method, baselineInteractions] of baselineByMethod.entries()) {
      const currentInteractions = currentByMethod.get(method) || [];

      if (currentInteractions.length === 0) {
        // Method removed (breaking)
        for (const interaction of baselineInteractions) {
          const change: DiffChange = {
            type: "removed",
            method,
            baseline: interaction,
            breaking: true,
          };
          removed.push(change);
          breaking.push(change);
        }
      }
    }

    return {
      added,
      removed,
      modified,
      breaking_changes: breaking,
      summary: {
        total_changes: added.length + removed.length + modified.length,
        breaking_count: breaking.length,
        added_count: added.length,
        removed_count: removed.length,
        modified_count: modified.length,
      },
    };
  }

  /**
   * Load two recordings from files and compare them.
   */
  static async compareFiles(
    baselinePath: string,
    currentPath: string
  ): Promise<DiffResult> {
    const [baselineContent, currentContent] = await Promise.all([
      fs.readFile(baselinePath, "utf-8"),
      fs.readFile(currentPath, "utf-8"),
    ]);

    const baseline = loadVCRRecording(JSON.parse(baselineContent));
    const current = loadVCRRecording(JSON.parse(currentContent));

    return this.compare(baseline, current);
  }

  private static indexByMethod(
    recording: VCRRecording
  ): Map<string, VCRInteraction[]> {
    const index = new Map<string, VCRInteraction[]>();

    for (const interaction of recording.session.interactions) {
      const method = interaction.request.method;
      if (!index.has(method)) {
        index.set(method, []);
      }
      index.get(method)!.push(interaction);
    }

    return index;
  }

  private static findMatchingInteraction(
    interaction: VCRInteraction,
    candidates: VCRInteraction[]
  ): VCRInteraction | null {
    // Try exact params match first
    for (const candidate of candidates) {
      if (
        JSON.stringify(interaction.request.params) ===
        JSON.stringify(candidate.request.params)
      ) {
        return candidate;
      }
    }

    // Fall back to first interaction with same method
    return candidates[0] || null;
  }

  private static deepDiff(a: unknown, b: unknown): string[] {
    const diffs: string[] = [];

    if (typeof a !== typeof b) {
      diffs.push(`Type changed: ${typeof a} → ${typeof b}`);
      return diffs;
    }

    if (a === null || b === null) {
      if (a !== b) {
        diffs.push(`Value changed: ${a} → ${b}`);
      }
      return diffs;
    }

    if (typeof a === "object" && typeof b === "object") {
      const aObj = a as Record<string, unknown>;
      const bObj = b as Record<string, unknown>;

      // Check for added/removed keys
      const aKeys = new Set(Object.keys(aObj));
      const bKeys = new Set(Object.keys(bObj));

      for (const key of aKeys) {
        if (!bKeys.has(key)) {
          diffs.push(`Key removed: ${key}`);
        }
      }

      for (const key of bKeys) {
        if (!aKeys.has(key)) {
          diffs.push(`Key added: ${key}`);
        } else {
          // Recursively check values
          const subDiffs = this.deepDiff(aObj[key], bObj[key]);
          for (const diff of subDiffs) {
            diffs.push(`${key}.${diff}`);
          }
        }
      }
    } else if (a !== b) {
      diffs.push(`Value changed: ${JSON.stringify(a)} → ${JSON.stringify(b)}`);
    }

    return diffs;
  }

  private static isBreakingChange(
    baseline: VCRInteraction,
    current: VCRInteraction
  ): boolean {
    // Success → error is breaking
    if (baseline.response?.result && current.response?.error) {
      return true;
    }

    // Missing required response fields is breaking
    if (baseline.response?.result && current.response?.result) {
      const baselineKeys = Object.keys(baseline.response.result);
      const currentKeys = Object.keys(current.response.result);

      for (const key of baselineKeys) {
        if (!currentKeys.includes(key)) {
          return true;
        }
      }
    }

    // Error code change is potentially breaking
    if (
      baseline.response?.error &&
      current.response?.error &&
      baseline.response.error.code !== current.response.error.code
    ) {
      return true;
    }

    return false;
  }

  private static formatDiffDetails(
    requestDiff: string[],
    responseDiff: string[]
  ): string {
    const parts: string[] = [];

    if (requestDiff.length > 0) {
      parts.push(`Request: ${requestDiff.join(", ")}`);
    }

    if (responseDiff.length > 0) {
      parts.push(`Response: ${responseDiff.join(", ")}`);
    }

    return parts.join("; ");
  }
}
