"""Tests for RequestMatcher — all 5 matching strategies."""

from datetime import datetime

import pytest

from agent_vcr.core.format import (
    JSONRPCRequest,
    JSONRPCResponse,
    VCRInteraction,
)
from agent_vcr.core.matcher import RequestMatcher


# ===== Fixture Helpers =====


def create_interaction(
    method: str,
    params=None,
    sequence: int = 0,
) -> VCRInteraction:
    """Helper to create an interaction with given method and params."""
    return VCRInteraction(
        sequence=sequence,
        timestamp=datetime.now(),
        direction="client_to_server",
        request=JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method=method,
            params=params,
        ),
        response=JSONRPCResponse(
            jsonrpc="2.0",
            id=1,
            result={},
        ),
        latency_ms=10.0,
    )


# ===== RequestMatcher Initialization Tests =====


class TestRequestMatcherInit:
    """Tests for RequestMatcher initialization."""

    def test_init_default_strategy(self):
        """Default strategy is method_and_params."""
        matcher = RequestMatcher()
        assert matcher.strategy == "method_and_params"

    def test_init_with_strategy(self):
        """Can specify strategy on init."""
        for strategy in ["exact", "method", "method_and_params", "subset", "sequential"]:
            matcher = RequestMatcher(strategy=strategy)
            assert matcher.strategy == strategy

    def test_fuzzy_alias_resolves_to_subset(self):
        """'fuzzy' is accepted as deprecated alias for 'subset'."""
        matcher = RequestMatcher(strategy="fuzzy")
        assert matcher.strategy == "subset"

    def test_init_invalid_strategy(self):
        """Invalid strategy raises ValueError."""
        with pytest.raises(ValueError):
            RequestMatcher(strategy="invalid")  # type: ignore

    def test_sequential_index_starts_at_zero(self):
        """Sequential index initialized to 0."""
        matcher = RequestMatcher(strategy="sequential")
        assert matcher._sequential_index == 0


# ===== Strategy: Exact Matching =====


class TestMatcherExactStrategy:
    """Tests for exact matching strategy."""

    def test_exact_match_identical_request(self):
        """Exact match finds identical requests."""
        matcher = RequestMatcher(strategy="exact")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/list",
            params={"limit": 10},
        )

        interaction = create_interaction("tools/list", {"limit": 10})
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 1
        assert matches[0] == interaction

    def test_exact_match_different_params(self):
        """Exact match fails with different params."""
        matcher = RequestMatcher(strategy="exact")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/list",
            params={"limit": 10},
        )

        interaction = create_interaction("tools/list", {"limit": 20})
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 0

    def test_exact_match_different_method(self):
        """Exact match fails with different method."""
        matcher = RequestMatcher(strategy="exact")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/list",
        )

        interaction = create_interaction("tools/call")
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 0

    def test_exact_match_ignores_id(self):
        """Exact match ignores the request id."""
        matcher = RequestMatcher(strategy="exact")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=100,
            method="test",
            params={"key": "value"},
        )

        interaction = create_interaction("test", {"key": "value"})
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 1

    def test_exact_match_empty_params(self):
        """Exact match handles empty/None params."""
        matcher = RequestMatcher(strategy="exact")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params=None,
        )

        interaction = create_interaction("test", None)
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 1

    def test_exact_match_multiple_candidates(self):
        """Exact match returns all exact matches."""
        matcher = RequestMatcher(strategy="exact")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params={"key": "value"},
        )

        interactions = [
            create_interaction("test", {"key": "value"}, sequence=0),
            create_interaction("test", {"key": "value"}, sequence=1),
            create_interaction("test", {"key": "other"}, sequence=2),
        ]

        matches = matcher.find_all_matches(request, interactions)
        assert len(matches) == 2


# ===== Strategy: Method Matching =====


class TestMatcherMethodStrategy:
    """Tests for method-only matching strategy."""

    def test_method_match_same_method(self):
        """Method match finds same method regardless of params."""
        matcher = RequestMatcher(strategy="method")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/list",
            params={"limit": 10},
        )

        interaction = create_interaction("tools/list", {"limit": 20})
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 1

    def test_method_match_different_method(self):
        """Method match fails with different method."""
        matcher = RequestMatcher(strategy="method")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/list",
        )

        interaction = create_interaction("tools/call")
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 0

    def test_method_match_multiple_same_method(self):
        """Method match returns all interactions with same method."""
        matcher = RequestMatcher(strategy="method")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
        )

        interactions = [
            create_interaction("test", {"params": "a"}, sequence=0),
            create_interaction("test", {"params": "b"}, sequence=1),
            create_interaction("test", {"params": "c"}, sequence=2),
            create_interaction("other", {}, sequence=3),
        ]

        matches = matcher.find_all_matches(request, interactions)
        assert len(matches) == 3

    def test_method_match_none_params(self):
        """Method match works with None params."""
        matcher = RequestMatcher(strategy="method")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params=None,
        )

        interaction = create_interaction("test", {"key": "value"})
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 1


# ===== Strategy: Method and Params Matching =====


class TestMatcherMethodAndParamsStrategy:
    """Tests for method + full params matching (default)."""

    def test_method_params_exact_match(self):
        """Method+params match requires both to match exactly."""
        matcher = RequestMatcher(strategy="method_and_params")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/call",
            params={"name": "echo", "arguments": {"text": "hello"}},
        )

        interaction = create_interaction(
            "tools/call",
            {"name": "echo", "arguments": {"text": "hello"}},
        )

        matches = matcher.find_all_matches(request, [interaction])
        assert len(matches) == 1

    def test_method_params_different_params(self):
        """Method+params fails if params differ."""
        matcher = RequestMatcher(strategy="method_and_params")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/call",
            params={"name": "echo"},
        )

        interaction = create_interaction(
            "tools/call",
            {"name": "different"},
        )

        matches = matcher.find_all_matches(request, [interaction])
        assert len(matches) == 0

    def test_method_params_different_method(self):
        """Method+params fails if method differs."""
        matcher = RequestMatcher(strategy="method_and_params")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="tools/list",
            params={"key": "value"},
        )

        interaction = create_interaction("tools/call", {"key": "value"})
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 0

    def test_method_params_none_params(self):
        """Method+params with None params."""
        matcher = RequestMatcher(strategy="method_and_params")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params=None,
        )

        interaction = create_interaction("test", None)
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 1

    def test_method_params_default_strategy(self):
        """method_and_params is the default strategy."""
        default_matcher = RequestMatcher()
        explicit_matcher = RequestMatcher(strategy="method_and_params")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params={"key": "value"},
        )

        interaction = create_interaction("test", {"key": "value"})

        default_matches = default_matcher.find_all_matches(request, [interaction])
        explicit_matches = explicit_matcher.find_all_matches(
            request, [interaction]
        )

        assert len(default_matches) == len(explicit_matches) == 1


# ===== Strategy: Fuzzy Matching =====


class TestMatcherFuzzyStrategy:
    """Tests for fuzzy/subset matching strategy."""

    def test_fuzzy_dict_subset(self):
        """Fuzzy match accepts dict params as subset."""
        matcher = RequestMatcher(strategy="fuzzy")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params={"name": "echo"},
        )

        # Recorded has more fields
        interaction = create_interaction(
            "test",
            {"name": "echo", "version": "1.0", "timeout": 30},
        )

        matches = matcher.find_all_matches(request, [interaction])
        assert len(matches) == 1

    def test_fuzzy_dict_extra_key_fails(self):
        """Fuzzy match fails if request has extra keys."""
        matcher = RequestMatcher(strategy="fuzzy")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params={"name": "echo", "extra": "field"},
        )

        # Recorded has fewer fields
        interaction = create_interaction(
            "test",
            {"name": "echo"},
        )

        matches = matcher.find_all_matches(request, [interaction])
        assert len(matches) == 0

    def test_fuzzy_dict_value_mismatch_fails(self):
        """Fuzzy match fails if values don't match."""
        matcher = RequestMatcher(strategy="fuzzy")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params={"name": "different"},
        )

        interaction = create_interaction("test", {"name": "echo"})
        matches = matcher.find_all_matches(request, [interaction])

        assert len(matches) == 0

    def test_fuzzy_list_exact_only(self):
        """Fuzzy match requires exact match for list params."""
        matcher = RequestMatcher(strategy="fuzzy")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params=["a", "b"],
        )

        interaction = create_interaction("test", ["a", "b"])
        matches = matcher.find_all_matches(request, [interaction])
        assert len(matches) == 1

        interaction2 = create_interaction("test", ["a", "b", "c"])
        matches2 = matcher.find_all_matches(request, [interaction2])
        assert len(matches2) == 0

    def test_fuzzy_none_params(self):
        """Fuzzy match handles None params."""
        matcher = RequestMatcher(strategy="fuzzy")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params=None,
        )

        interaction = create_interaction("test", None)
        matches = matcher.find_all_matches(request, [interaction])
        assert len(matches) == 1

    def test_fuzzy_mixed_type_params(self):
        """Fuzzy match rejects when request has list params and recorded has dict."""
        matcher = RequestMatcher(strategy="fuzzy")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params=["a", "b"],
        )

        # List vs dict should not match
        interaction = create_interaction("test", {"key": "value"})
        matches = matcher.find_all_matches(request, [interaction])
        assert len(matches) == 0

        # List vs same list should match
        interaction2 = create_interaction("test", ["a", "b"])
        matches2 = matcher.find_all_matches(request, [interaction2])
        assert len(matches2) == 1


# ===== Strategy: Sequential Matching =====


class TestMatcherSequentialStrategy:
    """Tests for sequential matching strategy."""

    def test_sequential_returns_in_order(self):
        """Sequential returns interactions in order."""
        matcher = RequestMatcher(strategy="sequential")

        interactions = [
            create_interaction("first", sequence=0),
            create_interaction("second", sequence=1),
            create_interaction("third", sequence=2),
        ]

        # First call returns first interaction
        request = JSONRPCRequest(jsonrpc="2.0", id=1, method="any")
        match = matcher.find_match(request, interactions)
        assert match.request.method == "first"

        # Second call returns second interaction
        match = matcher.find_match(request, interactions)
        assert match.request.method == "second"

        # Third call returns third interaction
        match = matcher.find_match(request, interactions)
        assert match.request.method == "third"

    def test_sequential_exhausted_returns_empty(self):
        """Sequential returns empty when exhausted."""
        matcher = RequestMatcher(strategy="sequential")

        interactions = [
            create_interaction("only", sequence=0),
        ]

        request = JSONRPCRequest(jsonrpc="2.0", id=1, method="any")

        # First call matches
        match = matcher.find_match(request, interactions)
        assert match is not None

        # Second call finds nothing
        match = matcher.find_match(request, interactions)
        assert match is None

    def test_sequential_ignores_request_details(self):
        """Sequential ignores request method/params."""
        matcher = RequestMatcher(strategy="sequential")

        interactions = [
            create_interaction("first", {"key": "value"}, sequence=0),
            create_interaction("second", None, sequence=1),
        ]

        # Request details don't matter
        request1 = JSONRPCRequest(
            jsonrpc="2.0", id=1, method="different"
        )
        request2 = JSONRPCRequest(
            jsonrpc="2.0", id=2, method="also_different"
        )

        match1 = matcher.find_match(request1, interactions)
        assert match1.request.method == "first"

        match2 = matcher.find_match(request2, interactions)
        assert match2.request.method == "second"

    def test_sequential_reset_index(self):
        """Can reset sequential index."""
        matcher = RequestMatcher(strategy="sequential")

        interactions = [
            create_interaction("first", sequence=0),
            create_interaction("second", sequence=1),
        ]

        request = JSONRPCRequest(jsonrpc="2.0", id=1, method="any")

        # Consume first interaction
        matcher.find_match(request, interactions)

        # Reset
        matcher.reset_sequential_index()

        # Should get first again
        match = matcher.find_match(request, interactions)
        assert match.request.method == "first"


# ===== Generic find_match vs find_all_matches =====


class TestRequestMatcherGeneric:
    """Tests for generic find_match and find_all_matches."""

    def test_find_match_returns_first(self):
        """find_match returns first of all matches."""
        matcher = RequestMatcher(strategy="method")

        interactions = [
            create_interaction("test", {"a": 1}, sequence=0),
            create_interaction("test", {"b": 2}, sequence=1),
            create_interaction("test", {"c": 3}, sequence=2),
        ]

        request = JSONRPCRequest(jsonrpc="2.0", id=1, method="test")
        match = matcher.find_match(request, interactions)

        assert match is not None
        assert match.sequence == 0

    def test_find_match_no_match_returns_none(self):
        """find_match returns None when no matches."""
        matcher = RequestMatcher(strategy="method")

        interactions = [
            create_interaction("other", sequence=0),
        ]

        request = JSONRPCRequest(jsonrpc="2.0", id=1, method="test")
        match = matcher.find_match(request, interactions)

        assert match is None

    def test_find_all_matches_empty_list(self):
        """find_all_matches returns empty list for no matches."""
        matcher = RequestMatcher(strategy="method")

        interactions = [
            create_interaction("other", sequence=0),
        ]

        request = JSONRPCRequest(jsonrpc="2.0", id=1, method="test")
        matches = matcher.find_all_matches(request, interactions)

        assert matches == []

    def test_find_all_matches_empty_interactions(self):
        """find_all_matches handles empty interaction list."""
        matcher = RequestMatcher(strategy="method")

        request = JSONRPCRequest(jsonrpc="2.0", id=1, method="test")
        matches = matcher.find_all_matches(request, [])

        assert matches == []


# ===== Edge Cases and Integration =====


class TestRequestMatcherEdgeCases:
    """Tests for edge cases and integration scenarios."""

    def test_switching_strategies(self):
        """Can create different matchers with different strategies."""
        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params={"key": "value"},
        )

        interaction = create_interaction("test", {"key": "value", "extra": "data"})

        # exact: doesn't match due to extra field
        exact = RequestMatcher(strategy="exact")
        assert len(exact.find_all_matches(request, [interaction])) == 0

        # fuzzy: matches (subset)
        fuzzy = RequestMatcher(strategy="fuzzy")
        assert len(fuzzy.find_all_matches(request, [interaction])) == 1

        # method: matches
        method = RequestMatcher(strategy="method")
        assert len(method.find_all_matches(request, [interaction])) == 1

    def test_complex_nested_params(self):
        """Matching works with complex nested params."""
        matcher = RequestMatcher(strategy="method_and_params")

        request = JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="test",
            params={
                "outer": {
                    "inner": {
                        "value": 123,
                    }
                }
            },
        )

        interaction = create_interaction(
            "test",
            {
                "outer": {
                    "inner": {
                        "value": 123,
                    }
                }
            },
        )

        matches = matcher.find_all_matches(request, [interaction])
        assert len(matches) == 1
