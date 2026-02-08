"""Request matcher for VCR replay — matches incoming requests to recorded interactions."""

from typing import Dict, List, Literal, Optional, Any

from agent_vcr.core.format import JSONRPCRequest, VCRInteraction


MatchStrategy = Literal["exact", "method", "method_and_params", "fuzzy", "sequential"]


class RequestMatcher:
    """Matches incoming requests to recorded interactions using various strategies.

    Strategies:
    - exact: Exact JSON match of the entire request
    - method: Match by method name only
    - method_and_params: Match method + full params (default)
    - fuzzy: Match method + partial params (subset matching)
    - sequential: Return interactions in order regardless of match
    """

    VALID_STRATEGIES = {"exact", "method", "method_and_params", "fuzzy", "sequential"}

    def __init__(self, strategy: MatchStrategy = "method_and_params") -> None:
        """Initialize the request matcher.

        Args:
            strategy: Matching strategy to use

        Raises:
            ValueError: If strategy is not a valid matching strategy
        """
        if strategy not in self.VALID_STRATEGIES:
            raise ValueError(
                f"Unknown matching strategy: '{strategy}'. "
                f"Valid strategies: {', '.join(sorted(self.VALID_STRATEGIES))}"
            )
        self.strategy = strategy
        self._sequential_index = 0

    def reset_sequential_index(self) -> None:
        """Reset the sequential index counter.

        Used when starting a new replay or replay session.
        """
        self._sequential_index = 0

    def find_match(
        self, request: JSONRPCRequest, interactions: List[VCRInteraction]
    ) -> Optional[VCRInteraction]:
        """Find a single matching interaction for the given request.

        Args:
            request: The incoming request to match
            interactions: List of recorded interactions to search

        Returns:
            The first matching VCRInteraction, or None if no match found
        """
        matches = self.find_all_matches(request, interactions)
        return matches[0] if matches else None

    def find_all_matches(
        self, request: JSONRPCRequest, interactions: List[VCRInteraction]
    ) -> List[VCRInteraction]:
        """Find all matching interactions for the given request.

        Args:
            request: The incoming request to match
            interactions: List of recorded interactions to search

        Returns:
            List of matching VCRInteractions, sorted by relevance
        """
        if self.strategy == "sequential":
            return self._match_sequential(interactions)
        elif self.strategy == "exact":
            return self._match_exact(request, interactions)
        elif self.strategy == "method":
            return self._match_method(request, interactions)
        elif self.strategy == "method_and_params":
            return self._match_method_and_params(request, interactions)
        elif self.strategy == "fuzzy":
            return self._match_fuzzy(request, interactions)
        else:
            raise ValueError(f"Unknown matching strategy: {self.strategy}")

    def _match_sequential(
        self, interactions: List[VCRInteraction]
    ) -> List[VCRInteraction]:
        """Return the next interaction in sequential order.

        Args:
            interactions: List of recorded interactions

        Returns:
            A single-item list with the next interaction, or empty list if exhausted
        """
        if self._sequential_index < len(interactions):
            match = interactions[self._sequential_index]
            self._sequential_index += 1
            return [match]
        return []

    def _match_exact(
        self, request: JSONRPCRequest, interactions: List[VCRInteraction]
    ) -> List[VCRInteraction]:
        """Match by exact JSON equality of entire request.

        Args:
            request: The incoming request
            interactions: List of recorded interactions

        Returns:
            List of interactions whose requests exactly match
        """
        matches = []
        request_dict = request.model_dump(exclude={"jsonrpc", "id"})

        for interaction in interactions:
            recorded_dict = interaction.request.model_dump(exclude={"jsonrpc", "id"})
            if request_dict == recorded_dict:
                matches.append(interaction)

        return matches

    def _match_method(
        self, request: JSONRPCRequest, interactions: List[VCRInteraction]
    ) -> List[VCRInteraction]:
        """Match by method name only.

        Args:
            request: The incoming request
            interactions: List of recorded interactions

        Returns:
            List of interactions with matching method
        """
        matches = []

        for interaction in interactions:
            if interaction.request.method == request.method:
                matches.append(interaction)

        return matches

    def _match_method_and_params(
        self, request: JSONRPCRequest, interactions: List[VCRInteraction]
    ) -> List[VCRInteraction]:
        """Match by method name and full params equality (default strategy).

        Args:
            request: The incoming request
            interactions: List of recorded interactions

        Returns:
            List of interactions with matching method and params
        """
        matches = []

        for interaction in interactions:
            if (
                interaction.request.method == request.method
                and interaction.request.params == request.params
            ):
                matches.append(interaction)

        return matches

    def _match_fuzzy(
        self, request: JSONRPCRequest, interactions: List[VCRInteraction]
    ) -> List[VCRInteraction]:
        """Match by method and partial params (subset matching).

        For dict params, the incoming request's params must be a subset of
        the recorded interaction's params. For list params, exact match is required.

        Args:
            request: The incoming request
            interactions: List of recorded interactions

        Returns:
            List of interactions with matching method and partial params
        """
        matches = []

        for interaction in interactions:
            if interaction.request.method != request.method:
                continue

            if self._is_params_subset(request.params, interaction.request.params):
                matches.append(interaction)

        return matches

    @staticmethod
    def _is_params_subset(
        request_params: Optional[Any], recorded_params: Optional[Any]
    ) -> bool:
        """Check if request params are a subset of recorded params.

        For dict params, all keys in request_params must exist in recorded_params
        with the same values. For list params, exact match is required.
        For None/non-dict/non-list, exact match is required.

        Args:
            request_params: Params from incoming request
            recorded_params: Params from recorded interaction

        Returns:
            True if request_params are a subset of recorded_params
        """
        # Both None or both missing params
        if request_params is None and recorded_params is None:
            return True

        # One is None but not the other
        if (request_params is None) != (recorded_params is None):
            return False

        # Handle dict params - subset matching
        if isinstance(request_params, dict) and isinstance(recorded_params, dict):
            for key, value in request_params.items():
                if key not in recorded_params:
                    return False
                if recorded_params[key] != value:
                    return False
            return True

        # Handle list params - exact match required
        if isinstance(request_params, list) and isinstance(recorded_params, list):
            return request_params == recorded_params

        # For other types, require exact match
        return request_params == recorded_params
