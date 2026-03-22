from __future__ import annotations

from collections.abc import Callable

from app.models import WhatIfResponse


class WhatIfService:
    def __init__(self, engine_getter: Callable[[], object], platform_services) -> None:
        self._engine_getter = engine_getter
        self._platform_services = platform_services

    def simulate(self, edge_id: str, focus_resource_id: str | None = None) -> WhatIfResponse:
        engine = self._engine_getter()
        focus_key = focus_resource_id or "all"
        cache_key = f"whatif:{engine.snapshot.generated_at}:{edge_id}:{focus_key}"
        cached = self._platform_services.cache.get_json(cache_key)
        if cached is not None:
            return WhatIfResponse.model_validate(cached)
        response = engine.simulate_edge_removal(edge_id, focus_resource_id)
        self._platform_services.cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=300,
        )
        return response
