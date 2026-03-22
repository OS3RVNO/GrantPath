from __future__ import annotations

import calendar
import mimetypes
import os
import smtplib
import threading
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

import httpx

from app.auth import utc_now, utc_now_iso
from app.branding import PRODUCT_REPORT_SUBJECT_PREFIX
from app.engine import AccessGraphEngine
from app.models import (
    AccessReviewCampaignDetailResponse,
    ReportDeliverySettings,
    ReportScheduleCreateRequest,
    ReportScheduleDetailResponse,
    ReportScheduleRunRecord,
    ReportScheduleRunStatus,
    ReportScheduleSummary,
    ReportScheduleUpdateRequest,
)
from app.reporting import (
    build_report_context,
    render_excel_report,
    render_html_report,
    render_pdf_report,
    render_review_campaign_excel_report,
    render_review_campaign_html_report,
    render_review_campaign_pdf_report,
)
from app.storage import AppStorage


def _slugify(value: str) -> str:
    safe = "".join(character.lower() if character.isalnum() else "-" for character in value)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-")[:120] or "scheduled-report"


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _default_subject(schedule_name: str) -> str:
    return f"{PRODUCT_REPORT_SUBJECT_PREFIX}: {schedule_name}"


def compute_next_run_at(
    summary: ReportScheduleSummary,
    *,
    reference: datetime | None = None,
) -> str | None:
    if not summary.enabled:
        return None

    now_utc = reference or utc_now()
    zone = ZoneInfo(summary.timezone)
    local_now = now_utc.astimezone(zone)

    if summary.cadence == "hourly":
        candidate = local_now.replace(minute=summary.minute, second=0, microsecond=0)
        if candidate <= local_now:
            candidate += timedelta(hours=1)
        return _iso_utc(candidate)

    candidate = local_now.replace(
        hour=summary.hour,
        minute=summary.minute,
        second=0,
        microsecond=0,
    )

    if summary.cadence == "daily":
        if candidate <= local_now:
            candidate += timedelta(days=1)
        return _iso_utc(candidate)

    if summary.cadence == "weekly":
        day_of_week = summary.day_of_week if summary.day_of_week is not None else 0
        delta_days = (day_of_week - local_now.weekday()) % 7
        candidate = candidate + timedelta(days=delta_days)
        if candidate <= local_now:
            candidate += timedelta(days=7)
        return _iso_utc(candidate)

    day_of_month = summary.day_of_month if summary.day_of_month is not None else 1
    year = local_now.year
    month = local_now.month
    max_day = calendar.monthrange(year, month)[1]
    candidate = candidate.replace(day=min(day_of_month, max_day))
    if candidate <= local_now:
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        max_day = calendar.monthrange(year, month)[1]
        candidate = candidate.replace(year=year, month=month, day=min(day_of_month, max_day))
    return _iso_utc(candidate)


def _validate_delivery_settings(delivery: ReportDeliverySettings) -> None:
    enabled_channels = [
        delivery.email.enabled,
        delivery.webhook.enabled,
        delivery.archive.enabled,
    ]
    if not any(enabled_channels):
        raise ValueError("At least one delivery channel must be enabled.")
    if delivery.email.enabled:
        if not delivery.email.smtp_host:
            raise ValueError("Email delivery requires an SMTP host.")
        if not delivery.email.from_address:
            raise ValueError("Email delivery requires a from address.")
        if not delivery.email.to:
            raise ValueError("Email delivery requires at least one recipient.")
    if delivery.webhook.enabled and not delivery.webhook.url:
        raise ValueError("Webhook delivery requires a destination URL.")


class ReportScheduleService:
    def __init__(
        self,
        storage: AppStorage,
        data_dir: Path,
        engine_provider: Callable[[], AccessGraphEngine],
        review_provider: Callable[[str], AccessReviewCampaignDetailResponse | None],
    ) -> None:
        self.storage = storage
        self.data_dir = data_dir
        self.engine_provider = engine_provider
        self.review_provider = review_provider
        self._run_lock_guard = threading.Lock()
        self._run_locks: dict[str, threading.Lock] = {}

    def list_schedules(self):
        return self.storage.list_report_schedules()

    def get_schedule(self, schedule_id: str):
        return self.storage.get_report_schedule(schedule_id)

    def create_schedule(
        self,
        payload: ReportScheduleCreateRequest,
        *,
        actor_username: str,
    ) -> ReportScheduleDetailResponse:
        _validate_delivery_settings(payload.delivery)
        summary = ReportScheduleSummary(
            id="draft",
            name=payload.name,
            description=payload.description,
            enabled=payload.enabled,
            cadence=payload.cadence,
            timezone=payload.timezone,
            hour=payload.hour,
            minute=payload.minute,
            day_of_week=payload.day_of_week,
            day_of_month=payload.day_of_month,
            report_kind=payload.config.kind,
            locale=payload.config.locale,
            formats=payload.config.formats,
            channels=[],
            created_by=actor_username,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        next_run_at = compute_next_run_at(summary)
        return self.storage.create_report_schedule(
            payload,
            created_by=actor_username,
            timestamp=utc_now_iso(),
            next_run_at=next_run_at,
        )

    def update_schedule(
        self,
        schedule_id: str,
        payload: ReportScheduleUpdateRequest,
    ) -> ReportScheduleDetailResponse | None:
        current = self.storage.get_report_schedule(schedule_id)
        if current is None:
            return None
        next_config = current.config if payload.config is None else payload.config
        next_delivery = current.delivery if payload.delivery is None else payload.delivery
        _validate_delivery_settings(next_delivery)
        next_summary = current.summary.model_copy(
            update={
                "name": current.summary.name if payload.name is None else payload.name,
                "description": current.summary.description if payload.description is None else payload.description,
                "enabled": current.summary.enabled if payload.enabled is None else payload.enabled,
                "cadence": current.summary.cadence if payload.cadence is None else payload.cadence,
                "timezone": current.summary.timezone if payload.timezone is None else payload.timezone,
                "hour": current.summary.hour if payload.hour is None else payload.hour,
                "minute": current.summary.minute if payload.minute is None else payload.minute,
                "day_of_week": current.summary.day_of_week if payload.day_of_week is None else payload.day_of_week,
                "day_of_month": current.summary.day_of_month if payload.day_of_month is None else payload.day_of_month,
                "report_kind": next_config.kind,
                "locale": next_config.locale,
                "formats": next_config.formats,
            }
        )
        next_run_at = compute_next_run_at(next_summary)
        return self.storage.update_report_schedule(
            schedule_id,
            payload,
            timestamp=utc_now_iso(),
            next_run_at=next_run_at,
        )

    def delete_schedule(self, schedule_id: str) -> bool:
        return self.storage.delete_report_schedule(schedule_id)

    def run_due_schedules(self) -> list[tuple[ReportScheduleDetailResponse, ReportScheduleRunRecord]]:
        now = utc_now()
        due: list[ReportScheduleSummary] = []
        for schedule in self.storage.list_report_schedules():
            if not schedule.enabled or not schedule.next_run_at:
                continue
            if _parse_iso(schedule.next_run_at) <= now:
                due.append(schedule)
        results: list[tuple[ReportScheduleDetailResponse, ReportScheduleRunRecord]] = []
        for schedule in due:
            detail, run = self.run_schedule(schedule.id, trigger="scheduled")
            results.append((detail, run))
        return results

    def run_schedule(
        self,
        schedule_id: str,
        *,
        trigger: str = "manual",
    ) -> tuple[ReportScheduleDetailResponse, ReportScheduleRunRecord]:
        with self._lock_for_schedule(schedule_id):
            detail = self.storage.get_report_schedule(schedule_id)
            if detail is None:
                raise ValueError("Report schedule not found.")
            run = self._execute(detail, trigger=trigger)
            updated = self.storage.get_report_schedule(schedule_id)
            if updated is None:
                raise ValueError("Report schedule disappeared during execution.")
            return updated, run

    def _execute(
        self,
        schedule: ReportScheduleDetailResponse,
        *,
        trigger: str,
    ) -> ReportScheduleRunRecord:
        started_at = utc_now_iso()
        artifact_paths: list[str] = []
        delivered_channels: list[str] = []
        failures: list[str] = []
        generated_at = utc_now_iso()
        run_id = f"report_run_{os.urandom(6).hex()}"

        try:
            html_content, attachments = self._build_report(schedule)
            if schedule.delivery.archive.enabled:
                base_directory = self._artifact_directory(schedule, run_id)
                base_directory.mkdir(parents=True, exist_ok=True)
                for filename, content_type, payload in attachments:
                    output_path = base_directory / filename
                    output_path.write_bytes(payload)
                    artifact_paths.append(str(output_path))
                delivered_channels.append("archive")
            if schedule.delivery.email.enabled:
                try:
                    self._send_email(schedule, html_content, attachments, generated_at)
                    delivered_channels.append("email")
                except Exception as exc:  # pragma: no cover - network / SMTP dependent
                    failures.append(f"email: {exc}")
            if schedule.delivery.webhook.enabled:
                try:
                    self._send_webhook(schedule, generated_at, artifact_paths)
                    delivered_channels.append("webhook")
                except Exception as exc:  # pragma: no cover - network dependent
                    failures.append(f"webhook: {exc}")

            if failures and delivered_channels:
                status: ReportScheduleRunStatus = "partial"
            elif failures:
                status = "failed"
            else:
                status = "success"
            message = (
                " | ".join(failures)
                if failures
                else f"Delivered via {', '.join(delivered_channels) or 'archive'}."
            )
        except Exception as exc:
            status = "failed"
            message = str(exc)

        finished_at = utc_now_iso()
        run = ReportScheduleRunRecord(
            id=run_id,
            schedule_id=schedule.summary.id,
            started_at=started_at,
            finished_at=finished_at,
            trigger=trigger,
            status=status,
            delivered_channels=delivered_channels,
            artifact_paths=artifact_paths,
            message=message,
        )
        next_run_at = compute_next_run_at(
            schedule.summary,
            reference=_parse_iso(finished_at),
        )
        self.storage.record_report_schedule_run(
            schedule.summary.id,
            run,
            next_run_at=next_run_at,
            last_run_at=finished_at,
            last_status=status,
            last_message=message,
        )
        return run

    def _build_report(
        self,
        schedule: ReportScheduleDetailResponse,
    ) -> tuple[str | None, list[tuple[str, str, bytes]]]:
        locale = schedule.config.locale
        base_name = _slugify(schedule.config.title_override or schedule.summary.name)
        html_content: str | None = None
        attachments: list[tuple[str, str, bytes]] = []

        if schedule.config.kind == "access_review":
            context = build_report_context(
                self.engine_provider(),
                schedule.config.principal_id or "",
                schedule.config.resource_id or "",
                schedule.config.scenario_edge_id or "",
                focus_resource_id=schedule.config.focus_resource_id,
            )
            if "html" in schedule.config.formats or schedule.delivery.email.include_html_body:
                html_content = render_html_report(context, locale=locale)
            if "html" in schedule.config.formats and html_content is not None:
                attachments.append((f"{base_name}.html", "text/html; charset=utf-8", html_content.encode("utf-8")))
            if "pdf" in schedule.config.formats:
                attachments.append((f"{base_name}.pdf", "application/pdf", render_pdf_report(context, locale=locale)))
            if "xlsx" in schedule.config.formats:
                attachments.append(
                    (
                        f"{base_name}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        render_excel_report(context, locale=locale),
                    )
                )
            return html_content, attachments

        campaign = self.review_provider(schedule.config.campaign_id or "")
        if campaign is None:
            raise ValueError("The selected review campaign is no longer available.")
        if "html" in schedule.config.formats or schedule.delivery.email.include_html_body:
            html_content = render_review_campaign_html_report(campaign, locale=locale)
        if "html" in schedule.config.formats and html_content is not None:
            attachments.append((f"{base_name}.html", "text/html; charset=utf-8", html_content.encode("utf-8")))
        if "pdf" in schedule.config.formats:
            attachments.append(
                (
                    f"{base_name}.pdf",
                    "application/pdf",
                    render_review_campaign_pdf_report(campaign, locale=locale),
                )
            )
        if "xlsx" in schedule.config.formats:
            attachments.append(
                (
                    f"{base_name}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    render_review_campaign_excel_report(campaign, locale=locale),
                )
            )
        return html_content, attachments

    def _artifact_directory(self, schedule: ReportScheduleDetailResponse, run_id: str) -> Path:
        configured = schedule.delivery.archive.directory
        if configured:
            base_dir = Path(configured)
        else:
            base_dir = self.data_dir / "report-runs"
        prefix = schedule.delivery.archive.filename_prefix or _slugify(schedule.summary.name)
        return base_dir / schedule.summary.id / f"{prefix}-{run_id}"

    def _send_email(
        self,
        schedule: ReportScheduleDetailResponse,
        html_content: str | None,
        attachments: list[tuple[str, str, bytes]],
        generated_at: str,
    ) -> None:
        settings = schedule.delivery.email
        if not settings.smtp_host or not settings.from_address:
            raise ValueError("SMTP host and from address are required for email delivery.")
        recipients = [*settings.to, *settings.cc, *settings.bcc]
        if not recipients:
            raise ValueError("At least one email recipient is required.")

        message = EmailMessage()
        message["Subject"] = (settings.subject_template or _default_subject(schedule.summary.name)).format(
            schedule_name=schedule.summary.name,
            generated_at=generated_at,
            report_kind=schedule.summary.report_kind,
            tenant=self.engine_provider().snapshot.tenant,
        )
        message["From"] = settings.from_address
        message["To"] = ", ".join(settings.to)
        if settings.cc:
            message["Cc"] = ", ".join(settings.cc)
        if settings.reply_to:
            message["Reply-To"] = settings.reply_to
        message.set_content(settings.message_body)
        if settings.include_html_body and html_content:
            message.add_alternative(html_content, subtype="html")

        selected_formats = settings.attach_formats or schedule.config.formats
        for filename, content_type, payload in attachments:
            extension = filename.rsplit(".", 1)[-1]
            if extension not in selected_formats:
                continue
            maintype, subtype = content_type.split("/", 1)
            subtype = subtype.split(";", 1)[0]
            message.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)

        password = ""
        if settings.password_env:
            password = os.getenv(settings.password_env, "")
        if settings.security == "ssl":
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        with server:
            if settings.security == "starttls":
                server.starttls()
            if settings.username:
                server.login(settings.username, password)
            server.send_message(message, to_addrs=recipients)

    def _send_webhook(
        self,
        schedule: ReportScheduleDetailResponse,
        generated_at: str,
        artifact_paths: list[str],
    ) -> None:
        settings = schedule.delivery.webhook
        if not settings.url:
            raise ValueError("Webhook delivery requires a destination URL.")
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.secret_env:
            secret = os.getenv(settings.secret_env, "")
            if secret:
                headers[settings.secret_header] = secret
        payload = {
            "schedule": {
                "id": schedule.summary.id,
                "name": schedule.summary.name,
                "report_kind": schedule.summary.report_kind,
                "locale": schedule.summary.locale,
            },
            "generated_at": generated_at,
            "artifacts": artifact_paths,
        }
        with httpx.Client(timeout=20) as client:
            response = client.post(settings.url, json=payload, headers=headers)
            response.raise_for_status()

    def _lock_for_schedule(self, schedule_id: str) -> threading.Lock:
        with self._run_lock_guard:
            lock = self._run_locks.get(schedule_id)
            if lock is None:
                lock = threading.Lock()
                self._run_locks[schedule_id] = lock
            return lock
