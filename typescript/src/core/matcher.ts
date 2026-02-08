/**
 * Request matching strategies for replaying VCR interactions.
 *
 * Matchers determine which recorded interaction should respond to an incoming request.
 */

import { JSONRPCRequest, VCRInteraction } from "./format.js";

export type MatchStrategy =
  | "exact"
  | "method"
  | "method_and_params"
  | "fuzzy"
  | "sequential";

/**
 * Abstract base class for request matchers.
 */
export abstract class RequestMatcher {
  protected usedInteractions = new Set<number>();

  abstract match(
    request: JSONRPCRequest,
    interactions: VCRInteraction[]
  ): VCRInteraction | null;

  reset(): void {
    this.usedInteractions.clear();
  }
}

/**
 * Exact matcher: full JSON equality (excluding jsonrpc field).
 */
export class ExactMatcher extends RequestMatcher {
  match(
    request: JSONRPCRequest,
    interactions: VCRInteraction[]
  ): VCRInteraction | null {
    for (const interaction of interactions) {
      if (this.usedInteractions.has(interaction.sequence)) continue;

      if (this.isExactMatch(request, interaction.request)) {
        this.usedInteractions.add(interaction.sequence);
        return interaction;
      }
    }
    return null;
  }

  private isExactMatch(a: JSONRPCRequest, b: JSONRPCRequest): boolean {
    return (
      a.id === b.id &&
      a.method === b.method &&
      JSON.stringify(a.params) === JSON.stringify(b.params)
    );
  }
}

/**
 * Method matcher: matches by method name only.
 */
export class MethodMatcher extends RequestMatcher {
  match(
    request: JSONRPCRequest,
    interactions: VCRInteraction[]
  ): VCRInteraction | null {
    for (const interaction of interactions) {
      if (this.usedInteractions.has(interaction.sequence)) continue;

      if (request.method === interaction.request.method) {
        this.usedInteractions.add(interaction.sequence);
        return interaction;
      }
    }
    return null;
  }
}

/**
 * Method and params matcher: matches by method name and full params equality.
 */
export class MethodAndParamsMatcher extends RequestMatcher {
  match(
    request: JSONRPCRequest,
    interactions: VCRInteraction[]
  ): VCRInteraction | null {
    for (const interaction of interactions) {
      if (this.usedInteractions.has(interaction.sequence)) continue;

      if (
        request.method === interaction.request.method &&
        JSON.stringify(request.params) === JSON.stringify(interaction.request.params)
      ) {
        this.usedInteractions.add(interaction.sequence);
        return interaction;
      }
    }
    return null;
  }
}

/**
 * Fuzzy matcher: matches if request params are a subset of recorded params.
 */
export class FuzzyMatcher extends RequestMatcher {
  match(
    request: JSONRPCRequest,
    interactions: VCRInteraction[]
  ): VCRInteraction | null {
    for (const interaction of interactions) {
      if (this.usedInteractions.has(interaction.sequence)) continue;

      if (
        request.method === interaction.request.method &&
        this.isSubset(request.params, interaction.request.params)
      ) {
        this.usedInteractions.add(interaction.sequence);
        return interaction;
      }
    }
    return null;
  }

  private isSubset(
    subset: unknown,
    superset: unknown
  ): boolean {
    if (subset === undefined || subset === null) return true;
    if (superset === undefined || superset === null) return false;

    if (typeof subset !== "object" || typeof superset !== "object") {
      return JSON.stringify(subset) === JSON.stringify(superset);
    }

    if (Array.isArray(subset) && Array.isArray(superset)) {
      return JSON.stringify(subset) === JSON.stringify(superset);
    }

    // Check if all keys in subset exist in superset with same values
    const subObj = subset as Record<string, unknown>;
    const superObj = superset as Record<string, unknown>;

    for (const key of Object.keys(subObj)) {
      if (!(key in superObj)) return false;
      if (!this.isSubset(subObj[key], superObj[key])) return false;
    }

    return true;
  }
}

/**
 * Sequential matcher: returns interactions in order, ignoring request content.
 */
export class SequentialMatcher extends RequestMatcher {
  private currentIndex = 0;

  match(
    _request: JSONRPCRequest,
    interactions: VCRInteraction[]
  ): VCRInteraction | null {
    if (this.currentIndex >= interactions.length) {
      return null;
    }
    return interactions[this.currentIndex++];
  }

  override reset(): void {
    super.reset();
    this.currentIndex = 0;
  }
}

/**
 * Factory function to create a matcher based on strategy.
 */
export function createMatcher(strategy: MatchStrategy): RequestMatcher {
  switch (strategy) {
    case "exact":
      return new ExactMatcher();
    case "method":
      return new MethodMatcher();
    case "method_and_params":
      return new MethodAndParamsMatcher();
    case "fuzzy":
      return new FuzzyMatcher();
    case "sequential":
      return new SequentialMatcher();
    default:
      throw new Error(`Unknown match strategy: ${strategy}`);
  }
}
