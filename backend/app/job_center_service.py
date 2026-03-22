from __future__ import annotations

from datetime import UTC, datetime

from app.auth import utc_now_iso
from app.models import JobCenterResponse, JobRecentActivity, JobWorkerLane


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class JobCenterService:
    def __init__(self, storage, runtime_getter) -> None:
        self._storage = storage
        self._runtime_getter = runtime_getter

    def status(self) -> JobCenterResponse:
        runtime = self._runtime_getter()
        now = datetime.now(tz=UTC)
        background_worker = runtime.background_worker_status()
        targets = self._storage.list_targets()
        active_targets = [target for target in targets if target.enabled]
        scan_runs = self._storage.list_scan_runs(limit=12)
        latest_scan = scan_runs[0] if scan_runs else None
        report_summaries = self._storage.list_report_schedules()
        enabled_summaries = [summary for summary in report_summaries if summary.enabled]
        due_summaries = [
            summary
            for summary in enabled_summaries
            if summary.next_run_at and _parse_iso(summary.next_run_at) and _parse_iso(summary.next_run_at) <= now
        ]

        scan_scheduler_enabled = (
            runtime._scheduler_enabled
            if background_worker["state"] == "local"
            else bool(background_worker["scan_scheduler_enabled"])
        )
        if runtime._scan_in_progress and background_worker["state"] == "local":
            scan_lane_state = "running"
        elif active_targets and background_worker["state"] == "missing":
            scan_lane_state = "attention"
        elif active_targets and background_worker["state"] in {"local", "remote", "standby"} and scan_scheduler_enabled:
            scan_lane_state = "scheduled"
        elif active_targets:
            scan_lane_state = "idle"
        else:
            scan_lane_state = "disabled"

        scan_lane = JobWorkerLane(
            id="scan-runner",
            name="Collection worker",
            kind="scan",
            state=scan_lane_state,
            scheduler_enabled=scan_scheduler_enabled,
            execution_mode=str(background_worker["state"]),
            worker_host=None if background_worker["host"] is None else str(background_worker["host"]),
            worker_role=(
                None
                if background_worker["runtime_role"] is None
                else str(background_worker["runtime_role"])
            ),
            worker_last_seen_at=(
                None
                if background_worker["updated_at"] is None
                else str(background_worker["updated_at"])
            ),
            queue_depth=1 if runtime._scan_in_progress else 0,
            active_work_items=len(active_targets),
            last_completed_at=latest_scan.finished_at if latest_scan else None,
            next_due_at=None,
            last_status=latest_scan.status if latest_scan else None,
            summary=(
                "A collection cycle is currently running."
                if runtime._scan_in_progress and background_worker["state"] == "local"
                else f"{len(active_targets)} target(s) are scheduled on the active background worker."
                if active_targets and background_worker["state"] in {"local", "remote"} and scan_scheduler_enabled
                else "Another node currently owns background collection for this deployment."
                if active_targets and background_worker["state"] == "standby"
                else "No active background worker heartbeat is visible for collection jobs."
                if active_targets and background_worker["state"] == "missing"
                else f"{len(active_targets)} target(s) are ready for manual collection."
                if active_targets
                else "No active collection target is currently enabled."
            ),
        )

        report_recent_runs: list[tuple[datetime, JobRecentActivity]] = []
        latest_report_finished_at: str | None = None
        latest_report_status: str | None = None
        for summary in enabled_summaries[:20]:
            detail = self._storage.get_report_schedule(summary.id)
            if detail is None:
                continue
            if detail.summary.last_run_at and (
                latest_report_finished_at is None
                or _parse_iso(detail.summary.last_run_at) > _parse_iso(latest_report_finished_at)
            ):
                latest_report_finished_at = detail.summary.last_run_at
                latest_report_status = detail.summary.last_status
            for run in detail.recent_runs[:4]:
                started = _parse_iso(run.started_at)
                if started is None:
                    continue
                report_recent_runs.append(
                    (
                        started,
                        JobRecentActivity(
                            id=run.id,
                            lane_id="report-delivery",
                            label=detail.summary.name,
                            status=run.status,
                            started_at=run.started_at,
                            finished_at=run.finished_at,
                            summary=run.message or "Report schedule execution completed.",
                        ),
                    )
                )

        report_scheduler_enabled = (
            runtime._report_scheduler_enabled
            if background_worker["state"] == "local"
            else bool(background_worker["report_scheduler_enabled"])
        )
        if any(summary.last_status == "failed" for summary in enabled_summaries):
            report_lane_state = "attention"
        elif enabled_summaries and background_worker["state"] == "missing":
            report_lane_state = "attention"
        elif runtime._report_scheduler_enabled and enabled_summaries and background_worker["state"] == "local":
            report_lane_state = "scheduled"
        elif enabled_summaries and background_worker["state"] in {"remote", "standby"} and report_scheduler_enabled:
            report_lane_state = "scheduled"
        elif enabled_summaries:
            report_lane_state = "idle"
        else:
            report_lane_state = "disabled"

        report_lane = JobWorkerLane(
            id="report-delivery",
            name="Report delivery worker",
            kind="report_delivery",
            state=report_lane_state,
            scheduler_enabled=report_scheduler_enabled,
            execution_mode=str(background_worker["state"]),
            worker_host=None if background_worker["host"] is None else str(background_worker["host"]),
            worker_role=(
                None
                if background_worker["runtime_role"] is None
                else str(background_worker["runtime_role"])
            ),
            worker_last_seen_at=(
                None
                if background_worker["updated_at"] is None
                else str(background_worker["updated_at"])
            ),
            queue_depth=len(due_summaries),
            active_work_items=len(enabled_summaries),
            last_completed_at=latest_report_finished_at,
            next_due_at=min(
                (summary.next_run_at for summary in enabled_summaries if summary.next_run_at),
                default=None,
            ),
            last_status=latest_report_status,
            summary=(
                f"{len(due_summaries)} scheduled report(s) are currently due."
                if due_summaries
                else f"{len(enabled_summaries)} report schedule(s) are owned by the active background worker."
                if enabled_summaries and background_worker["state"] in {"local", "remote"} and report_scheduler_enabled
                else "Another node currently owns scheduled report delivery."
                if enabled_summaries and background_worker["state"] == "standby"
                else "No active background worker heartbeat is visible for scheduled report delivery."
                if enabled_summaries and background_worker["state"] == "missing"
                else f"{len(enabled_summaries)} report schedule(s) are enabled."
                if enabled_summaries
                else "No report schedule is currently enabled."
            ),
        )

        recent_jobs: list[tuple[datetime, JobRecentActivity]] = []
        for run in scan_runs:
            started = _parse_iso(run.started_at)
            if started is None:
                continue
            recent_jobs.append(
                (
                    started,
                    JobRecentActivity(
                        id=run.id,
                        lane_id="scan-runner",
                        label="Live collection run",
                        status=run.status,
                        started_at=run.started_at,
                        finished_at=run.finished_at,
                        summary=(
                            f"Processed {run.resource_count} resources, {run.principal_count} principals and {run.relationship_count} relationships."
                        ),
                    ),
                )
            )
        recent_jobs.extend(report_recent_runs)
        recent_jobs.sort(key=lambda item: item[0], reverse=True)

        overall_status = "healthy"
        if report_lane.state == "attention" or (latest_scan and latest_scan.status == "failed"):
            overall_status = "attention"
        elif scan_lane.state == "running" or report_lane.queue_depth > 0:
            overall_status = "watch"

        return JobCenterResponse(
            generated_at=utc_now_iso(),
            overall_status=overall_status,
            lanes=[scan_lane, report_lane],
            recent_jobs=[item for _, item in recent_jobs[:12]],
        )
