from __future__ import annotations

from statistics import mean, median
from time import perf_counter

from app.demo_data import build_scaled_snapshot
from app.engine import AccessGraphEngine
from app.models import BenchmarkMetric, BenchmarkResponse, BenchmarkSnapshot
from app.reporting import (
    build_report_context,
    render_excel_report,
    render_html_report,
    render_pdf_report,
)
from app.runtime import runtime


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return ordered[index]


def _measure(iterations: int, fn) -> BenchmarkMetric:
    durations: list[float] = []
    for _ in range(iterations):
        start = perf_counter()
        fn()
        durations.append((perf_counter() - start) * 1000)

    return BenchmarkMetric(
        name=fn.__name__,
        iterations=iterations,
        average_ms=round(mean(durations), 4),
        median_ms=round(median(durations), 4),
        p95_ms=round(_percentile(durations, 0.95), 4),
        max_ms=round(max(durations), 4),
    )


def run_local_benchmark(
    *,
    mode: str = "real",
    scale: int = 1,
    iterations: int = 2,
    target_ids: list[str] | None = None,
) -> BenchmarkResponse:
    if mode == "synthetic":
        return _run_synthetic_benchmark(scale=scale, iterations=iterations)
    return runtime.benchmark(iterations=iterations, target_ids=target_ids)


def _run_synthetic_benchmark(scale: int = 1, iterations: int = 20) -> BenchmarkResponse:
    snapshot = build_scaled_snapshot(scale)
    compile_start = perf_counter()
    engine = AccessGraphEngine(snapshot)
    compile_ms = (perf_counter() - compile_start) * 1000

    overview_start = perf_counter()
    overview = engine.get_overview()
    materialization_ms = (perf_counter() - overview_start) * 1000

    default_principal_id = overview.default_principal_id
    default_resource_id = overview.default_resource_id
    default_scenario_edge_id = overview.default_scenario_edge_id
    report_context = None
    if default_principal_id and default_resource_id and default_scenario_edge_id:
        report_context = build_report_context(
            engine,
            principal_id=default_principal_id,
            resource_id=default_resource_id,
            scenario_edge_id=default_scenario_edge_id,
            focus_resource_id=default_resource_id,
        )

    metrics = [
        BenchmarkMetric(
            name="graph_compile",
            iterations=1,
            average_ms=round(compile_ms, 4),
            median_ms=round(compile_ms, 4),
            p95_ms=round(compile_ms, 4),
            max_ms=round(compile_ms, 4),
        ),
        BenchmarkMetric(
            name="graph_materialization",
            iterations=1,
            average_ms=round(materialization_ms, 4),
            median_ms=round(materialization_ms, 4),
            p95_ms=round(materialization_ms, 4),
            max_ms=round(materialization_ms, 4),
        ),
        _measure(iterations, lambda: engine.get_overview()),
        _measure(iterations, lambda: engine.get_catalog()),
    ]
    if report_context is not None:
        metrics.extend(
            [
                _measure(iterations, lambda: render_html_report(report_context)),
                _measure(iterations, lambda: render_pdf_report(report_context)),
                _measure(iterations, lambda: render_excel_report(report_context)),
            ]
        )

    metric_names = [
        "graph_compile",
        "graph_materialization",
        "overview",
        "catalog",
        "report_html",
        "report_pdf",
        "report_xlsx",
    ]
    for benchmark_metric, name in zip(metrics, metric_names, strict=False):
        benchmark_metric.name = name

    return BenchmarkResponse(
        generated_at=overview.generated_at,
        snapshot=BenchmarkSnapshot(
            mode="synthetic",
            scope=f"Scaled synthetic dataset x{scale}",
            target_count=0,
            entity_count=len(snapshot.entities),
            relationship_count=len(snapshot.relationships),
            scale=scale,
        ),
        metrics=metrics,
        notes=[
            "Synthetic benchmark retained for algorithmic regression testing.",
            "Production-facing latency guidance should use mode=real.",
        ],
    )
