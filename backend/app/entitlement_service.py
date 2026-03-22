from __future__ import annotations

from collections.abc import Callable

from app.models import CatalogResponse, OverviewResponse, PrincipalAccessResponse, PrincipalResourceRecord, ResourceAccessRecord, ResourceAccessResponse
from app.storage import AppStorage


class EntitlementService:
    def __init__(
        self,
        engine_getter: Callable[[], object],
        storage: AppStorage,
        platform_services,
    ) -> None:
        self._engine_getter = engine_getter
        self._storage = storage
        self._platform_services = platform_services

    def overview(self) -> OverviewResponse:
        engine = self._engine_getter()
        cache_key = f"overview:{engine.snapshot.generated_at}"
        cached = self._platform_services.cache.get_json(cache_key)
        if cached is not None:
            return OverviewResponse.model_validate(cached)
        response = engine.get_overview()
        self._platform_services.cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=300,
        )
        return response

    def catalog(self) -> CatalogResponse:
        engine = self._engine_getter()
        cache_key = f"catalog:{engine.snapshot.generated_at}"
        cached = self._platform_services.cache.get_json(cache_key)
        if cached is not None:
            return CatalogResponse.model_validate(cached)
        response = engine.get_catalog()
        self._platform_services.cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=600,
        )
        return response

    @staticmethod
    def _resolved_window(limit: int | None, offset: int) -> tuple[int, int]:
        resolved_limit = max(1, min(int(limit or 50), 500))
        resolved_offset = max(0, int(offset))
        return resolved_limit, resolved_offset

    @staticmethod
    def _slice_window(records: list, *, limit: int, offset: int) -> tuple[list, bool]:
        window = records[offset : offset + limit]
        has_more = offset + len(window) < len(records)
        return window, has_more

    def resource_exposure(
        self,
        resource_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> ResourceAccessResponse:
        engine = self._engine_getter()
        resolved_limit, resolved_offset = self._resolved_window(limit, offset)
        cache_key = (
            f"resource-access:{engine.snapshot.generated_at}:{resource_id}:"
            f"{resolved_limit}:{resolved_offset}"
        )
        cached = self._platform_services.cache.get_json(cache_key)
        if cached is not None:
            return ResourceAccessResponse.model_validate(cached)

        rows = self._storage.list_materialized_access_by_resource(
            engine.snapshot.generated_at,
            resource_id,
            limit=resolved_limit,
            offset=resolved_offset,
        )
        if rows:
            records = [
                ResourceAccessRecord(
                    principal=engine._summary(str(row["principal_id"])),
                    permissions=list(row["permissions"]),
                    path_count=int(row["path_count"]),
                    path_complexity=int(row.get("path_complexity", 0)),
                    access_mode=str(row["access_mode"]),
                    risk_score=int(row["risk_score"]),
                    why=str(row["why"]),
                )
                for row in rows
            ]
            summary = self._storage.get_resource_exposure_summary(
                engine.snapshot.generated_at,
                resource_id,
            )
            total_principals = (
                int(summary["principal_count"])
                if summary is not None
                else self._storage.count_materialized_access_by_resource(
                    engine.snapshot.generated_at,
                    resource_id,
                )
            )
            privileged_principal_count = (
                int(summary["privileged_principal_count"])
                if summary is not None
                else sum(
                    1 for record in records if engine._is_privileged_permission_set(record.permissions)
                )
            )
            has_more = resolved_offset + len(records) < total_principals
            response = ResourceAccessResponse(
                resource=engine._summary(resource_id),
                total_principals=total_principals,
                privileged_principal_count=privileged_principal_count,
                offset=resolved_offset,
                limit=resolved_limit,
                returned_count=len(records),
                has_more=has_more,
                records=records,
            )
        else:
            full_cache_key = f"resource-access-full:{engine.snapshot.generated_at}:{resource_id}"
            cached_full = self._platform_services.cache.get_json(full_cache_key)
            if cached_full is not None:
                full_response = ResourceAccessResponse.model_validate(cached_full)
            else:
                full_response = engine.get_resource_access(resource_id)
                self._platform_services.cache.set_json(
                    full_cache_key,
                    full_response.model_dump(mode="json"),
                    ttl_seconds=600,
                )
            records, has_more = self._slice_window(
                full_response.records,
                limit=resolved_limit,
                offset=resolved_offset,
            )
            response = full_response.model_copy(
                update={
                    "offset": resolved_offset,
                    "limit": resolved_limit,
                    "returned_count": len(records),
                    "has_more": has_more,
                    "records": records,
                }
            )

        self._platform_services.cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=600,
        )
        return response

    def principal_access(
        self,
        principal_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> PrincipalAccessResponse:
        engine = self._engine_getter()
        resolved_limit, resolved_offset = self._resolved_window(limit, offset)
        cache_key = (
            f"principal-access:{engine.snapshot.generated_at}:{principal_id}:"
            f"{resolved_limit}:{resolved_offset}"
        )
        cached = self._platform_services.cache.get_json(cache_key)
        if cached is not None:
            return PrincipalAccessResponse.model_validate(cached)

        rows = self._storage.list_materialized_access_by_principal(
            engine.snapshot.generated_at,
            principal_id,
            limit=resolved_limit,
            offset=resolved_offset,
        )
        if rows:
            records = [
                PrincipalResourceRecord(
                    resource=engine._summary(str(row["resource_id"])),
                    permissions=list(row["permissions"]),
                    path_count=int(row["path_count"]),
                    path_complexity=int(row.get("path_complexity", 0)),
                    access_mode=str(row["access_mode"]),
                    risk_score=int(row["risk_score"]),
                    why=str(row["why"]),
                )
                for row in rows
            ]
            summary = self._storage.get_principal_access_summary(
                engine.snapshot.generated_at,
                principal_id,
            )
            total_resources = (
                int(summary["resource_count"])
                if summary is not None
                else self._storage.count_materialized_access_by_principal(
                    engine.snapshot.generated_at,
                    principal_id,
                )
            )
            privileged_resources = (
                int(summary["privileged_resource_count"])
                if summary is not None
                else sum(
                    1 for record in records if engine._is_privileged_permission_set(record.permissions)
                )
            )
            has_more = resolved_offset + len(records) < total_resources
            response = PrincipalAccessResponse(
                principal=engine._summary(principal_id),
                total_resources=total_resources,
                privileged_resources=privileged_resources,
                offset=resolved_offset,
                limit=resolved_limit,
                returned_count=len(records),
                has_more=has_more,
                records=records,
            )
        else:
            full_cache_key = f"principal-access-full:{engine.snapshot.generated_at}:{principal_id}"
            cached_full = self._platform_services.cache.get_json(full_cache_key)
            if cached_full is not None:
                full_response = PrincipalAccessResponse.model_validate(cached_full)
            else:
                full_response = engine.get_principal_access(principal_id)
                self._platform_services.cache.set_json(
                    full_cache_key,
                    full_response.model_dump(mode="json"),
                    ttl_seconds=600,
                )
            records, has_more = self._slice_window(
                full_response.records,
                limit=resolved_limit,
                offset=resolved_offset,
            )
            response = full_response.model_copy(
                update={
                    "offset": resolved_offset,
                    "limit": resolved_limit,
                    "returned_count": len(records),
                    "has_more": has_more,
                    "records": records,
                }
            )

        self._platform_services.cache.set_json(
            cache_key,
            response.model_dump(mode="json"),
            ttl_seconds=600,
        )
        return response
