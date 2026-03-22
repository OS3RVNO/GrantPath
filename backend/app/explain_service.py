from __future__ import annotations

from collections.abc import Callable

from app.models import ExplainResponse


class ExplainService:
    def __init__(self, engine_getter: Callable[[], object], platform_services) -> None:
        self._engine_getter = engine_getter
        self._platform_services = platform_services

    def explain(self, principal_id: str, resource_id: str) -> ExplainResponse:
        engine = self._engine_getter()
        cache_key = f"explain:{engine.snapshot.generated_at}:{principal_id}:{resource_id}"
        cached = self._platform_services.cache.get_json(cache_key)
        if cached is not None:
            return ExplainResponse.model_validate(cached)
        response = engine.explain(principal_id, resource_id)
        self._platform_services.cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=600,
        )
        return response
