from __future__ import annotations

from dataclasses import dataclass
import json

from app.auth import utc_now_iso
from app.engine import AccessGraphEngine
from app.models import Entity, IndexRefreshSummary, Relationship, Snapshot
from app.storage import AppStorage

SAFE_DELTA_RELATIONSHIP_KINDS = {
    "member_of",
    "nested_group",
    "delegated_access",
    "assigned_role",
    "direct_acl",
    "role_grant",
}
FULL_REBUILD_RELATIONSHIP_KINDS = {"contains", "deny_acl"}
GROUP_CLOSURE_RELATIONSHIP_KINDS = {"member_of", "nested_group"}


@dataclass(frozen=True)
class _SnapshotDiff:
    added_entities: dict[str, Entity]
    removed_entities: dict[str, Entity]
    changed_entities: dict[str, tuple[Entity, Entity]]
    added_relationships: dict[str, Relationship]
    removed_relationships: dict[str, Relationship]
    changed_relationships: dict[str, tuple[Relationship, Relationship]]

    @property
    def changed_entity_count(self) -> int:
        return len(self.added_entities) + len(self.removed_entities) + len(self.changed_entities)

    @property
    def changed_relationship_count(self) -> int:
        return (
            len(self.added_relationships)
            + len(self.removed_relationships)
            + len(self.changed_relationships)
        )

    def relationship_kinds(self) -> set[str]:
        kinds = {relationship.kind for relationship in self.added_relationships.values()}
        kinds.update(relationship.kind for relationship in self.removed_relationships.values())
        kinds.update(
            current.kind
            for _, current in self.changed_relationships.values()
        )
        kinds.update(
            previous.kind
            for previous, _ in self.changed_relationships.values()
        )
        return kinds


class IndexRefreshService:
    _SUMMARY_KEY = "runtime_index_refresh_summary"

    def __init__(self, storage: AppStorage) -> None:
        self._storage = storage

    def load_last_summary(self, snapshot_generated_at: str | None = None) -> IndexRefreshSummary | None:
        raw = self._storage.get_setting(self._SUMMARY_KEY)
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        summary = IndexRefreshSummary.model_validate(payload)
        if snapshot_generated_at and summary.generated_at != snapshot_generated_at:
            return None
        return summary

    def ensure_indexes(
        self,
        snapshot: Snapshot,
        engine: AccessGraphEngine,
    ) -> IndexRefreshSummary:
        if self._indexes_exist(snapshot.generated_at):
            existing_summary = self.load_last_summary(snapshot.generated_at)
            if existing_summary is not None:
                return existing_summary
            summary = IndexRefreshSummary(
                generated_at=snapshot.generated_at,
                mode="existing",
                total_access_rows=self._storage.materialized_access_index_stats(snapshot.generated_at)["row_count"],
                carried_forward_group_closure=self._storage.has_principal_group_closure(snapshot.generated_at),
                carried_forward_resource_hierarchy=self._storage.has_resource_hierarchy_closure(snapshot.generated_at),
            )
            self._save_summary(summary)
            return summary

        previous_snapshot = self._previous_snapshot(snapshot.generated_at)
        if previous_snapshot is None:
            return self._full_refresh(
                snapshot=snapshot,
                engine=engine,
                previous_snapshot_at=None,
                reasons=["No previous snapshot was available for incremental refresh."],
            )

        previous_rows = self._storage.list_materialized_access_index(previous_snapshot.generated_at)
        if not previous_rows:
            return self._full_refresh(
                snapshot=snapshot,
                engine=engine,
                previous_snapshot_at=previous_snapshot.generated_at,
                reasons=["The previous snapshot has no materialized access index to reuse."],
            )

        previous_engine = AccessGraphEngine(previous_snapshot)
        diff = self._diff_snapshots(previous_snapshot, snapshot)
        if diff.changed_entity_count == 0 and diff.changed_relationship_count == 0:
            return self._carry_forward_refresh(
                snapshot=snapshot,
                previous_snapshot=previous_snapshot,
                previous_rows=previous_rows,
            )

        fallback_reasons = self._full_rebuild_reasons(diff)
        access_rows: list[dict[str, object]]
        mode = "delta"
        reused_access_rows = 0
        recomputed_access_rows = 0
        impacted_principal_ids: set[str] = set()
        impacted_resource_ids: set[str] = set()

        if fallback_reasons:
            summary = self._full_refresh(
                snapshot=snapshot,
                engine=engine,
                previous_snapshot_at=previous_snapshot.generated_at,
                reasons=fallback_reasons,
                diff=diff,
            )
            return summary

        impacted_principal_ids, impacted_resource_ids = self._delta_access_scope(
            diff=diff,
            previous_engine=previous_engine,
            current_engine=engine,
            previous_rows=previous_rows,
        )

        total_principals = max(1, len(engine.principal_ids))
        total_resources = max(1, len(engine.resource_ids))
        if (
            len(impacted_principal_ids) > total_principals * 0.7
            or len(impacted_resource_ids) > total_resources * 0.7
        ):
            summary = self._full_refresh(
                snapshot=snapshot,
                engine=engine,
                previous_snapshot_at=previous_snapshot.generated_at,
                reasons=[
                    "Incremental scope expanded too far, so a full rebuild kept the index refresh deterministic."
                ],
                diff=diff,
            )
            return summary

        recompute_principal_ids = impacted_principal_ids.intersection(engine.principal_ids)
        recompute_resource_ids = impacted_resource_ids.intersection(engine.resource_ids)

        if recompute_principal_ids and recompute_resource_ids:
            current_rows = engine.materialized_access_index_for_scope(
                recompute_principal_ids,
                recompute_resource_ids,
            )
            impacted_principal_set = set(impacted_principal_ids)
            impacted_resource_set = set(impacted_resource_ids)
            access_rows = [
                row
                for row in previous_rows
                if row["principal_id"] in engine.entities
                and row["resource_id"] in engine.entities
                and not (
                    row["principal_id"] in impacted_principal_set
                    and row["resource_id"] in impacted_resource_set
                )
            ]
            access_rows.extend(current_rows)
            reused_access_rows = len(access_rows) - len(current_rows)
            recomputed_access_rows = len(current_rows)
        else:
            mode = "carry_forward"
            access_rows = [
                row
                for row in previous_rows
                if row["principal_id"] in engine.entities and row["resource_id"] in engine.entities
            ]
            reused_access_rows = len(access_rows)

        self._storage.save_materialized_access_index(snapshot.generated_at, access_rows)
        self._storage.save_resource_exposure_index(
            snapshot.generated_at,
            engine.resource_exposure_index_from_rows(access_rows),
        )
        self._storage.save_principal_access_summary(
            snapshot.generated_at,
            engine.principal_access_summary_index_from_rows(access_rows),
        )

        carried_forward_group_closure, recomputed_group_closure_principals = self._refresh_group_closure(
            snapshot=snapshot,
            previous_snapshot=previous_snapshot,
            diff=diff,
            previous_engine=previous_engine,
            current_engine=engine,
        )
        (
            carried_forward_resource_hierarchy,
            recomputed_resource_hierarchy_resources,
        ) = self._refresh_resource_hierarchy(
            snapshot=snapshot,
            previous_snapshot=previous_snapshot,
            diff=diff,
            current_engine=engine,
        )

        summary = IndexRefreshSummary(
            generated_at=snapshot.generated_at,
            previous_snapshot_at=previous_snapshot.generated_at,
            mode=mode,
            changed_entities=diff.changed_entity_count,
            changed_relationships=diff.changed_relationship_count,
            impacted_principals=len(impacted_principal_ids),
            impacted_resources=len(impacted_resource_ids),
            reused_access_rows=reused_access_rows,
            recomputed_access_rows=recomputed_access_rows,
            total_access_rows=len(access_rows),
            carried_forward_group_closure=carried_forward_group_closure,
            recomputed_group_closure_principals=recomputed_group_closure_principals,
            carried_forward_resource_hierarchy=carried_forward_resource_hierarchy,
            recomputed_resource_hierarchy_resources=recomputed_resource_hierarchy_resources,
            fallback_reasons=[],
        )
        self._save_summary(summary)
        return summary

    def _indexes_exist(self, snapshot_generated_at: str) -> bool:
        return all(
            (
                self._storage.has_materialized_access_index(snapshot_generated_at),
                self._storage.has_principal_group_closure(snapshot_generated_at),
                self._storage.has_resource_hierarchy_closure(snapshot_generated_at),
                self._storage.has_resource_exposure_index(snapshot_generated_at),
                self._storage.has_principal_access_summary(snapshot_generated_at),
            )
        )

    def _previous_snapshot(self, snapshot_generated_at: str) -> Snapshot | None:
        for candidate in self._storage.list_recent_snapshot_generated_at(limit=10):
            if candidate == snapshot_generated_at:
                continue
            snapshot = self._storage.load_snapshot_by_generated_at(candidate)
            if snapshot is not None:
                return snapshot
        return None

    def _full_refresh(
        self,
        *,
        snapshot: Snapshot,
        engine: AccessGraphEngine,
        previous_snapshot_at: str | None,
        reasons: list[str],
        diff: _SnapshotDiff | None = None,
    ) -> IndexRefreshSummary:
        access_rows = engine.materialized_access_index()
        self._storage.save_materialized_access_index(snapshot.generated_at, access_rows)
        self._storage.save_principal_group_closure(
            snapshot.generated_at,
            self._build_group_closure_rows(engine, engine.principal_ids),
            last_verified_at=utc_now_iso(),
        )
        self._storage.save_resource_hierarchy_closure(
            snapshot.generated_at,
            self._build_resource_hierarchy_rows(engine, engine.resource_ids),
        )
        self._storage.save_resource_exposure_index(
            snapshot.generated_at,
            engine.resource_exposure_index_from_rows(access_rows),
        )
        self._storage.save_principal_access_summary(
            snapshot.generated_at,
            engine.principal_access_summary_index_from_rows(access_rows),
        )
        summary = IndexRefreshSummary(
            generated_at=snapshot.generated_at,
            previous_snapshot_at=previous_snapshot_at,
            mode="full",
            changed_entities=0 if diff is None else diff.changed_entity_count,
            changed_relationships=0 if diff is None else diff.changed_relationship_count,
            impacted_principals=len(engine.principal_ids),
            impacted_resources=len(engine.resource_ids),
            reused_access_rows=0,
            recomputed_access_rows=len(access_rows),
            total_access_rows=len(access_rows),
            carried_forward_group_closure=False,
            recomputed_group_closure_principals=len(engine.principal_ids),
            carried_forward_resource_hierarchy=False,
            recomputed_resource_hierarchy_resources=len(engine.resource_ids),
            fallback_reasons=reasons,
        )
        self._save_summary(summary)
        return summary

    def _carry_forward_refresh(
        self,
        *,
        snapshot: Snapshot,
        previous_snapshot: Snapshot,
        previous_rows: list[dict[str, object]],
    ) -> IndexRefreshSummary:
        current_engine = AccessGraphEngine(snapshot)
        entity_ids = {entity.id for entity in snapshot.entities}
        access_rows = [
            row
            for row in previous_rows
            if row["principal_id"] in entity_ids
            and row["resource_id"] in entity_ids
        ]
        self._storage.save_materialized_access_index(snapshot.generated_at, access_rows)
        self._storage.save_resource_exposure_index(
            snapshot.generated_at,
            current_engine.resource_exposure_index_from_rows(access_rows),
        )
        self._storage.save_principal_access_summary(
            snapshot.generated_at,
            current_engine.principal_access_summary_index_from_rows(access_rows),
        )
        previous_group_rows = self._storage.list_all_principal_group_closure(previous_snapshot.generated_at)
        self._storage.save_principal_group_closure(
            snapshot.generated_at,
            (
                [
                    row
                    for row in previous_group_rows
                    if row["principal_id"] in entity_ids and row["group_id"] in entity_ids
                ]
                if previous_group_rows
                else self._build_group_closure_rows(current_engine, current_engine.principal_ids)
            ),
            last_verified_at=utc_now_iso(),
        )
        previous_hierarchy_rows = self._storage.list_all_resource_hierarchy_closure(previous_snapshot.generated_at)
        self._storage.save_resource_hierarchy_closure(
            snapshot.generated_at,
            (
                [
                    row
                    for row in previous_hierarchy_rows
                    if row["resource_id"] in entity_ids and row["ancestor_resource_id"] in entity_ids
                ]
                if previous_hierarchy_rows
                else self._build_resource_hierarchy_rows(current_engine, current_engine.resource_ids)
            ),
        )
        summary = IndexRefreshSummary(
            generated_at=snapshot.generated_at,
            previous_snapshot_at=previous_snapshot.generated_at,
            mode="carry_forward",
            changed_entities=0,
            changed_relationships=0,
            impacted_principals=0,
            impacted_resources=0,
            reused_access_rows=len(access_rows),
            recomputed_access_rows=0,
            total_access_rows=len(access_rows),
            carried_forward_group_closure=True,
            recomputed_group_closure_principals=0,
            carried_forward_resource_hierarchy=True,
            recomputed_resource_hierarchy_resources=0,
            fallback_reasons=[],
        )
        self._save_summary(summary)
        return summary

    def _refresh_group_closure(
        self,
        *,
        snapshot: Snapshot,
        previous_snapshot: Snapshot,
        diff: _SnapshotDiff,
        previous_engine: AccessGraphEngine,
        current_engine: AccessGraphEngine,
    ) -> tuple[bool, int]:
        previous_rows = self._storage.list_all_principal_group_closure(previous_snapshot.generated_at)
        if not previous_rows:
            self._storage.save_principal_group_closure(
                snapshot.generated_at,
                self._build_group_closure_rows(current_engine, current_engine.principal_ids),
                last_verified_at=utc_now_iso(),
            )
            return (False, len(current_engine.principal_ids))

        if not self._group_topology_changed(diff):
            carried_rows = [
                row
                for row in previous_rows
                if row["principal_id"] in current_engine.entities and row["group_id"] in current_engine.entities
            ]
            self._storage.save_principal_group_closure(
                snapshot.generated_at,
                carried_rows,
                last_verified_at=utc_now_iso(),
            )
            return (True, 0)

        impacted_principals = self._delta_group_closure_scope(diff, previous_engine, current_engine)
        if len(impacted_principals) > max(1, len(current_engine.principal_ids)) * 0.7:
            self._storage.save_principal_group_closure(
                snapshot.generated_at,
                self._build_group_closure_rows(current_engine, current_engine.principal_ids),
                last_verified_at=utc_now_iso(),
            )
            return (False, len(current_engine.principal_ids))

        carried_rows = [
            row
            for row in previous_rows
            if row["principal_id"] in current_engine.entities
            and row["group_id"] in current_engine.entities
            and row["principal_id"] not in impacted_principals
        ]
        carried_rows.extend(self._build_group_closure_rows(current_engine, impacted_principals))
        self._storage.save_principal_group_closure(
            snapshot.generated_at,
            carried_rows,
            last_verified_at=utc_now_iso(),
        )
        return (False, len(impacted_principals))

    def _refresh_resource_hierarchy(
        self,
        *,
        snapshot: Snapshot,
        previous_snapshot: Snapshot,
        diff: _SnapshotDiff,
        current_engine: AccessGraphEngine,
    ) -> tuple[bool, int]:
        previous_rows = self._storage.list_all_resource_hierarchy_closure(previous_snapshot.generated_at)
        if not previous_rows:
            self._storage.save_resource_hierarchy_closure(
                snapshot.generated_at,
                self._build_resource_hierarchy_rows(current_engine, current_engine.resource_ids),
            )
            return (False, len(current_engine.resource_ids))

        if not self._resource_hierarchy_changed(diff):
            carried_rows = [
                row
                for row in previous_rows
                if row["resource_id"] in current_engine.entities
                and row["ancestor_resource_id"] in current_engine.entities
            ]
            self._storage.save_resource_hierarchy_closure(snapshot.generated_at, carried_rows)
            return (True, 0)

        self._storage.save_resource_hierarchy_closure(
            snapshot.generated_at,
            self._build_resource_hierarchy_rows(current_engine, current_engine.resource_ids),
        )
        return (False, len(current_engine.resource_ids))

    def _delta_access_scope(
        self,
        *,
        diff: _SnapshotDiff,
        previous_engine: AccessGraphEngine,
        current_engine: AccessGraphEngine,
        previous_rows: list[dict[str, object]],
    ) -> tuple[set[str], set[str]]:
        impacted_principals: set[str] = set()
        impacted_resources: set[str] = set()

        for relationship in diff.added_relationships.values():
            impacted_principals.update(current_engine.impacted_principal_ids_for_relationship(relationship))
            impacted_resources.update(current_engine.impacted_resource_ids_for_relationship(relationship))

        for relationship in diff.removed_relationships.values():
            impacted_principals.update(previous_engine.impacted_principal_ids_for_relationship(relationship))
            impacted_resources.update(previous_engine.impacted_resource_ids_for_relationship(relationship))

        for previous_relationship, current_relationship in diff.changed_relationships.values():
            impacted_principals.update(previous_engine.impacted_principal_ids_for_relationship(previous_relationship))
            impacted_principals.update(current_engine.impacted_principal_ids_for_relationship(current_relationship))
            impacted_resources.update(previous_engine.impacted_resource_ids_for_relationship(previous_relationship))
            impacted_resources.update(current_engine.impacted_resource_ids_for_relationship(current_relationship))

        for entity in diff.added_entities.values():
            self._expand_entity_delta_scope(
                entity=entity,
                engine=current_engine,
                access_rows=previous_rows,
                impacted_principals=impacted_principals,
                impacted_resources=impacted_resources,
            )

        for entity in diff.removed_entities.values():
            self._expand_entity_delta_scope(
                entity=entity,
                engine=previous_engine,
                access_rows=previous_rows,
                impacted_principals=impacted_principals,
                impacted_resources=impacted_resources,
            )

        for previous_entity, current_entity in diff.changed_entities.values():
            self._expand_entity_delta_scope(
                entity=previous_entity,
                engine=previous_engine,
                access_rows=previous_rows,
                impacted_principals=impacted_principals,
                impacted_resources=impacted_resources,
            )
            self._expand_entity_delta_scope(
                entity=current_entity,
                engine=current_engine,
                access_rows=previous_rows,
                impacted_principals=impacted_principals,
                impacted_resources=impacted_resources,
            )

        return impacted_principals, impacted_resources

    def _expand_entity_delta_scope(
        self,
        *,
        entity: Entity,
        engine: AccessGraphEngine,
        access_rows: list[dict[str, object]],
        impacted_principals: set[str],
        impacted_resources: set[str],
    ) -> None:
        if entity.kind in {"user", "service_account", "group", "role"}:
            impacted_principals.update(engine.impacted_principal_ids_for_actor(entity.id))
            impacted_resources.update(engine.impacted_resource_ids_for_actor(entity.id))
            return
        if entity.kind == "resource":
            affected_resources = set(engine.affected_resource_ids_for_resource(entity.id))
            impacted_resources.update(affected_resources)
            impacted_principals.update(
                str(row["principal_id"])
                for row in access_rows
                if str(row["resource_id"]) in affected_resources
            )

    def _delta_group_closure_scope(
        self,
        diff: _SnapshotDiff,
        previous_engine: AccessGraphEngine,
        current_engine: AccessGraphEngine,
    ) -> set[str]:
        impacted: set[str] = set()
        for relationship in diff.added_relationships.values():
            if relationship.kind in GROUP_CLOSURE_RELATIONSHIP_KINDS:
                impacted.update(current_engine.impacted_principal_ids_for_relationship(relationship))
        for relationship in diff.removed_relationships.values():
            if relationship.kind in GROUP_CLOSURE_RELATIONSHIP_KINDS:
                impacted.update(previous_engine.impacted_principal_ids_for_relationship(relationship))
        for previous_relationship, current_relationship in diff.changed_relationships.values():
            if previous_relationship.kind in GROUP_CLOSURE_RELATIONSHIP_KINDS:
                impacted.update(previous_engine.impacted_principal_ids_for_relationship(previous_relationship))
            if current_relationship.kind in GROUP_CLOSURE_RELATIONSHIP_KINDS:
                impacted.update(current_engine.impacted_principal_ids_for_relationship(current_relationship))
        impacted.intersection_update(current_engine.principal_ids)
        return impacted

    def _build_group_closure_rows(
        self,
        engine: AccessGraphEngine,
        principal_ids,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for principal_id in sorted(set(principal_ids)):
            if principal_id not in engine.entities:
                continue
            for record in engine.principal_group_closure(principal_id):
                rows.append(
                    {
                        "principal_id": principal_id,
                        "group_id": record.group.id,
                        "depth": record.depth,
                        "shortest_parent_id": record.shortest_parent.id,
                        "path_count": record.path_count,
                    }
                )
        return rows

    def _build_resource_hierarchy_rows(
        self,
        engine: AccessGraphEngine,
        resource_ids,
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for resource_id in sorted(set(resource_ids)):
            if resource_id not in engine.entities:
                continue
            for record in engine.resource_hierarchy_closure(resource_id):
                rows.append(
                    {
                        "resource_id": resource_id,
                        "ancestor_resource_id": record.ancestor.id,
                        "depth": record.depth,
                        "inherits_acl": record.inherits_acl,
                    }
                )
        return rows

    def _full_rebuild_reasons(self, diff: _SnapshotDiff) -> list[str]:
        reasons: list[str] = []
        unsupported_relationship_kinds = sorted(
            kind for kind in diff.relationship_kinds() if kind in FULL_REBUILD_RELATIONSHIP_KINDS
        )
        if unsupported_relationship_kinds:
            reasons.append(
                "Detected changes in "
                + ", ".join(unsupported_relationship_kinds)
                + ", which still require a full entitlement rebuild."
            )
        for previous_entity, current_entity in diff.changed_entities.values():
            if previous_entity.kind != current_entity.kind:
                reasons.append(
                    f"Entity {previous_entity.id} changed type from {previous_entity.kind} to {current_entity.kind}."
                )
        return reasons

    def _group_topology_changed(self, diff: _SnapshotDiff) -> bool:
        if any(
            relationship.kind in GROUP_CLOSURE_RELATIONSHIP_KINDS
            for relationship in diff.added_relationships.values()
        ):
            return True
        if any(
            relationship.kind in GROUP_CLOSURE_RELATIONSHIP_KINDS
            for relationship in diff.removed_relationships.values()
        ):
            return True
        if any(
            previous.kind in GROUP_CLOSURE_RELATIONSHIP_KINDS
            or current.kind in GROUP_CLOSURE_RELATIONSHIP_KINDS
            for previous, current in diff.changed_relationships.values()
        ):
            return True
        return False

    def _resource_hierarchy_changed(self, diff: _SnapshotDiff) -> bool:
        if any(entity.kind == "resource" for entity in diff.added_entities.values()):
            return True
        if any(entity.kind == "resource" for entity in diff.removed_entities.values()):
            return True
        if any(
            relationship.kind == "contains"
            for relationship in diff.added_relationships.values()
        ):
            return True
        if any(
            relationship.kind == "contains"
            for relationship in diff.removed_relationships.values()
        ):
            return True
        if any(
            previous.kind == "contains" or current.kind == "contains"
            for previous, current in diff.changed_relationships.values()
        ):
            return True
        return False

    def _diff_snapshots(self, previous_snapshot: Snapshot, current_snapshot: Snapshot) -> _SnapshotDiff:
        previous_entities = {entity.id: entity for entity in previous_snapshot.entities}
        current_entities = {entity.id: entity for entity in current_snapshot.entities}
        previous_relationships = {
            relationship.id: relationship for relationship in previous_snapshot.relationships
        }
        current_relationships = {
            relationship.id: relationship for relationship in current_snapshot.relationships
        }

        added_entities = {
            entity_id: entity
            for entity_id, entity in current_entities.items()
            if entity_id not in previous_entities
        }
        removed_entities = {
            entity_id: entity
            for entity_id, entity in previous_entities.items()
            if entity_id not in current_entities
        }
        changed_entities = {
            entity_id: (previous_entities[entity_id], current_entities[entity_id])
            for entity_id in previous_entities.keys() & current_entities.keys()
            if self._entity_signature(previous_entities[entity_id])
            != self._entity_signature(current_entities[entity_id])
        }

        added_relationships = {
            relationship_id: relationship
            for relationship_id, relationship in current_relationships.items()
            if relationship_id not in previous_relationships
        }
        removed_relationships = {
            relationship_id: relationship
            for relationship_id, relationship in previous_relationships.items()
            if relationship_id not in current_relationships
        }
        changed_relationships = {
            relationship_id: (
                previous_relationships[relationship_id],
                current_relationships[relationship_id],
            )
            for relationship_id in previous_relationships.keys() & current_relationships.keys()
            if self._relationship_signature(previous_relationships[relationship_id])
            != self._relationship_signature(current_relationships[relationship_id])
        }

        return _SnapshotDiff(
            added_entities=added_entities,
            removed_entities=removed_entities,
            changed_entities=changed_entities,
            added_relationships=added_relationships,
            removed_relationships=removed_relationships,
            changed_relationships=changed_relationships,
        )

    def _entity_signature(self, entity: Entity) -> dict[str, object]:
        payload = entity.model_dump()
        payload["tags"] = sorted(str(tag) for tag in entity.tags)
        return payload

    def _relationship_signature(self, relationship: Relationship) -> dict[str, object]:
        payload = relationship.model_dump()
        payload["permissions"] = sorted(str(permission) for permission in relationship.permissions)
        payload["metadata"] = {
            key: relationship.metadata[key]
            for key in sorted(relationship.metadata)
        }
        return payload

    def _save_summary(self, summary: IndexRefreshSummary) -> None:
        self._storage.set_setting(self._SUMMARY_KEY, summary.model_dump_json())
