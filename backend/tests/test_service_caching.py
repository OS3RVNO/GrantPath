from pathlib import Path
from types import SimpleNamespace

from app.demo_data import build_demo_snapshot
from app.engine import AccessGraphEngine
from app.entitlement_service import EntitlementService
from app.explain_service import ExplainService
from app.graph_service import GraphService
from app.models import GraphEdge, GraphNode, GraphPayload, GraphSubgraphResponse, SearchResult
from app.risk_service import RiskService
from app.search_service import SearchService
from app.storage import AppStorage
from app.whatif_service import WhatIfService


class _MemoryCache:
    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    def get_json(self, key: str):
        return self._store.get(key)

    def set_json(self, key: str, payload, ttl_seconds: int) -> None:  # noqa: ARG002
        self._store[key] = payload


class _MemorySearchBackend:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, fallback_results: list[SearchResult], snapshot):  # noqa: ARG002
        self.calls += 1
        return fallback_results

    def index_snapshot(self, snapshot):  # noqa: ARG002
        return None


class _NullGraphBackend:
    def subgraph(self, *, entity_id: str, depth: int, focus, max_nodes: int, max_edges: int):  # noqa: ARG002
        return None

    def index_snapshot(self, snapshot):  # noqa: ARG002
        return None


class _ExternalGraphBackend(_NullGraphBackend):
    def __init__(self) -> None:
        self.calls = 0

    def subgraph(self, *, entity_id: str, depth: int, focus, max_nodes: int, max_edges: int):  # noqa: ARG002
        self.calls += 1
        return GraphSubgraphResponse(
            focus=focus,
            depth=depth,
            truncated=False,
            node_limit=max_nodes,
            edge_limit=max_edges,
            graph=GraphPayload(
                nodes=[
                    GraphNode(
                        id=focus.id,
                        label=focus.name,
                        kind=focus.kind,
                        source=focus.source,
                        tags=[],
                    )
                ],
                edges=[],
            ),
            inbound_count=0,
            outbound_count=0,
        )


class _PlatformServices:
    def __init__(self) -> None:
        self.cache = _MemoryCache()
        self.search = _MemorySearchBackend()
        self.graph = _NullGraphBackend()


def _storage_for(tmp_path: Path) -> AppStorage:
    storage = AppStorage(tmp_path / "eip.db")
    storage.initialize()
    return storage


def test_cached_query_services_return_cached_payloads_without_recomputing(tmp_path: Path) -> None:
    storage = _storage_for(tmp_path)
    snapshot = build_demo_snapshot().model_copy(update={"generated_at": "2026-03-21T00:00:00Z"})
    storage.save_snapshot(snapshot)
    engine = AccessGraphEngine(snapshot)
    platform_services = _PlatformServices()

    entitlement_service = EntitlementService(lambda: engine, storage, platform_services)
    explain_service = ExplainService(lambda: engine, platform_services)
    graph_service = GraphService(lambda: engine, platform_services)
    whatif_service = WhatIfService(lambda: engine, platform_services)
    risk_service = RiskService(lambda: engine, storage, platform_services)

    overview = entitlement_service.overview()
    catalog = entitlement_service.catalog()
    explanation = explain_service.explain("user_alice", "res_folder_payroll")
    subgraph = graph_service.subgraph("user_alice", depth=2)
    simulation = whatif_service.simulate("rel_finance_into_payroll_editors", "res_folder_payroll")
    findings = risk_service.list_findings(limit=10)

    engine.get_overview = lambda: (_ for _ in ()).throw(RuntimeError("overview should come from cache"))  # type: ignore[method-assign]
    engine.get_catalog = lambda: (_ for _ in ()).throw(RuntimeError("catalog should come from cache"))  # type: ignore[method-assign]
    engine.explain = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("explain should come from cache"))  # type: ignore[method-assign]
    engine.simulate_edge_removal = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("what-if should come from cache"))  # type: ignore[method-assign]
    engine.materialized_access_index = lambda: (_ for _ in ()).throw(RuntimeError("risk should come from cache"))  # type: ignore[method-assign]
    engine.relationships = []

    assert entitlement_service.overview() == overview
    assert entitlement_service.catalog() == catalog
    assert explain_service.explain("user_alice", "res_folder_payroll") == explanation
    assert graph_service.subgraph("user_alice", depth=2) == subgraph
    assert whatif_service.simulate("rel_finance_into_payroll_editors", "res_folder_payroll") == simulation
    assert risk_service.list_findings(limit=10) == findings


def test_search_service_caches_results_above_search_backend(tmp_path: Path) -> None:
    storage = _storage_for(tmp_path)
    snapshot = build_demo_snapshot().model_copy(update={"generated_at": "2026-03-21T00:00:00Z"})
    storage.save_snapshot(snapshot)
    engine = AccessGraphEngine(snapshot)
    platform_services = _PlatformServices()
    search_service = SearchService(lambda: engine, platform_services)

    first = search_service.search("alice")
    second = search_service.search("alice")

    assert first
    assert second == first
    assert platform_services.search.calls == 1


def test_search_service_reranks_exact_identity_matches_above_noisy_resource_hits() -> None:
    class _Engine:
        def __init__(self) -> None:
            self.snapshot = SimpleNamespace(generated_at="2026-03-22T00:00:00Z")

        def search(self, query: str):  # noqa: ARG002
            return [
                SearchResult.model_validate(
                    {
                        "entity": {
                            "id": "res_system_dll",
                            "name": r"C:\Windows\System32\system.dll",
                            "kind": "resource",
                            "source": "Windows Filesystem",
                            "environment": "on-prem",
                        },
                        "headline": "Resource via Windows Filesystem",
                        "keywords": ["windows", "resource"],
                    }
                ),
                SearchResult.model_validate(
                    {
                        "entity": {
                            "id": "principal_system",
                            "name": r"NT AUTHORITY\SYSTEM",
                            "kind": "service_account",
                            "source": "Windows Local Identity",
                            "environment": "on-prem",
                        },
                        "headline": "Service Account via Windows Local Identity",
                        "keywords": ["identity", "windows"],
                    }
                ),
            ]

    platform_services = _PlatformServices()
    search_service = SearchService(lambda: _Engine(), platform_services)

    results = search_service.search("SYSTEM")

    assert results[0].entity.id == "principal_system"
    assert results[1].entity.id == "res_system_dll"


def test_graph_service_prefers_external_graph_backend_when_available(tmp_path: Path) -> None:
    storage = _storage_for(tmp_path)
    snapshot = build_demo_snapshot().model_copy(update={"generated_at": "2026-03-21T00:00:00Z"})
    storage.save_snapshot(snapshot)
    engine = AccessGraphEngine(snapshot)
    platform_services = _PlatformServices()
    platform_services.graph = _ExternalGraphBackend()
    graph_service = GraphService(lambda: engine, platform_services)

    first = graph_service.subgraph("user_alice", depth=2)
    second = graph_service.subgraph("user_alice", depth=2)

    assert first.focus.id == "user_alice"
    assert second == first
    assert platform_services.graph.calls == 1


def test_graph_service_caps_dense_subgraphs(tmp_path: Path) -> None:
    storage = _storage_for(tmp_path)
    snapshot = build_demo_snapshot().model_copy(update={"generated_at": "2026-03-22T00:00:00Z"})
    snapshot = snapshot.model_copy(
        update={
            "entities": [
                *snapshot.entities,
                *[
                    snapshot.entities[0].model_copy(
                        update={
                            "id": f"res_extra_{index}",
                            "name": f"Extra Resource {index}",
                            "kind": "resource",
                            "source": "Synthetic",
                            "tags": ["resource"],
                        }
                    )
                        for index in range(30)
                ],
            ],
            "relationships": [
                *snapshot.relationships,
                *[
                    snapshot.relationships[0].model_copy(
                        update={
                            "id": f"rel_extra_{index}",
                            "source": "user_alice",
                            "target": f"res_extra_{index}",
                            "label": f"Allow Read on Extra Resource {index}",
                            "kind": "direct_acl",
                            "permissions": ["Read"],
                        }
                    )
                        for index in range(30)
                ],
            ],
        }
    )
    storage.save_snapshot(snapshot)
    engine = AccessGraphEngine(snapshot)
    platform_services = _PlatformServices()
    graph_service = GraphService(lambda: engine, platform_services)

    response = graph_service.subgraph("user_alice", depth=1, max_nodes=20, max_edges=20)

    assert response.truncated is True
    assert response.node_limit == 20
    assert response.edge_limit == 20
    assert len(response.graph.nodes) <= 20
    assert len(response.graph.edges) <= 20
