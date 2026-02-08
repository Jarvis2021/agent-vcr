/**
 * Tests for RequestMatcher — all 5 matching strategies.
 * Ported from Python test_matcher.py.
 */
import { describe, it, expect } from "vitest";
import {
  ExactMatcher,
  MethodMatcher,
  MethodAndParamsMatcher,
  FuzzyMatcher,
  SequentialMatcher,
  createMatcher,
} from "../../src/core/matcher.js";
import type { JSONRPCRequest, VCRInteraction } from "../../src/core/format.js";
import { createInteraction } from "../fixtures.js";

function makeRequest(
  method: string,
  params?: Record<string, unknown>,
  id: number | string = 1
): JSONRPCRequest {
  return {
    jsonrpc: "2.0",
    id,
    method,
    params,
  };
}

describe("createMatcher", () => {
  it("creates ExactMatcher for exact", () => {
    const matcher = createMatcher("exact");
    expect(matcher).toBeInstanceOf(ExactMatcher);
  });

  it("creates MethodMatcher for method", () => {
    const matcher = createMatcher("method");
    expect(matcher).toBeInstanceOf(MethodMatcher);
  });

  it("creates MethodAndParamsMatcher for method_and_params", () => {
    const matcher = createMatcher("method_and_params");
    expect(matcher).toBeInstanceOf(MethodAndParamsMatcher);
  });

  it("creates FuzzyMatcher for fuzzy", () => {
    const matcher = createMatcher("fuzzy");
    expect(matcher).toBeInstanceOf(FuzzyMatcher);
  });

  it("creates SequentialMatcher for sequential", () => {
    const matcher = createMatcher("sequential");
    expect(matcher).toBeInstanceOf(SequentialMatcher);
  });

  it("throws for invalid strategy", () => {
    expect(() => createMatcher("invalid" as "exact")).toThrow(/Unknown match strategy/);
  });
});

describe("ExactMatcher", () => {
  it("matches identical request (method + params)", () => {
    const matcher = new ExactMatcher();
    const request = makeRequest("tools/list", { limit: 10 });
    const interaction = createInteraction("tools/list", { limit: 10 });
    const match = matcher.match(request, [interaction]);
    expect(match).toBe(interaction);
  });

  it("does not match different params", () => {
    const matcher = new ExactMatcher();
    const request = makeRequest("tools/list", { limit: 10 });
    const interaction = createInteraction("tools/list", { limit: 20 });
    expect(matcher.match(request, [interaction])).toBeNull();
  });

  it("does not match different method", () => {
    const matcher = new ExactMatcher();
    const request = makeRequest("tools/list");
    const interaction = createInteraction("tools/call");
    expect(matcher.match(request, [interaction])).toBeNull();
  });

  it("ignores request id (matches by method and params only)", () => {
    const matcher = new ExactMatcher();
    const request = makeRequest("test", { key: "value" }, 100);
    const interaction = createInteraction("test", { key: "value" });
    expect(matcher.match(request, [interaction])).toBe(interaction);
  });

  it("matches empty params", () => {
    const matcher = new ExactMatcher();
    const request = makeRequest("test", {});
    const interaction = createInteraction("test", {});
    expect(matcher.match(request, [interaction])).toBe(interaction);
  });
});

describe("MethodMatcher", () => {
  it("matches same method regardless of params", () => {
    const matcher = new MethodMatcher();
    const request = makeRequest("tools/list", { limit: 10 });
    const interaction = createInteraction("tools/list", { limit: 20 });
    expect(matcher.match(request, [interaction])).toBe(interaction);
  });

  it("does not match different method", () => {
    const matcher = new MethodMatcher();
    const request = makeRequest("tools/call");
    const interaction = createInteraction("tools/list");
    expect(matcher.match(request, [interaction])).toBeNull();
  });
});

describe("MethodAndParamsMatcher", () => {
  it("matches same method and params", () => {
    const matcher = new MethodAndParamsMatcher();
    const request = makeRequest("tools/call", { name: "echo" });
    const interaction = createInteraction("tools/call", { name: "echo" });
    expect(matcher.match(request, [interaction])).toBe(interaction);
  });

  it("does not match different params", () => {
    const matcher = new MethodAndParamsMatcher();
    const request = makeRequest("tools/call", { name: "echo" });
    const interaction = createInteraction("tools/call", { name: "other" });
    expect(matcher.match(request, [interaction])).toBeNull();
  });
});

describe("FuzzyMatcher", () => {
  it("matches when request params are subset of recorded", () => {
    const matcher = new FuzzyMatcher();
    const request = makeRequest("test", { a: 1 });
    const interaction = createInteraction("test", { a: 1, b: 2 });
    expect(matcher.match(request, [interaction])).toBe(interaction);
  });

  it("does not match when request has extra key not in recorded", () => {
    const matcher = new FuzzyMatcher();
    const request = makeRequest("test", { a: 1, b: 2 });
    const interaction = createInteraction("test", { a: 1 });
    expect(matcher.match(request, [interaction])).toBeNull();
  });

  it("matches undefined params", () => {
    const matcher = new FuzzyMatcher();
    const request = makeRequest("test", undefined);
    const interaction = createInteraction("test", {});
    expect(matcher.match(request, [interaction])).toBe(interaction);
  });
});

describe("SequentialMatcher", () => {
  it("returns interactions in order", () => {
    const matcher = new SequentialMatcher();
    const i0 = createInteraction("a", {}, 0);
    const i1 = createInteraction("b", {}, 1);
    const interactions = [i0, i1];
    expect(matcher.match(makeRequest("x"), interactions)).toBe(i0);
    expect(matcher.match(makeRequest("y"), interactions)).toBe(i1);
  });

  it("returns null when exhausted", () => {
    const matcher = new SequentialMatcher();
    const interactions = [createInteraction("a", {}, 0)];
    matcher.match(makeRequest("x"), interactions);
    expect(matcher.match(makeRequest("y"), interactions)).toBeNull();
  });

  it("reset restarts index", () => {
    const matcher = new SequentialMatcher();
    const i0 = createInteraction("a", {}, 0);
    const interactions = [i0];
    matcher.match(makeRequest("x"), interactions);
    matcher.reset();
    expect(matcher.match(makeRequest("y"), interactions)).toBe(i0);
  });
});
