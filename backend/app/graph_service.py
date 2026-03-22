from __future__ import annotations

from collections.abc import Callable

from app.models import GraphEdge, GraphNode, GraphPayload, GraphSubgraphResponse


class GraphService:
    def __init__(self, engine_getter: Callable[[], object], platform_services) -> None:
        self._engine_getter = engine_getter
        self._platform_services = platform_services

    @staticmethod
    def _relationship_priority(relationship, *, focus_id: str) -> tuple[int, int, int, str]:
        focus_connected = int(relationship.source == focus_id or relationship.target == focus_id)
        permission_edge = int(bool(getattr(relationship, "permissions", [])))
        highlighted_kind = int(relationship.kind in {"direct_acl", "member_of", "nested_group", "has_role"})
        return (
            -focus_connected,
            -permission_edge,
            -highlighted_kind,
            relationship.label.lower(),
        )

    def subgraph(
        self,
        entity_id: str,
        depth: int = 1,
        *,
        max_nodes: int = 160,
        max_edges: int = 320,
    ) -> GraphSubgraphResponse:
        engine = self._engine_getter()
        focus = engine._summary(entity_id)
        resolved_depth = max(1, min(int(depth), 4))
        resolved_max_nodes = max(20, min(int(max_nodes), 800))
        resolved_max_edges = max(20, min(int(max_edges), 2000))
        cache_key = (
            f"graph:{engine.snapshot.generated_at}:{entity_id}:{resolved_depth}:"
            f"{resolved_max_nodes}:{resolved_max_edges}"
        )
        cached = self._platform_services.cache.get_json(cache_key)
        if cached is not None:
            return GraphSubgraphResponse.model_validate(cached)

        external_response = self._platform_services.graph.subgraph(
            entity_id=entity_id,
            depth=resolved_depth,
            focus=focus,
            max_nodes=resolved_max_nodes,
            max_edges=resolved_max_edges,
        )
        if external_response is not None:
            self._platform_services.cache.set_json(
                cache_key,
                external_response.model_dump(mode="json"),
                ttl_seconds=600,
            )
            return external_response

        selected_nodes = {entity_id}
        frontier = {entity_id}
        selected_edges = {}
        truncated = False
        for _ in range(resolved_depth):
            if len(selected_nodes) >= resolved_max_nodes or len(selected_edges) >= resolved_max_edges:
                truncated = True
                break
            next_frontier: set[str] = set()
            connected_relationships = [
                relationship
                for relationship in engine.relationships
                if relationship.source in frontier or relationship.target in frontier
            ]
            connected_relationships.sort(
                key=lambda relationship: self._relationship_priority(
                    relationship,
                    focus_id=entity_id,
                )
            )
            processed_relationships = 0
            for relationship in connected_relationships:
                if len(selected_edges) >= resolved_max_edges:
                    truncated = True
                    break
                candidate_nodes = {relationship.source, relationship.target}
                new_nodes = [node_id for node_id in candidate_nodes if node_id not in selected_nodes]
                if new_nodes and len(selected_nodes) + len(new_nodes) > resolved_max_nodes:
                    truncated = True
                    continue
                selected_edges[relationship.id] = relationship
                processed_relationships += 1
                for node_id in candidate_nodes:
                    if node_id not in selected_nodes:
                        next_frontier.add(node_id)
                    selected_nodes.add(node_id)
            if processed_relationships < len(connected_relationships):
                truncated = True
            frontier = next_frontier
            if not frontier:
                break

        nodes = [
            GraphNode(
                id=entity.id,
                label=entity.name,
                kind=entity.kind,
                source=entity.source,
                tags=entity.tags[:4],
            )
            for entity in sorted(
                (engine.entities[node_id] for node_id in selected_nodes if node_id in engine.entities),
                key=lambda item: (item.id != entity_id, item.kind, item.name.lower()),
            )
        ]
        edges = [
            GraphEdge(
                id=relationship.id,
                source=relationship.source,
                target=relationship.target,
                label=relationship.label,
                kind=relationship.kind,
                highlighted=relationship.source == entity_id or relationship.target == entity_id,
            )
            for relationship in sorted(
                selected_edges.values(),
                key=lambda item: (
                    item.source != entity_id and item.target != entity_id,
                    item.kind,
                    item.label.lower(),
                ),
            )
        ]
        inbound_count = sum(1 for relationship in engine.relationships if relationship.target == entity_id)
        outbound_count = sum(1 for relationship in engine.relationships if relationship.source == entity_id)
        truncated = (
            truncated
            or len(nodes) >= resolved_max_nodes
            or len(edges) >= resolved_max_edges
            or inbound_count + outbound_count > len(edges)
        )
        response = GraphSubgraphResponse(
            focus=focus,
            depth=resolved_depth,
            truncated=truncated,
            node_limit=resolved_max_nodes,
            edge_limit=resolved_max_edges,
            graph=GraphPayload(nodes=nodes, edges=edges),
            inbound_count=inbound_count,
            outbound_count=outbound_count,
        )
        self._platform_services.cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=600,
        )
        return response
