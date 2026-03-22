from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.models import EntitySummary, GraphEdge, GraphNode, GraphPayload, GraphSubgraphResponse, PlatformComponentStatus, SearchResult, Snapshot

logger = logging.getLogger(__name__)

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency in local fallback mode
    redis = None

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover - optional dependency in local fallback mode
    GraphDatabase = None


OPENSEARCH_DOCS = "https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/"
CLICKHOUSE_DOCS = "https://clickhouse.com/docs/install/docker"
VALKEY_DOCS = "https://valkey.io/topics/quickstart/"
NEO4J_DOCS = "https://neo4j.com/docs/operations-manual/current/docker/introduction/"
KAFKA_DOCS = "https://kafka.apache.org/documentation/"
TEMPORAL_DOCS = "https://docs.temporal.io/self-hosted-guide/installation"
LANGFUSE_DOCS = "https://langfuse.com/docs/deployment/self-host"


class CacheBackend(ABC):
    name = "In-process cache"

    @abstractmethod
    def get_json(self, key: str) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> PlatformComponentStatus:
        raise NotImplementedError


class NullCacheBackend(CacheBackend):
    def get_json(self, key: str) -> Any | None:
        return None

    def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        return None

    def status(self) -> PlatformComponentStatus:
        return PlatformComponentStatus(
            id="valkey",
            name="Valkey cache",
            category="cache",
            state="optional",
            configured=False,
            connected=False,
            summary="Using in-process cache only.",
            details=[
                "Set EIP_VALKEY_URL to enable distributed caching for search and access responses.",
            ],
            documentation_url=VALKEY_DOCS,
        )


class ValkeyCacheBackend(CacheBackend):
    name = "Valkey"

    def __init__(self, url: str) -> None:
        self._url = url
        self._client = None
        self._connection_error: str | None = None
        if redis is None:  # pragma: no cover - dependency guard
            self._connection_error = "redis client library is not installed."
            return
        try:
            self._client = redis.from_url(url, decode_responses=True)
            self._client.ping()
        except Exception as exc:  # pragma: no cover - depends on runtime service
            self._connection_error = str(exc)
            self._client = None

    def get_json(self, key: str) -> Any | None:
        if self._client is None:
            return None
        raw = self._client.get(key)
        if not raw:
            return None
        return json.loads(raw)

    def set_json(self, key: str, payload: Any, ttl_seconds: int) -> None:
        if self._client is None:
            return
        self._client.set(key, json.dumps(payload), ex=max(30, ttl_seconds))

    def status(self) -> PlatformComponentStatus:
        if self._client is not None:
            return PlatformComponentStatus(
                id="valkey",
                name="Valkey cache",
                category="cache",
                state="active",
                configured=True,
                connected=True,
                summary="Distributed cache is active.",
                details=[
                    "Search, explain, graph, risk and materialized access responses can be shared across workers.",
                    f"Endpoint: {self._url}",
                ],
                documentation_url=VALKEY_DOCS,
            )

        return PlatformComponentStatus(
            id="valkey",
            name="Valkey cache",
            category="cache",
            state="error",
            configured=True,
            connected=False,
            summary="Valkey is configured but not reachable.",
            details=[self._connection_error or "Unable to connect to the configured Valkey endpoint."],
            documentation_url=VALKEY_DOCS,
        )


class SearchBackend(ABC):
    name = "In-memory search"

    @abstractmethod
    def index_snapshot(self, snapshot: Snapshot) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, fallback_results: list[SearchResult], snapshot: Snapshot) -> list[SearchResult]:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> PlatformComponentStatus:
        raise NotImplementedError


class GraphBackend(ABC):
    name = "In-memory graph"

    @abstractmethod
    def index_snapshot(self, snapshot: Snapshot) -> None:
        raise NotImplementedError

    @abstractmethod
    def subgraph(
        self,
        *,
        entity_id: str,
        depth: int,
        focus: EntitySummary,
        max_nodes: int,
        max_edges: int,
    ) -> GraphSubgraphResponse | None:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> PlatformComponentStatus:
        raise NotImplementedError


class InMemorySearchBackend(SearchBackend):
    def index_snapshot(self, snapshot: Snapshot) -> None:
        return None

    def search(self, query: str, fallback_results: list[SearchResult], snapshot: Snapshot) -> list[SearchResult]:
        return fallback_results

    def status(self) -> PlatformComponentStatus:
        return PlatformComponentStatus(
            id="opensearch",
            name="OpenSearch",
            category="search",
            state="optional",
            configured=False,
            connected=False,
            summary="Using the built-in in-memory search index.",
            details=[
                "Set EIP_OPENSEARCH_URL to enable external full-text search and autocomplete.",
            ],
            documentation_url=OPENSEARCH_DOCS,
        )


class NullGraphBackend(GraphBackend):
    def index_snapshot(self, snapshot: Snapshot) -> None:
        return None

    def subgraph(
        self,
        *,
        entity_id: str,
        depth: int,
        focus: EntitySummary,
        max_nodes: int,
        max_edges: int,
    ) -> GraphSubgraphResponse | None:
        return None

    def status(self) -> PlatformComponentStatus:
        return PlatformComponentStatus(
            id="neo4j",
            name="Neo4j graph backend",
            category="graph",
            state="optional",
            configured=False,
            connected=False,
            summary="Using the built-in relationship engine for graph traversal.",
            details=[
                "Set EIP_NEO4J_URI together with EIP_NEO4J_USERNAME and EIP_NEO4J_PASSWORD to enable a dedicated investigation graph backend.",
            ],
            documentation_url=NEO4J_DOCS,
        )


class Neo4jGraphBackend(GraphBackend):
    name = "Neo4j"

    def __init__(self, uri: str) -> None:
        self._uri = uri
        self._driver = None
        self._last_error: str | None = None
        if GraphDatabase is None:  # pragma: no cover - dependency guard
            self._last_error = "neo4j client library is not installed."
            return
        try:
            auth = None
            if settings.neo4j_username:
                auth = (settings.neo4j_username, settings.neo4j_password or "")
            self._driver = GraphDatabase.driver(uri, auth=auth)
            self._driver.verify_connectivity()
        except Exception as exc:  # pragma: no cover - depends on runtime service
            self._last_error = str(exc)
            self._driver = None

    def index_snapshot(self, snapshot: Snapshot) -> None:
        if self._driver is None:
            return
        try:
            entity_rows = [
                {
                    "entity_id": entity.id,
                    "name": entity.name,
                    "kind": entity.kind,
                    "source": entity.source,
                    "environment": entity.environment,
                    "description": entity.description,
                    "tags": list(entity.tags),
                    "risk_score": int(entity.risk_score),
                    "criticality": int(entity.criticality),
                    "owner": entity.owner,
                    "snapshot_generated_at": snapshot.generated_at,
                }
                for entity in snapshot.entities
            ]
            relationship_rows = [
                {
                    "relationship_id": relationship.id,
                    "source": relationship.source,
                    "target": relationship.target,
                    "label": relationship.label,
                    "kind": relationship.kind,
                    "rationale": relationship.rationale,
                    "permissions": list(relationship.permissions),
                    "inherits": bool(relationship.inherits),
                    "temporary": bool(relationship.temporary),
                    "expires_at": relationship.expires_at,
                    "removable": bool(relationship.removable),
                    "metadata_json": json.dumps(relationship.metadata),
                    "snapshot_generated_at": snapshot.generated_at,
                }
                for relationship in snapshot.relationships
            ]
            with self._driver.session() as session:
                session.run("MATCH (n:EipEntity) DETACH DELETE n").consume()
                session.run(
                    """
                    UNWIND $entities AS entity
                    CREATE (n:EipEntity {
                        entity_id: entity.entity_id,
                        name: entity.name,
                        kind: entity.kind,
                        source: entity.source,
                        environment: entity.environment,
                        description: entity.description,
                        tags: entity.tags,
                        risk_score: entity.risk_score,
                        criticality: entity.criticality,
                        owner: entity.owner,
                        snapshot_generated_at: entity.snapshot_generated_at
                    })
                    """,
                    entities=entity_rows,
                ).consume()
                session.run(
                    """
                    UNWIND $relationships AS rel
                    MATCH (source:EipEntity {entity_id: rel.source})
                    MATCH (target:EipEntity {entity_id: rel.target})
                    CREATE (source)-[r:EIP_REL {
                        relationship_id: rel.relationship_id,
                        label: rel.label,
                        kind: rel.kind,
                        rationale: rel.rationale,
                        permissions: rel.permissions,
                        inherits: rel.inherits,
                        temporary: rel.temporary,
                        expires_at: rel.expires_at,
                        removable: rel.removable,
                        metadata_json: rel.metadata_json,
                        snapshot_generated_at: rel.snapshot_generated_at
                    }]->(target)
                    """,
                    relationships=relationship_rows,
                ).consume()
            self._last_error = None
        except Exception as exc:  # pragma: no cover - network dependent
            self._last_error = str(exc)
            logger.warning("Neo4j indexing failed: %s", exc)

    def subgraph(
        self,
        *,
        entity_id: str,
        depth: int,
        focus: EntitySummary,
        max_nodes: int,
        max_edges: int,
    ) -> GraphSubgraphResponse | None:
        if self._driver is None:
            return None
        resolved_depth = max(1, min(int(depth), 4))
        resolved_max_nodes = max(20, min(int(max_nodes), 800))
        resolved_max_edges = max(20, min(int(max_edges), 2000))
        try:
            with self._driver.session() as session:
                query = f"""
                MATCH (focus:EipEntity {{entity_id: $entity_id}})
                OPTIONAL MATCH path=(focus)-[:EIP_REL*1..{resolved_depth}]-(neighbor:EipEntity)
                RETURN focus, collect(path)[0..$path_limit] AS paths
                """
                record = session.run(
                    query,
                    entity_id=entity_id,
                    path_limit=max(resolved_max_edges, resolved_max_nodes),
                ).single()
                if record is None or record.get("focus") is None:
                    return None
                node_map: dict[str, GraphNode] = {}
                edge_map: dict[str, GraphEdge] = {}
                focus_node = record["focus"]
                node_map[str(focus_node["entity_id"])] = GraphNode(
                    id=str(focus_node["entity_id"]),
                    label=str(focus_node["name"]),
                    kind=str(focus_node["kind"]),
                    source=str(focus_node["source"]),
                    tags=[str(item) for item in (focus_node.get("tags") or [])[:4]],
                )
                for path in record["paths"] or []:
                    if path is None:
                        continue
                    for node in path.nodes:
                        node_id = str(node["entity_id"])
                        if node_id not in node_map:
                            node_map[node_id] = GraphNode(
                                id=node_id,
                                label=str(node["name"]),
                                kind=str(node["kind"]),
                                source=str(node["source"]),
                                tags=[str(item) for item in (node.get("tags") or [])[:4]],
                            )
                    for relationship in path.relationships:
                        relationship_id = str(relationship["relationship_id"])
                        if relationship_id not in edge_map:
                            edge_map[relationship_id] = GraphEdge(
                                id=relationship_id,
                                source=str(relationship.start_node["entity_id"]),
                                target=str(relationship.end_node["entity_id"]),
                                label=str(relationship["label"]),
                                kind=str(relationship["kind"]),
                                highlighted=(
                                    str(relationship.start_node["entity_id"]) == entity_id
                                    or str(relationship.end_node["entity_id"]) == entity_id
                                ),
                            )
                inbound_count = session.run(
                    """
                    MATCH (:EipEntity)-[r:EIP_REL]->(focus:EipEntity {entity_id: $entity_id})
                    RETURN count(r) AS inbound_count
                    """,
                    entity_id=entity_id,
                ).single()
                outbound_count = session.run(
                    """
                    MATCH (focus:EipEntity {entity_id: $entity_id})-[r:EIP_REL]->(:EipEntity)
                    RETURN count(r) AS outbound_count
                    """,
                    entity_id=entity_id,
                ).single()
            self._last_error = None
            sorted_nodes = sorted(
                node_map.values(),
                key=lambda item: (item.id != entity_id, item.kind, item.label.lower()),
            )
            kept_nodes = sorted_nodes[:resolved_max_nodes]
            kept_node_ids = {item.id for item in kept_nodes}
            sorted_edges = sorted(
                (
                    edge
                    for edge in edge_map.values()
                    if edge.source in kept_node_ids and edge.target in kept_node_ids
                ),
                key=lambda item: (
                    item.source != entity_id and item.target != entity_id,
                    item.kind,
                    item.label.lower(),
                ),
            )
            kept_edges = sorted_edges[:resolved_max_edges]
            return GraphSubgraphResponse(
                focus=focus,
                depth=resolved_depth,
                truncated=len(node_map) > len(kept_nodes) or len(edge_map) > len(kept_edges),
                node_limit=resolved_max_nodes,
                edge_limit=resolved_max_edges,
                graph=GraphPayload(
                    nodes=kept_nodes,
                    edges=kept_edges,
                ),
                inbound_count=int(inbound_count["inbound_count"]) if inbound_count is not None else 0,
                outbound_count=int(outbound_count["outbound_count"]) if outbound_count is not None else 0,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            self._last_error = str(exc)
            logger.warning("Neo4j graph query failed: %s", exc)
            return None

    def status(self) -> PlatformComponentStatus:
        if self._driver is None:
            return PlatformComponentStatus(
                id="neo4j",
                name="Neo4j graph backend",
                category="graph",
                state="error",
                configured=True,
                connected=False,
                summary="Neo4j is configured but not reachable.",
                details=[self._last_error or "Unable to connect to the configured Neo4j endpoint."],
                documentation_url=NEO4J_DOCS,
            )
        try:
            with self._driver.session() as session:
                version_record = session.run("CALL dbms.components() YIELD versions RETURN versions[0] AS version").single()
                node_count_record = session.run("MATCH (n:EipEntity) RETURN count(n) AS node_count").single()
                edge_count_record = session.run("MATCH ()-[r:EIP_REL]->() RETURN count(r) AS edge_count").single()
            self._last_error = None
            details = [f"URI: {self._uri}"]
            if version_record is not None and version_record.get("version") is not None:
                details.append(f"Version: {version_record['version']}")
            if node_count_record is not None:
                details.append(f"Indexed nodes: {int(node_count_record['node_count'])}")
            if edge_count_record is not None:
                details.append(f"Indexed relationships: {int(edge_count_record['edge_count'])}")
            return PlatformComponentStatus(
                id="neo4j",
                name="Neo4j graph backend",
                category="graph",
                state="active",
                configured=True,
                connected=True,
                summary="Dedicated investigation graph backend is active.",
                details=details,
                documentation_url=NEO4J_DOCS,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            self._last_error = str(exc)
            return PlatformComponentStatus(
                id="neo4j",
                name="Neo4j graph backend",
                category="graph",
                state="error",
                configured=True,
                connected=False,
                summary="Neo4j is configured but not reachable.",
                details=[self._last_error],
                documentation_url=NEO4J_DOCS,
            )


class OpenSearchBackend(SearchBackend):
    name = "OpenSearch"

    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")
        self._index = settings.opensearch_index
        self._auth = None
        self._last_error: str | None = None
        if settings.opensearch_username and settings.opensearch_password:
            self._auth = (settings.opensearch_username, settings.opensearch_password)

    def index_snapshot(self, snapshot: Snapshot) -> None:
        try:
            self._ensure_index()
            payload_lines: list[str] = []
            for entity in snapshot.entities:
                doc = {
                    "entity_id": entity.id,
                    "snapshot_generated_at": snapshot.generated_at,
                    "name": entity.name,
                    "name_prefix": entity.name,
                    "description": entity.description,
                    "source": entity.source,
                    "kind": entity.kind,
                    "environment": entity.environment,
                    "tags": entity.tags,
                    "summary": {
                        "id": entity.id,
                        "name": entity.name,
                        "kind": entity.kind,
                        "source": entity.source,
                        "environment": entity.environment,
                    },
                    "headline": f"{entity.kind.replace('_', ' ').title()} via {entity.source}",
                    "keywords": entity.tags[:6],
                }
                payload_lines.append(json.dumps({"index": {"_index": self._index, "_id": entity.id}}))
                payload_lines.append(json.dumps(doc))

            if payload_lines:
                response = self._request(
                    "POST",
                    "/_bulk",
                    content="\n".join(payload_lines) + "\n",
                    headers={"Content-Type": "application/x-ndjson"},
                )
                errors = bool(response.json().get("errors"))
                if errors:
                    raise RuntimeError("OpenSearch bulk indexing returned partial failures.")
                self._request(
                    "POST",
                    f"/{self._index}/_delete_by_query?conflicts=proceed&refresh=true",
                    json={
                        "query": {
                        "bool": {
                            "must_not": [
                                    {"term": {"snapshot_generated_at": snapshot.generated_at}}
                                ]
                            }
                        }
                    },
                )
            self._last_error = None
        except Exception as exc:  # pragma: no cover - network dependent
            self._last_error = str(exc)
            logger.warning("OpenSearch indexing failed: %s", exc)

    def search(self, query: str, fallback_results: list[SearchResult], snapshot: Snapshot) -> list[SearchResult]:
        try:
            response = self._request(
                "POST",
                f"/{self._index}/_search",
                json={
                    "size": 8,
                    "_source": ["summary", "headline", "keywords"],
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "fields": [
                                            "name^4",
                                            "name_prefix^6",
                                            "description^2",
                                            "source^2",
                                            "tags^2",
                                            "kind",
                                        ],
                                        "type": "best_fields",
                                        "fuzziness": "AUTO",
                                    }
                                }
                            ],
                            "should": [
                                {
                                    "multi_match": {
                                        "query": query,
                                        "type": "bool_prefix",
                                        "fields": [
                                            "name_prefix",
                                            "name_prefix._2gram",
                                            "name_prefix._3gram",
                                        ],
                                        "boost": 4,
                                    }
                                },
                                {
                                    "match_phrase_prefix": {
                                        "name": {
                                            "query": query,
                                            "boost": 3,
                                        }
                                    }
                                },
                                {
                                    "term": {
                                        "name.keyword": {
                                            "value": query,
                                            "boost": 8,
                                        }
                                    }
                                },
                            ],
                            "filter": [
                                {"term": {"snapshot_generated_at": snapshot.generated_at}}
                            ],
                        }
                    },
                    "sort": [{"_score": {"order": "desc"}}, {"name.keyword": {"order": "asc"}}],
                },
            )
            hits = response.json().get("hits", {}).get("hits", [])
            payload = []
            for hit in hits:
                source = hit.get("_source", {})
                payload.append(
                    SearchResult.model_validate(
                        {
                            "entity": source.get("summary", {}),
                            "headline": source.get("headline", "Indexed result"),
                            "keywords": source.get("keywords", []),
                        }
                    )
                )
            self._last_error = None
            return payload or fallback_results
        except Exception as exc:  # pragma: no cover - network dependent
            self._last_error = str(exc)
            logger.warning("OpenSearch query failed: %s", exc)
            return fallback_results

    def status(self) -> PlatformComponentStatus:
        try:
            response = self._request("GET", "/")
            version = response.json().get("version", {}).get("number")
            self._last_error = None
            details = [f"Endpoint: {self._url}", f"Index: {self._index}"]
            if version:
                details.append(f"Version: {version}")
            return PlatformComponentStatus(
                id="opensearch",
                name="OpenSearch",
                category="search",
                state="active",
                configured=True,
                connected=True,
                summary="External search backend is active.",
                details=details,
                documentation_url=OPENSEARCH_DOCS,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            self._last_error = str(exc)
            return PlatformComponentStatus(
                id="opensearch",
                name="OpenSearch",
                category="search",
                state="error",
                configured=True,
                connected=False,
                summary="OpenSearch is configured but not reachable.",
                details=[self._last_error],
                documentation_url=OPENSEARCH_DOCS,
            )

    def _ensure_index(self) -> None:
        response = self._request("HEAD", f"/{self._index}")
        if response.status_code != 404:
            return
        self._request(
            "PUT",
            f"/{self._index}",
            json={
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                },
                "mappings": {
                    "properties": {
                        "snapshot_generated_at": {"type": "keyword"},
                        "name": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                        },
                        "name_prefix": {"type": "search_as_you_type"},
                        "description": {"type": "text"},
                        "source": {"type": "keyword"},
                        "kind": {"type": "keyword"},
                        "environment": {"type": "keyword"},
                        "tags": {"type": "keyword"},
                    }
                },
            },
        )

    def _request(self, method: str, path: str, **kwargs):
        with httpx.Client(
            base_url=self._url,
            auth=self._auth,
            timeout=10.0,
            verify=settings.opensearch_verify_tls,
        ) as client:
            response = client.request(method, path, **kwargs)
            if response.status_code >= 400 and not (
                method.upper() == "HEAD" and response.status_code == 404
            ):
                response.raise_for_status()
            return response


class AnalyticsBackend(ABC):
    name = "Scan runs table"

    @abstractmethod
    def record_scan(self, run_payload: dict[str, object]) -> None:
        raise NotImplementedError

    @abstractmethod
    def record_query(self, query_payload: dict[str, object]) -> None:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> PlatformComponentStatus:
        raise NotImplementedError


class NullAnalyticsBackend(AnalyticsBackend):
    def record_scan(self, run_payload: dict[str, object]) -> None:
        return None

    def record_query(self, query_payload: dict[str, object]) -> None:
        return None

    def status(self) -> PlatformComponentStatus:
        return PlatformComponentStatus(
            id="clickhouse",
            name="ClickHouse",
            category="analytics",
            state="optional",
            configured=False,
            connected=False,
            summary="Analytics stay inside the transactional store only.",
            details=[
                "Set EIP_CLICKHOUSE_URL to stream scan metrics into a dedicated analytics backend.",
            ],
            documentation_url=CLICKHOUSE_DOCS,
        )


class ClickHouseAnalyticsBackend(AnalyticsBackend):
    name = "ClickHouse"

    def __init__(self, url: str) -> None:
        self._url = url.rstrip("/")
        self._database = self._safe_identifier(settings.clickhouse_database, "eip")
        self._last_error: str | None = None
        self._auth = None
        if settings.clickhouse_username:
            self._auth = (settings.clickhouse_username, settings.clickhouse_password or "")

    def record_scan(self, run_payload: dict[str, object]) -> None:
        try:
            self._ensure_tables()
            self._request(
                f"INSERT INTO {self._database}.scan_runs FORMAT JSONEachRow",
                content=json.dumps(run_payload),
                headers={"Content-Type": "application/json"},
            )
            self._last_error = None
        except Exception as exc:  # pragma: no cover - network dependent
            self._last_error = str(exc)
            logger.warning("ClickHouse analytics write failed: %s", exc)

    def record_query(self, query_payload: dict[str, object]) -> None:
        try:
            self._ensure_tables()
            self._request(
                f"INSERT INTO {self._database}.query_metrics FORMAT JSONEachRow",
                content=json.dumps(query_payload),
                headers={"Content-Type": "application/json"},
            )
            self._last_error = None
        except Exception as exc:  # pragma: no cover - network dependent
            self._last_error = str(exc)
            logger.warning("ClickHouse query analytics write failed: %s", exc)

    def status(self) -> PlatformComponentStatus:
        try:
            version = self._request("SELECT version()").text.strip()
            scan_count = self._request(
                f"SELECT count() FROM {self._database}.scan_runs FORMAT TabSeparatedRaw"  # nosec B608
            ).text.strip()
            query_count = self._request(
                f"SELECT count() FROM {self._database}.query_metrics FORMAT TabSeparatedRaw"  # nosec B608
            ).text.strip()
            self._last_error = None
            return PlatformComponentStatus(
                id="clickhouse",
                name="ClickHouse",
                category="analytics",
                state="active",
                configured=True,
                connected=True,
                summary="High-cardinality analytics backend is active.",
                details=[
                    f"Endpoint: {self._url}",
                    f"Database: {self._database}",
                    f"Version: {version}",
                    f"Stored scan analytics rows: {scan_count}",
                    f"Stored query analytics rows: {query_count}",
                ],
                documentation_url=CLICKHOUSE_DOCS,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            self._last_error = str(exc)
            return PlatformComponentStatus(
                id="clickhouse",
                name="ClickHouse",
                category="analytics",
                state="error",
                configured=True,
                connected=False,
                summary="ClickHouse is configured but not reachable.",
                details=[self._last_error],
                documentation_url=CLICKHOUSE_DOCS,
            )

    def _ensure_tables(self) -> None:
        self._request(
            f"CREATE DATABASE IF NOT EXISTS {self._database}"  # nosec B608
        )
        self._request(
            f"""  # nosec B608
            CREATE TABLE IF NOT EXISTS {self._database}.scan_runs (
                recorded_at DateTime64(3),
                run_id String,
                tenant String,
                snapshot_generated_at String,
                status String,
                duration_ms Float64,
                target_count UInt32,
                resource_count UInt32,
                principal_count UInt32,
                relationship_count UInt32,
                warning_count UInt32,
                privileged_path_count UInt32,
                broad_access_count UInt32
            ) ENGINE = MergeTree
            ORDER BY (recorded_at, run_id)
            """
        )
        self._request(
            f"""  # nosec B608
            CREATE TABLE IF NOT EXISTS {self._database}.query_metrics (
                recorded_at DateTime64(3),
                operation String,
                duration_ms Float64,
                status_code UInt16,
                request_path String
            ) ENGINE = MergeTree
            ORDER BY (recorded_at, operation)
            """
        )

    def _safe_identifier(self, value: str, fallback: str) -> str:
        candidate = (value or "").strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate):
            return candidate
        logger.warning("Invalid ClickHouse identifier '%s'. Falling back to '%s'.", value, fallback)
        return fallback

    def _request(self, query: str, **kwargs):
        with httpx.Client(
            timeout=10.0,
            verify=settings.clickhouse_verify_tls,
            auth=self._auth,
        ) as client:
            response = client.post(
                self._url,
                params={"query": " ".join(query.split())},
                **kwargs,
            )
            response.raise_for_status()
            return response


@dataclass
class PlatformServices:
    cache: CacheBackend
    search: SearchBackend
    graph: GraphBackend
    analytics: AnalyticsBackend


def build_platform_services() -> PlatformServices:
    cache_backend: CacheBackend
    if settings.valkey_url:
        cache_backend = ValkeyCacheBackend(settings.valkey_url)
    else:
        cache_backend = NullCacheBackend()

    search_backend: SearchBackend
    if settings.opensearch_url:
        search_backend = OpenSearchBackend(settings.opensearch_url)
    else:
        search_backend = InMemorySearchBackend()

    graph_backend: GraphBackend
    if settings.neo4j_uri:
        graph_backend = Neo4jGraphBackend(settings.neo4j_uri)
    else:
        graph_backend = NullGraphBackend()

    analytics_backend: AnalyticsBackend
    if settings.clickhouse_url:
        analytics_backend = ClickHouseAnalyticsBackend(settings.clickhouse_url)
    else:
        analytics_backend = NullAnalyticsBackend()

    return PlatformServices(
        cache=cache_backend,
        search=search_backend,
        graph=graph_backend,
        analytics=analytics_backend,
    )


def configured_component_status(
    *,
    component_id: str,
    name: str,
    category: str,
    configured: bool,
    summary_enabled: str,
    summary_disabled: str,
    documentation_url: str,
    details: list[str] | None = None,
) -> PlatformComponentStatus:
    return PlatformComponentStatus(
        id=component_id,
        name=name,
        category=category,
        state="configured" if configured else "optional",
        configured=configured,
        connected=False,
        summary=summary_enabled if configured else summary_disabled,
        details=details or [],
        documentation_url=documentation_url,
    )
