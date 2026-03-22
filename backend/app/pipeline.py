from __future__ import annotations

from dataclasses import dataclass

from app.integration_collectors import CollectionBundle
from app.models import ConnectorStatus, Entity, InsightNote, Relationship, ScanTarget, Snapshot


@dataclass
class RawCollectionBatch:
    generated_at: str
    targets: list[ScanTarget]
    base_snapshot: Snapshot
    configured_bundles: list[CollectionBundle]
    imported_bundles: list[CollectionBundle]
    raw_collector_payload: dict[str, object]
    notes: list[str]
    warning_count: int
    privileged_path_count: int
    broad_access_count: int
    cache_hits: int
    cache_misses: int
    cache_records_by_target: dict[str, list[dict[str, object]]]


class NormalizationPipeline:
    def normalize(
        self,
        batch: RawCollectionBatch,
        *,
        tenant_name: str | None,
    ) -> Snapshot:
        bundles = [*batch.configured_bundles, *batch.imported_bundles]
        snapshot = batch.base_snapshot.model_copy(
            update={
                "tenant": tenant_name or batch.base_snapshot.tenant,
                "entities": self._merge_entities(batch.base_snapshot.entities, bundles),
                "relationships": self._merge_relationships(batch.base_snapshot.relationships, bundles),
                "connectors": self._merge_connectors(batch.base_snapshot.connectors, bundles),
                "insights": self._merge_insights(batch.base_snapshot.insights, bundles),
            }
        )
        return snapshot

    def serialize_raw_batch(self, batch: RawCollectionBatch) -> dict[str, object]:
        return {
            "generated_at": batch.generated_at,
            "targets": [target.model_dump(mode="json") for target in batch.targets],
            "filesystem_collector": batch.raw_collector_payload,
            "base_snapshot": batch.base_snapshot.model_dump(mode="json"),
            "configured_bundles": [self._serialize_bundle(bundle) for bundle in batch.configured_bundles],
            "imported_bundles": [self._serialize_bundle(bundle) for bundle in batch.imported_bundles],
            "notes": list(batch.notes),
            "warning_count": batch.warning_count,
            "privileged_path_count": batch.privileged_path_count,
            "broad_access_count": batch.broad_access_count,
            "cache_hits": batch.cache_hits,
            "cache_misses": batch.cache_misses,
        }

    def _serialize_bundle(self, bundle: CollectionBundle) -> dict[str, object]:
        return {
            "entities": [entity.model_dump(mode="json") for entity in bundle.entities],
            "relationships": [relationship.model_dump(mode="json") for relationship in bundle.relationships],
            "connectors": [connector.model_dump(mode="json") for connector in bundle.connectors],
            "insights": [insight.model_dump(mode="json") for insight in bundle.insights],
            "notes": list(bundle.notes),
            "runtime_status": (
                bundle.runtime_status.model_dump(mode="json") if bundle.runtime_status is not None else None
            ),
        }

    def _merge_entities(self, base_entities: list[Entity], bundles: list[CollectionBundle]) -> list[Entity]:
        merged = {entity.id: entity for entity in base_entities}
        for bundle in bundles:
            for entity in bundle.entities:
                existing = merged.get(entity.id)
                if existing is None or (len(entity.tags) + entity.risk_score) > (
                    len(existing.tags) + existing.risk_score
                ):
                    merged[entity.id] = entity
        return list(merged.values())

    def _merge_relationships(
        self,
        base_relationships: list[Relationship],
        bundles: list[CollectionBundle],
    ) -> list[Relationship]:
        merged = {relationship.id: relationship for relationship in base_relationships}
        for bundle in bundles:
            for relationship in bundle.relationships:
                merged[relationship.id] = relationship
        return list(merged.values())

    def _merge_connectors(
        self,
        base_connectors: list[ConnectorStatus],
        bundles: list[CollectionBundle],
    ) -> list[ConnectorStatus]:
        merged = {f"{connector.name}:{connector.source}": connector for connector in base_connectors}
        for bundle in bundles:
            for connector in bundle.connectors:
                merged[f"{connector.name}:{connector.source}"] = connector
        return list(merged.values())

    def _merge_insights(
        self,
        base_insights: list[InsightNote],
        bundles: list[CollectionBundle],
    ) -> list[InsightNote]:
        merged = {insight.title: insight for insight in base_insights}
        for bundle in bundles:
            for insight in bundle.insights:
                merged[insight.title] = insight
        return list(merged.values())[:10]
