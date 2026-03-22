from __future__ import annotations

from collections import defaultdict

from app.auth import utc_now_iso
from app.models import QueryPerformanceMetric, QueryPerformanceResponse


class QueryPerformanceService:
    def __init__(self, storage) -> None:
        self._storage = storage

    def status(self, limit: int = 12) -> QueryPerformanceResponse:
        rows = self._storage.list_query_metrics(limit=2500)
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            grouped[str(row["operation"])].append(row)

        metrics: list[QueryPerformanceMetric] = []
        for operation, items in grouped.items():
            durations = sorted(float(item["duration_ms"]) for item in items)
            if not durations:
                continue
            p95_index = min(len(durations) - 1, max(0, round((len(durations) - 1) * 0.95)))
            metrics.append(
                QueryPerformanceMetric(
                    operation=operation,
                    calls=len(items),
                    average_ms=round(sum(durations) / len(durations), 4),
                    p95_ms=round(durations[p95_index], 4),
                    max_ms=round(durations[-1], 4),
                    error_count=sum(1 for item in items if int(item["status_code"]) >= 400),
                    last_seen_at=str(items[0]["recorded_at"]),
                )
            )

        metrics.sort(
            key=lambda item: (item.p95_ms, item.calls, item.operation),
            reverse=True,
        )
        return QueryPerformanceResponse(
            generated_at=utc_now_iso(),
            metrics=metrics[:limit],
        )
