"""Concrete adapters for the Mapping service ports.

These adapters implement the port interfaces defined in ports.py,
providing concrete implementations for string matching and
template history operations.
"""

import logging
from difflib import SequenceMatcher
from typing import Callable

logger = logging.getLogger(__name__)

# Try to import rapidfuzz, fall back to difflib-based implementation
_RAPIDFUZZ_AVAILABLE = False
try:
    from rapidfuzz import fuzz as rapidfuzz_fuzz
    from rapidfuzz import process as rapidfuzz_process
    from rapidfuzz import utils as rapidfuzz_utils

    _RAPIDFUZZ_AVAILABLE = True
    logger.debug("rapidfuzz library available, using optimized string matching")
except ImportError:
    logger.info(
        "rapidfuzz not installed, using difflib fallback. "
        "Install rapidfuzz for better performance: pip install rapidfuzz"
    )


class RapidFuzzStringMatcher:
    """String matcher using the rapidfuzz library with difflib fallback.

    Provides high-performance fuzzy string matching using
    various similarity algorithms (Levenshtein, Jaro-Winkler, etc.).

    Falls back to Python's difflib if rapidfuzz is not installed.

    Example usage:
        matcher = RapidFuzzStringMatcher(scorer="WRatio")
        score = matcher.compute_similarity("customer name", "Customer Name")
        matches = matcher.find_matches("name", ["Name", "Address", "Email"])
    """

    def __init__(
        self,
        scorer: str = "WRatio",
        processor: str | None = "default",
    ) -> None:
        """Initialize the string matcher.

        Args:
            scorer: Scoring algorithm to use. Options:
                - "WRatio": Weighted ratio (handles partial matches well)
                - "ratio": Simple Levenshtein ratio
                - "partial_ratio": Best partial match ratio
                - "token_sort_ratio": Token sorted matching
                - "token_set_ratio": Token set matching
            processor: Text processor. "default" lowercases and strips.
                      None for no processing.
        """
        self._scorer_name = scorer
        self._processor = processor
        self._use_rapidfuzz = _RAPIDFUZZ_AVAILABLE
        self._scorer = self._get_scorer(scorer)

    def _get_scorer(self, scorer_name: str) -> Callable[[str, str], float]:
        """Get the scorer function.

        Args:
            scorer_name: Name of the scorer to use

        Returns:
            Scorer function that takes two strings and returns 0-100 score
        """
        if self._use_rapidfuzz:
            scorers = {
                "WRatio": rapidfuzz_fuzz.WRatio,
                "ratio": rapidfuzz_fuzz.ratio,
                "partial_ratio": rapidfuzz_fuzz.partial_ratio,
                "token_sort_ratio": rapidfuzz_fuzz.token_sort_ratio,
                "token_set_ratio": rapidfuzz_fuzz.token_set_ratio,
            }
            return scorers.get(scorer_name, rapidfuzz_fuzz.WRatio)

        # Difflib-based fallback scorers
        return self._get_difflib_scorer(scorer_name)

    def _get_difflib_scorer(self, scorer_name: str) -> Callable[[str, str], float]:
        """Get a difflib-based scorer function.

        Args:
            scorer_name: Name of the scorer (used to select algorithm variant)

        Returns:
            Scorer function returning 0-100 score
        """

        def ratio_scorer(s1: str, s2: str) -> float:
            """Basic sequence matching ratio."""
            return SequenceMatcher(None, s1, s2).ratio() * 100

        def partial_ratio_scorer(s1: str, s2: str) -> float:
            """Find best partial match ratio."""
            if not s1 or not s2:
                return 0.0

            shorter, longer = (s1, s2) if len(s1) <= len(s2) else (s2, s1)

            if len(shorter) == 0:
                return 100.0

            # Slide shorter string over longer to find best match
            best_ratio = 0.0
            for i in range(len(longer) - len(shorter) + 1):
                substr = longer[i : i + len(shorter)]
                ratio = SequenceMatcher(None, shorter, substr).ratio()
                best_ratio = max(best_ratio, ratio)

            return best_ratio * 100

        def token_sort_ratio_scorer(s1: str, s2: str) -> float:
            """Sort tokens before comparing."""
            tokens1 = sorted(s1.lower().split())
            tokens2 = sorted(s2.lower().split())
            sorted_s1 = " ".join(tokens1)
            sorted_s2 = " ".join(tokens2)
            return SequenceMatcher(None, sorted_s1, sorted_s2).ratio() * 100

        def token_set_ratio_scorer(s1: str, s2: str) -> float:
            """Compare token sets."""
            set1 = set(s1.lower().split())
            set2 = set(s2.lower().split())

            if not set1 and not set2:
                return 100.0
            if not set1 or not set2:
                return 0.0

            intersection = set1 & set2
            diff1_2 = set1 - set2
            diff2_1 = set2 - set1

            # Build comparison strings
            sorted_intersection = " ".join(sorted(intersection))
            combined1 = " ".join(sorted(intersection | diff1_2))
            combined2 = " ".join(sorted(intersection | diff2_1))

            # Compare all combinations
            ratios = [
                SequenceMatcher(None, sorted_intersection, combined1).ratio(),
                SequenceMatcher(None, sorted_intersection, combined2).ratio(),
                SequenceMatcher(None, combined1, combined2).ratio(),
            ]

            return max(ratios) * 100

        def wratio_scorer(s1: str, s2: str) -> float:
            """Weighted ratio combining multiple methods."""
            # Simplified WRatio: weighted combination of methods
            ratio = SequenceMatcher(None, s1.lower(), s2.lower()).ratio() * 100
            partial = partial_ratio_scorer(s1.lower(), s2.lower())
            token_sort = token_sort_ratio_scorer(s1, s2)
            token_set = token_set_ratio_scorer(s1, s2)

            # Weight longer matches more heavily
            len_ratio = min(len(s1), len(s2)) / max(len(s1), len(s2), 1)

            if len_ratio >= 0.95:
                # Similar length: prefer exact ratio
                return max(ratio, partial, token_sort, token_set)
            elif len_ratio >= 0.6:
                # Moderate difference: blend
                return max(partial, token_sort, token_set) * 0.95
            else:
                # Large difference: partial match more important
                return partial * 0.9

        scorers = {
            "WRatio": wratio_scorer,
            "ratio": ratio_scorer,
            "partial_ratio": partial_ratio_scorer,
            "token_sort_ratio": token_sort_ratio_scorer,
            "token_set_ratio": token_set_ratio_scorer,
        }

        return scorers.get(scorer_name, wratio_scorer)

    def _preprocess(self, text: str) -> str:
        """Preprocess text according to configured processor.

        Args:
            text: Input text

        Returns:
            Processed text
        """
        if self._processor == "default":
            if self._use_rapidfuzz:
                return rapidfuzz_utils.default_process(text)
            # Difflib fallback: lowercase and strip
            return text.lower().strip()
        return text

    def compute_similarity(
        self,
        source: str,
        target: str,
    ) -> float:
        """Compute similarity score between two strings.

        Args:
            source: Source string to compare
            target: Target string to compare against

        Returns:
            Similarity score from 0.0 (no match) to 1.0 (exact match)
        """
        if self._use_rapidfuzz:
            processor = rapidfuzz_utils.default_process if self._processor == "default" else None
            score = self._scorer(source, target, processor=processor)
            return score / 100.0

        # Difflib fallback
        processed_source = self._preprocess(source)
        processed_target = self._preprocess(target)
        score = self._scorer(processed_source, processed_target)
        return score / 100.0

    def find_matches(
        self,
        source: str,
        targets: tuple[str, ...],
        threshold: float = 0.6,
        limit: int = 5,
    ) -> tuple[tuple[str, float], ...]:
        """Find best matching strings from a list of targets.

        Args:
            source: Source string to match
            targets: Tuple of target strings to search
            threshold: Minimum similarity score to include (default 0.6)
            limit: Maximum number of matches to return (default 5)

        Returns:
            Tuple of (target_string, similarity_score) pairs,
            sorted by score descending
        """
        if not targets:
            return ()

        if self._use_rapidfuzz:
            processor = rapidfuzz_utils.default_process if self._processor == "default" else None

            results = rapidfuzz_process.extract(
                source,
                targets,
                scorer=self._scorer,
                processor=processor,
                limit=limit,
                score_cutoff=threshold * 100,
            )

            return tuple((match, score / 100.0) for match, score, _ in results)

        # Difflib fallback: compute scores for all targets
        scored = []
        for target in targets:
            score = self.compute_similarity(source, target)
            if score >= threshold:
                scored.append((target, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return tuple(scored[:limit])

    def batch_find_matches(
        self,
        sources: tuple[str, ...],
        targets: tuple[str, ...],
        threshold: float = 0.6,
    ) -> dict[str, tuple[tuple[str, float], ...]]:
        """Find matches for multiple source strings.

        Args:
            sources: Tuple of source strings to match
            targets: Tuple of target strings to search
            threshold: Minimum similarity score to include

        Returns:
            Dictionary mapping source strings to their matches
        """
        if not sources or not targets:
            return {}

        if self._use_rapidfuzz:
            # Use cdist for efficient batch matching
            try:
                processor = (
                    rapidfuzz_utils.default_process if self._processor == "default" else None
                )

                # Create similarity matrix
                scores = rapidfuzz_process.cdist(
                    list(sources),
                    list(targets),
                    scorer=self._scorer,
                    processor=processor,
                )

                results: dict[str, tuple[tuple[str, float], ...]] = {}
                for i, source in enumerate(sources):
                    matches = []
                    for j, target in enumerate(targets):
                        score = scores[i, j] / 100.0
                        if score >= threshold:
                            matches.append((target, score))
                    matches.sort(key=lambda x: x[1], reverse=True)
                    results[source] = tuple(matches[:5])

                return results

            except Exception as e:
                logger.warning("cdist failed, falling back to sequential matching: %s", str(e))

        # Fallback: iterate over sources
        results = {}
        for source in sources:
            results[source] = self.find_matches(
                source=source,
                targets=targets,
                threshold=threshold,
            )
        return results


class InMemoryTemplateHistory:
    """In-memory template history for testing/development.

    Stores mapping history in memory. Data is lost on restart.
    For production, use a persistent implementation like
    SupabaseTemplateHistory.
    """

    def __init__(self) -> None:
        """Initialize empty history storage."""
        # Structure: {template_id: {source_field_name: target_field_id}}
        self._history: dict[str, dict[str, str]] = {}

    async def get_historical_mappings(
        self,
        template_ids: tuple[str, ...],
        source_field_names: tuple[str, ...],
    ) -> dict[str, str]:
        """Retrieve historical mappings from similar templates.

        Args:
            template_ids: Template IDs to search for history
            source_field_names: Source field names to look up

        Returns:
            Dictionary mapping source_field_name to target_field_id
            for previously successful mappings
        """
        result: dict[str, str] = {}

        for template_id in template_ids:
            template_history = self._history.get(template_id, {})
            for source_name in source_field_names:
                if source_name in template_history and source_name not in result:
                    result[source_name] = template_history[source_name]

        return result

    async def record_mapping(
        self,
        template_id: str,
        source_field_name: str,
        target_field_id: str,
        was_corrected: bool = False,
    ) -> None:
        """Record a mapping for future reference.

        Args:
            template_id: Template identifier
            source_field_name: Name of the source field
            target_field_id: ID of the target field
            was_corrected: Whether this was a user correction
        """
        if template_id not in self._history:
            self._history[template_id] = {}

        self._history[template_id][source_field_name] = target_field_id

        # Note: was_corrected could be used to weight mappings
        # in a more sophisticated implementation
        _ = was_corrected

    def clear(self) -> None:
        """Clear all history. Useful for testing."""
        self._history = {}
