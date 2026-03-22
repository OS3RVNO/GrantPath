from __future__ import annotations

import re
from collections.abc import Callable

from app.models import SearchResult


class SearchService:
    def __init__(self, engine_getter: Callable[[], object], platform_services) -> None:
        self._engine_getter = engine_getter
        self._platform_services = platform_services

    @staticmethod
    def _split_tokens(value: str) -> list[str]:
        return [token for token in re.split(r"[\\/@._\-\s]+", value.lower()) if token]

    def _score_result(self, query: str, result: SearchResult) -> tuple[int, str]:
        normalized_query = query.strip().lower()
        entity = result.entity
        normalized_name = entity.name.lower()
        tokens = self._split_tokens(entity.name)
        principal_like_query = any(marker in query for marker in ("\\", "@")) or query.strip().isupper()
        score = 0

        if normalized_name == normalized_query:
            score += 240
        if normalized_query in tokens:
            score += 150
        if normalized_name.startswith(normalized_query):
            score += 90
        if any(token.startswith(normalized_query) for token in tokens):
            score += 60
        if normalized_query in normalized_name:
            score += 25

        if entity.kind in {"user", "group", "service_account", "local_account", "application_identity"}:
            score += 15
            if principal_like_query:
                score += 35

        if entity.kind == "resource":
            basename = tokens[-1] if tokens else normalized_name
            if basename == normalized_query:
                score += 40
            elif normalized_query not in basename:
                score -= 25
            score -= min(normalized_name.count("\\"), 12)

        return score, entity.name.lower()

    def _rerank_results(self, query: str, results: list[SearchResult]) -> list[SearchResult]:
        ranked = sorted(
            results,
            key=lambda result: (
                -self._score_result(query, result)[0],
                self._score_result(query, result)[1],
            ),
        )
        return ranked[:8]

    def search(self, query: str) -> list[SearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        engine = self._engine_getter()
        cache_key = f"search:{engine.snapshot.generated_at}:{normalized_query.lower()}"
        cached = self._platform_services.cache.get_json(cache_key)
        if cached is not None:
            return [SearchResult.model_validate(item) for item in cached]

        fallback_results = engine.search(normalized_query)
        results = self._platform_services.search.search(
            normalized_query,
            fallback_results,
            engine.snapshot,
        )
        results = self._rerank_results(normalized_query, results)
        self._platform_services.cache.set_json(
            cache_key,
            [item.model_dump(mode="json") for item in results],
            ttl_seconds=300,
        )
        return results
