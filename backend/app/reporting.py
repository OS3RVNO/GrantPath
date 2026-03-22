from __future__ import annotations

from html import escape
from io import BytesIO

import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.branding import PRODUCT_NAME, PRODUCT_REPORT_TITLE
from app.connector_blueprints import build_connector_blueprints
from app.engine import AccessGraphEngine
from app.models import AccessReviewCampaignDetailResponse
from app.report_i18n import normalize_report_locale, tr


def build_report_context(
    engine: AccessGraphEngine,
    principal_id: str,
    resource_id: str,
    scenario_edge_id: str,
    focus_resource_id: str | None = None,
) -> dict[str, object]:
    overview = engine.get_overview()
    explanation = engine.explain(principal_id, resource_id)
    resource_access = engine.get_resource_access(resource_id)
    principal_access = engine.get_principal_access(principal_id)
    simulation = engine.simulate_edge_removal(scenario_edge_id, focus_resource_id or resource_id)
    blueprints = build_connector_blueprints()

    return {
        "overview": overview,
        "explanation": explanation,
        "resource_access": resource_access,
        "principal_access": principal_access,
        "simulation": simulation,
        "blueprints": blueprints,
    }


def _filename_slug(*parts: str) -> str:
    joined = "-".join(part.lower().replace(" ", "-") for part in parts if part)
    safe = "".join(char for char in joined if char.isalnum() or char in {"-", "_"})
    return safe[:120] or "eip-report"


def report_filename(context: dict[str, object], extension: str, locale: str = "en") -> str:
    explanation = context["explanation"]
    resource_access = context["resource_access"]
    return (
        f"{_filename_slug(explanation.principal.name, resource_access.resource.name)}"
        f".{extension}"
    )


def review_campaign_report_filename(
    campaign: AccessReviewCampaignDetailResponse, extension: str, locale: str = "en"
) -> str:
    return f"{_filename_slug(campaign.summary.name)}.{extension}"


def _html_table(headers: list[str], rows: list[list[str]], column_classes: list[str] | None = None) -> str:
    header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body_html = []
    for row in rows:
        cells = []
        for index, cell in enumerate(row):
            cell_class = column_classes[index] if column_classes and index < len(column_classes) else ""
            class_attr = f' class="{cell_class}"' if cell_class else ""
            cells.append(f"<td{class_attr}>{escape(cell)}</td>")
        body_html.append(f"<tr>{''.join(cells)}</tr>")
    return (
        '<div class="table-wrap">'
        '<table class="report-table">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(body_html)}</tbody>"
        "</table>"
        "</div>"
    )


def _report_html_styles() -> str:
    return """
    body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; color: #14211f; background: #f3efe7; }
    .page { max-width: 1180px; margin: 0 auto; padding: 36px; }
    .hero { background: linear-gradient(135deg, #11201f, #305653); color: #fffaf4; border-radius: 28px; padding: 30px 34px; }
    .hero h1 { margin: 8px 0 10px; font-size: 32px; letter-spacing: -0.03em; }
    .hero p { color: #d6e5df; max-width: 78ch; margin: 0; }
    .meta { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 18px; }
    .meta span { background: rgba(255,255,255,0.12); padding: 8px 12px; border-radius: 999px; }
    .section { margin-top: 26px; background: #fffaf4; border: 1px solid #e2ddd4; border-radius: 24px; padding: 24px; }
    .section h2 { margin: 0 0 14px; font-size: 24px; letter-spacing: -0.02em; }
    .section-copy { color: #536563; margin: 0 0 18px; line-height: 1.6; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
    .metric { background: #f6f1e8; border-radius: 20px; padding: 18px; border: 1px solid #ebe3d7; }
    .metric .label { font-size: 12px; text-transform: uppercase; color: #6a7a77; letter-spacing: 0.12em; }
    .metric .value { font-size: 28px; font-weight: 700; margin-top: 8px; }
    .metric .delta { color: #c85c35; margin-top: 6px; line-height: 1.5; }
    .summary-grid { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 18px; }
    .summary-card { border: 1px solid #e8e0d4; border-radius: 18px; background: #fcfaf6; padding: 18px; }
    .summary-card h3 { margin: 0 0 12px; font-size: 16px; }
    .summary-list { display: grid; gap: 10px; margin: 0; }
    .summary-row { display: flex; justify-content: space-between; gap: 16px; padding-bottom: 10px; border-bottom: 1px solid #efe7da; }
    .summary-row:last-child { border-bottom: 0; padding-bottom: 0; }
    .summary-row span { color: #667774; }
    .path-stack { display: grid; gap: 14px; }
    .path { border: 1px solid #e6dfd4; border-radius: 18px; padding: 16px; background: #fcfaf6; }
    .path h4 { margin: 0; font-size: 15px; }
    .path p { margin: 10px 0 0; line-height: 1.65; color: #425b58; }
    .path-steps { display: grid; gap: 8px; margin: 14px 0 0; padding: 0; list-style: none; }
    .path-steps li { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border-radius: 14px; background: #eef6f2; color: #114943; }
    .path-steps strong { min-width: 88px; color: #0b615a; }
    .table-wrap { overflow: hidden; border: 1px solid #e7dfd2; border-radius: 18px; }
    .report-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    .report-table th, .report-table td { padding: 12px 14px; border-bottom: 1px solid #ece7dd; text-align: left; vertical-align: top; }
    .report-table th { background: #f6f1e8; font-size: 12px; text-transform: uppercase; color: #6a7a77; letter-spacing: 0.08em; }
    .report-table td { overflow-wrap: anywhere; word-break: break-word; line-height: 1.5; }
    .report-table tr:nth-child(even) td { background: #fdfbf8; }
    .col-permissions, .col-why, .col-resource, .col-principal { width: 28%; }
    .col-mode, .col-severity { width: 12%; }
    .col-paths, .col-risk, .col-count { width: 10%; text-align: center; white-space: nowrap; }
    .small-note { margin-top: 14px; color: #6a7a77; font-size: 13px; }
    @media (max-width: 920px) {
      .page { padding: 20px; }
      .metrics, .summary-grid { grid-template-columns: 1fr; }
      .summary-row { flex-direction: column; }
    }
    """


def _pdf_paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    safe = escape(text).replace("\n", "<br/>")
    return Paragraph(safe, style)


def render_html_report(context: dict[str, object], locale: str = "en") -> str:
    locale = normalize_report_locale(locale)
    overview = context["overview"]
    explanation = context["explanation"]
    resource_access = context["resource_access"]
    principal_access = context["principal_access"]
    simulation = context["simulation"]
    blueprints = context["blueprints"]

    metric_cards = "".join(
        f"""
        <div class="metric">
          <div class="label">{escape(metric.title)}</div>
          <div class="value">{escape(metric.value)}</div>
          <div class="delta">{escape(metric.delta)}</div>
        </div>
        """
        for metric in overview.metrics
    )
    path_blocks = "".join(
        f"""
        <div class="path">
          <h4>{escape(path.access_mode)} | risk {path.risk_score}</h4>
          <p>{escape(path.narrative)}</p>
          <ul class="path-steps">
            {''.join(f'<li><strong>{escape(step.edge_kind.replace("_", " ").title())}</strong><span>{escape(step.label)}</span></li>' for step in path.steps)}
          </ul>
        </div>
        """
        for path in explanation.paths
    )
    resource_table = _html_table(
        [
            tr(locale, "Principal"),
            tr(locale, "Permissions"),
            tr(locale, "Mode"),
            tr(locale, "Paths"),
            tr(locale, "Risk"),
            tr(locale, "Why"),
        ],
        [
            [
                record.principal.name,
                ", ".join(record.permissions),
                record.access_mode,
                str(record.path_count),
                str(record.risk_score),
                record.why,
            ]
            for record in resource_access.records
        ],
        ["col-principal", "col-permissions", "col-mode", "col-paths", "col-risk", "col-why"],
    )
    principal_table = _html_table(
        [
            tr(locale, "Resource"),
            tr(locale, "Permissions"),
            tr(locale, "Mode"),
            tr(locale, "Paths"),
            tr(locale, "Risk"),
            tr(locale, "Why"),
        ],
        [
            [
                record.resource.name,
                ", ".join(record.permissions),
                record.access_mode,
                str(record.path_count),
                str(record.risk_score),
                record.why,
            ]
            for record in principal_access.records
        ],
        ["col-resource", "col-permissions", "col-mode", "col-paths", "col-risk", "col-why"],
    )
    blast_table = _html_table(
        [
            tr(locale, "Resource"),
            tr(locale, "Impacted principals"),
            tr(locale, "Removed permissions"),
            tr(locale, "Severity"),
        ],
        [
            [
                item.resource.name,
                str(item.removed_principal_count),
                str(item.removed_permission_count),
                item.severity,
            ]
            for item in simulation.blast_radius
        ],
        ["col-resource", "col-count", "col-count", "col-severity"],
    )
    blueprint_table = _html_table(
        [
            tr(locale, "Vendor"),
            tr(locale, "Surface"),
            tr(locale, "Implementation"),
            tr(locale, "Mode"),
            tr(locale, "Freshness"),
        ],
        [
            [
                blueprint.vendor,
                blueprint.surface,
                tr(locale, blueprint.implementation_status),
                tr(locale, blueprint.collection_mode),
                blueprint.freshness,
            ]
            for blueprint in blueprints.blueprints
        ],
        ["", "col-resource", "col-mode", "col-mode", "col-why"],
    )

    return f"""<!DOCTYPE html>
<html lang="{locale}">
<head>
  <meta charset="utf-8" />
  <title>{escape(tr(locale, PRODUCT_REPORT_TITLE))}</title>
  <style>{_report_html_styles()}</style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div>{escape(tr(locale, PRODUCT_NAME))}</div>
      <h1>{escape(tr(locale, "Access Review Report"))}</h1>
      <p>{escape(tr(locale, "Operator-grade explainability for identity, group, role, ACL and delegated access review."))}</p>
      <div class="meta">
        <span>{escape(tr(locale, "Tenant"))}: {escape(overview.tenant)}</span>
        <span>{escape(tr(locale, "Principal"))}: {escape(explanation.principal.name)}</span>
        <span>{escape(tr(locale, "Resource"))}: {escape(explanation.resource.name)}</span>
        <span>{escape(tr(locale, "Scenario"))}: {escape(simulation.edge.label)}</span>
      </div>
    </section>

    <section class="section">
      <h2>{escape(tr(locale, "Executive Summary"))}</h2>
      <div class="metrics">{metric_cards}</div>
    </section>

    <section class="section">
      <h2>{escape(tr(locale, "Why This Access Exists"))}</h2>
      <div class="summary-grid">
        <div class="summary-card">
          <h3>{escape(tr(locale, "Access answer"))}</h3>
          <div class="summary-list">
            <div class="summary-row"><span>{escape(tr(locale, "Principal"))}</span><strong>{escape(explanation.principal.name)}</strong></div>
            <div class="summary-row"><span>{escape(tr(locale, "Resource"))}</span><strong>{escape(explanation.resource.name)}</strong></div>
            <div class="summary-row"><span>{escape(tr(locale, "Effective permissions"))}</span><strong>{escape(', '.join(explanation.permissions))}</strong></div>
            <div class="summary-row"><span>{escape(tr(locale, "Primary path count"))}</span><strong>{explanation.path_count}</strong></div>
          </div>
        </div>
        <div class="summary-card">
          <h3>{escape(tr(locale, "Risk posture"))}</h3>
          <div class="summary-list">
            <div class="summary-row"><span>{escape(tr(locale, "Risk score"))}</span><strong>{explanation.risk_score}</strong></div>
            <div class="summary-row"><span>{escape(tr(locale, "Scenario edge"))}</span><strong>{escape(simulation.edge.label)}</strong></div>
            <div class="summary-row"><span>{escape(tr(locale, "Impacted principals"))}</span><strong>{simulation.impacted_principals}</strong></div>
            <div class="summary-row"><span>{escape(tr(locale, "Privileged paths removed"))}</span><strong>{simulation.privileged_paths_removed}</strong></div>
          </div>
        </div>
      </div>
      <p class="section-copy">{escape(tr(locale, "The explanation below ranks the clearest access paths first, then keeps the operational blast radius ready for review or export."))}</p>
      <div class="path-stack">{path_blocks}</div>
    </section>

    <section class="section">
      <h2>{escape(tr(locale, "Who Has Access To {resource}", resource=resource_access.resource.name))}</h2>
      <p class="section-copy">{escape(tr(locale, "Resource exposure is flattened and pre-ranked for readability, including permission mode and supporting rationale."))}</p>
      {resource_table}
    </section>

    <section class="section">
      <h2>{escape(tr(locale, "Principal Footprint"))}</h2>
      <p class="section-copy">{escape(tr(locale, "This section shows where the selected principal still has effective coverage across the current snapshot."))}</p>
      {principal_table}
    </section>

    <section class="section">
      <h2>{escape(tr(locale, "What-If Blast Radius"))}</h2>
      <p class="section-copy">{escape(simulation.narrative)}</p>
      {blast_table}
    </section>

    <section class="section">
      <h2>{escape(tr(locale, "Official Connector Blueprint"))}</h2>
      <p class="section-copy">{escape(tr(locale, "Collector coverage is shown exactly as implemented today, so the report stays honest about what is live, partial or blueprint-only."))}</p>
      {blueprint_table}
      <div class="small-note">{escape(tr(locale, "Generated by GrantPath. Export designed for operational reviews, evidence packages and executive briefings."))}</div>
    </section>
  </div>
</body>
</html>
"""


def render_pdf_report(context: dict[str, object], locale: str = "en") -> bytes:
    locale = normalize_report_locale(locale)
    overview = context["overview"]
    explanation = context["explanation"]
    resource_access = context["resource_access"]
    principal_access = context["principal_access"]
    simulation = context["simulation"]
    blueprints = context["blueprints"]

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#11201f"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyTight",
            parent=styles["BodyText"],
            textColor=colors.HexColor("#425b58"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#203230"),
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
            textColor=colors.whitesmoke,
            spaceAfter=0,
        )
    )

    story = [
        Paragraph(tr(locale, PRODUCT_REPORT_TITLE), styles["Title"]),
        Spacer(1, 6),
        Paragraph(
            f"{escape(tr(locale, 'Tenant'))}: {escape(overview.tenant)} | {escape(tr(locale, 'Principal'))}: {escape(explanation.principal.name)} | "
            f"{escape(tr(locale, 'Resource'))}: {escape(explanation.resource.name)}",
            styles["BodyTight"],
        ),
        Spacer(1, 10),
        Paragraph(tr(locale, "Executive Summary"), styles["SectionTitle"]),
    ]

    metric_table = Table(
        [[_pdf_paragraph(tr(locale, "Metric"), styles["TableHeader"]), _pdf_paragraph(tr(locale, "Value"), styles["TableHeader"]), _pdf_paragraph(tr(locale, "Delta"), styles["TableHeader"])]]
        + [
            [
                _pdf_paragraph(metric.title, styles["TableCell"]),
                _pdf_paragraph(metric.value, styles["TableCell"]),
                _pdf_paragraph(metric.delta, styles["TableCell"]),
            ]
            for metric in overview.metrics
        ],
        colWidths=[65 * mm, 30 * mm, 55 * mm],
        repeatRows=1,
    )
    metric_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#11201f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d4cb")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fffaf4"), colors.HexColor("#f7f2ea")]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([metric_table, Spacer(1, 12)])

    story.append(Paragraph(tr(locale, "Why This Access Exists"), styles["SectionTitle"]))
    story.append(
        Paragraph(
            f"{escape(tr(locale, 'Permissions'))}: {escape(', '.join(explanation.permissions))} | {escape(tr(locale, 'Paths'))}: {explanation.path_count} | {escape(tr(locale, 'Risk'))}: {explanation.risk_score}",
            styles["BodyTight"],
        )
    )
    for path in explanation.paths:
        story.append(Paragraph(f"<b>{escape(tr(locale, path.access_mode))}</b> | {escape(tr(locale, 'risk {value}', value=path.risk_score))}", styles["BodyText"]))
        story.append(Paragraph(escape(path.narrative), styles["BodyTight"]))

    story.extend([Spacer(1, 8), Paragraph(tr(locale, "Who Has Access"), styles["SectionTitle"])])
    access_table = Table(
        [[
            _pdf_paragraph(tr(locale, "Principal"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Permissions"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Mode"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Paths"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Risk"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Why"), styles["TableHeader"]),
        ]]
        + [
            [
                _pdf_paragraph(record.principal.name, styles["TableCell"]),
                _pdf_paragraph(", ".join(record.permissions), styles["TableCell"]),
                _pdf_paragraph(record.access_mode, styles["TableCell"]),
                _pdf_paragraph(str(record.path_count), styles["TableCell"]),
                _pdf_paragraph(str(record.risk_score), styles["TableCell"]),
                _pdf_paragraph(record.why, styles["TableCell"]),
            ]
            for record in resource_access.records[:12]
        ],
        colWidths=[34 * mm, 44 * mm, 18 * mm, 14 * mm, 14 * mm, 54 * mm],
        repeatRows=1,
    )
    access_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#305653")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d4cb")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7f5")]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([access_table, Spacer(1, 12)])

    story.append(Paragraph(tr(locale, "Principal Footprint"), styles["SectionTitle"]))
    principal_table = Table(
        [[
            _pdf_paragraph(tr(locale, "Resource"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Permissions"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Mode"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Paths"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Risk"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Why"), styles["TableHeader"]),
        ]]
        + [
            [
                _pdf_paragraph(record.resource.name, styles["TableCell"]),
                _pdf_paragraph(", ".join(record.permissions), styles["TableCell"]),
                _pdf_paragraph(record.access_mode, styles["TableCell"]),
                _pdf_paragraph(str(record.path_count), styles["TableCell"]),
                _pdf_paragraph(str(record.risk_score), styles["TableCell"]),
                _pdf_paragraph(record.why, styles["TableCell"]),
            ]
            for record in principal_access.records[:12]
        ],
        colWidths=[34 * mm, 44 * mm, 18 * mm, 14 * mm, 14 * mm, 54 * mm],
        repeatRows=1,
    )
    principal_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#11201f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d4cb")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f2ea")]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([principal_table, Spacer(1, 12)])

    story.append(Paragraph(tr(locale, "What-If Blast Radius"), styles["SectionTitle"]))
    story.append(Paragraph(escape(simulation.narrative), styles["BodyTight"]))
    blast_table = Table(
        [[
            _pdf_paragraph(tr(locale, "Resource"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Impacted principals"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Removed permissions"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Severity"), styles["TableHeader"]),
        ]]
        + [
            [
                _pdf_paragraph(item.resource.name, styles["TableCell"]),
                _pdf_paragraph(str(item.removed_principal_count), styles["TableCell"]),
                _pdf_paragraph(str(item.removed_permission_count), styles["TableCell"]),
                _pdf_paragraph(item.severity, styles["TableCell"]),
            ]
            for item in simulation.blast_radius
        ],
        colWidths=[62 * mm, 35 * mm, 28 * mm, 28 * mm],
        repeatRows=1,
    )
    blast_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c85c35")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d4cb")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff5ee")]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([blast_table, Spacer(1, 12)])

    story.append(Paragraph(tr(locale, "Official Connector Blueprint"), styles["SectionTitle"]))
    blueprint_table = Table(
        [[
            _pdf_paragraph(tr(locale, "Surface"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Implementation"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Mode"), styles["TableHeader"]),
            _pdf_paragraph(tr(locale, "Freshness"), styles["TableHeader"]),
        ]]
        + [
            [
                _pdf_paragraph(blueprint.surface, styles["TableCell"]),
                _pdf_paragraph(tr(locale, blueprint.implementation_status), styles["TableCell"]),
                _pdf_paragraph(tr(locale, blueprint.collection_mode), styles["TableCell"]),
                _pdf_paragraph(blueprint.freshness, styles["TableCell"]),
            ]
            for blueprint in blueprints.blueprints
        ],
        colWidths=[54 * mm, 28 * mm, 24 * mm, 66 * mm],
        repeatRows=1,
    )
    blueprint_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#11201f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d4cb")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f2ea")]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(blueprint_table)

    doc.build(story)
    return buffer.getvalue()


def render_excel_report(context: dict[str, object], locale: str = "en") -> bytes:
    locale = normalize_report_locale(locale)
    overview = context["overview"]
    explanation = context["explanation"]
    resource_access = context["resource_access"]
    principal_access = context["principal_access"]
    simulation = context["simulation"]
    blueprints = context["blueprints"]

    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    title_format = workbook.add_format(
        {"bold": True, "font_size": 15, "font_color": "#11201f"}
    )
    header_format = workbook.add_format(
        {
            "bold": True,
            "font_color": "white",
            "bg_color": "#11201f",
            "border": 1,
        }
    )
    cell_format = workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    accent_format = workbook.add_format({"bold": True, "font_color": "#c85c35"})
    number_format = workbook.add_format({"border": 1, "valign": "top", "align": "center"})
    note_format = workbook.add_format({"text_wrap": True, "font_color": "#536563", "valign": "top"})

    summary_sheet = workbook.add_worksheet("Summary")
    summary_sheet.hide_gridlines(2)
    summary_sheet.set_column("A:A", 28)
    summary_sheet.set_column("B:B", 28)
    summary_sheet.set_column("C:C", 52)
    summary_sheet.write("A1", tr(locale, PRODUCT_REPORT_TITLE), title_format)
    summary_sheet.write("A3", tr(locale, "Tenant"), accent_format)
    summary_sheet.write("B3", overview.tenant)
    summary_sheet.write("A4", tr(locale, "Principal"), accent_format)
    summary_sheet.write("B4", explanation.principal.name)
    summary_sheet.write("A5", tr(locale, "Resource"), accent_format)
    summary_sheet.write("B5", explanation.resource.name)
    summary_sheet.write("C3", tr(locale, "Summary"), accent_format)
    summary_sheet.write("C4", ", ".join(explanation.permissions), note_format)
    summary_sheet.write("C5", f"{tr(locale, 'Paths')}: {explanation.path_count} | {tr(locale, 'Risk')}: {explanation.risk_score}", note_format)
    summary_sheet.write("A7", tr(locale, "Metric"), header_format)
    summary_sheet.write("B7", tr(locale, "Value"), header_format)
    summary_sheet.write("C7", tr(locale, "Commentary"), header_format)
    for row_index, metric in enumerate(overview.metrics, start=7):
        summary_sheet.write(row_index, 0, metric.title, cell_format)
        summary_sheet.write(row_index, 1, metric.value, cell_format)
        summary_sheet.write(row_index, 2, metric.description, cell_format)

    access_sheet = workbook.add_worksheet("Resource Access")
    access_sheet.freeze_panes(1, 0)
    access_sheet.autofilter(0, 0, max(len(resource_access.records), 1), 5)
    access_sheet.set_default_row(24)
    access_sheet.set_column("A:A", 28)
    access_sheet.set_column("B:B", 38)
    access_sheet.set_column("C:C", 16)
    access_sheet.set_column("D:E", 10)
    access_sheet.set_column("F:F", 52)
    headers = [tr(locale, "Principal"), tr(locale, "Permissions"), tr(locale, "Mode"), tr(locale, "Paths"), tr(locale, "Risk"), tr(locale, "Why")]
    for column_index, header in enumerate(headers):
        access_sheet.write(0, column_index, header, header_format)
    for row_index, record in enumerate(resource_access.records, start=1):
        access_sheet.write(row_index, 0, record.principal.name, cell_format)
        access_sheet.write(row_index, 1, ", ".join(record.permissions), cell_format)
        access_sheet.write(row_index, 2, record.access_mode, cell_format)
        access_sheet.write(row_index, 3, record.path_count, number_format)
        access_sheet.write(row_index, 4, record.risk_score, number_format)
        access_sheet.write(row_index, 5, record.why, cell_format)

    principal_sheet = workbook.add_worksheet("Principal Footprint")
    principal_sheet.freeze_panes(1, 0)
    principal_sheet.autofilter(0, 0, max(len(principal_access.records), 1), 5)
    principal_sheet.set_default_row(24)
    principal_sheet.set_column("A:A", 30)
    principal_sheet.set_column("B:B", 38)
    principal_sheet.set_column("C:C", 16)
    principal_sheet.set_column("D:E", 10)
    principal_sheet.set_column("F:F", 52)
    for column_index, header in enumerate([tr(locale, "Resource"), tr(locale, "Permissions"), tr(locale, "Mode"), tr(locale, "Paths"), tr(locale, "Risk"), tr(locale, "Why")]):
        principal_sheet.write(0, column_index, header, header_format)
    for row_index, record in enumerate(principal_access.records, start=1):
        principal_sheet.write(row_index, 0, record.resource.name, cell_format)
        principal_sheet.write(row_index, 1, ", ".join(record.permissions), cell_format)
        principal_sheet.write(row_index, 2, record.access_mode, cell_format)
        principal_sheet.write(row_index, 3, record.path_count, number_format)
        principal_sheet.write(row_index, 4, record.risk_score, number_format)
        principal_sheet.write(row_index, 5, record.why, cell_format)

    scenario_sheet = workbook.add_worksheet("What If")
    scenario_sheet.freeze_panes(1, 0)
    scenario_sheet.autofilter(0, 0, max(len(simulation.blast_radius), 1), 3)
    scenario_sheet.set_default_row(24)
    scenario_sheet.set_column("A:A", 56)
    scenario_sheet.set_column("B:C", 18)
    scenario_sheet.set_column("D:D", 18)
    for column_index, header in enumerate(
        [tr(locale, "Resource"), tr(locale, "Impacted principals"), tr(locale, "Removed permissions"), tr(locale, "Severity")]
    ):
        scenario_sheet.write(0, column_index, header, header_format)
    for row_index, item in enumerate(simulation.blast_radius, start=1):
        scenario_sheet.write(row_index, 0, item.resource.name, cell_format)
        scenario_sheet.write(row_index, 1, item.removed_principal_count, number_format)
        scenario_sheet.write(row_index, 2, item.removed_permission_count, number_format)
        scenario_sheet.write(row_index, 3, item.severity, cell_format)
    scenario_sheet.write("A14", tr(locale, "Commentary"), accent_format)
    scenario_sheet.write("A15", simulation.narrative, note_format)

    blueprint_sheet = workbook.add_worksheet("Connector Blueprint")
    blueprint_sheet.freeze_panes(1, 0)
    blueprint_sheet.autofilter(0, 0, max(len(blueprints.blueprints), 1), 4)
    blueprint_sheet.set_default_row(24)
    blueprint_sheet.set_column("A:A", 18)
    blueprint_sheet.set_column("B:B", 30)
    blueprint_sheet.set_column("C:D", 16)
    blueprint_sheet.set_column("E:E", 44)
    for column_index, header in enumerate([tr(locale, "Vendor"), tr(locale, "Surface"), tr(locale, "Implementation"), tr(locale, "Mode"), tr(locale, "Freshness")]):
        blueprint_sheet.write(0, column_index, header, header_format)
    for row_index, blueprint in enumerate(blueprints.blueprints, start=1):
        blueprint_sheet.write(row_index, 0, blueprint.vendor, cell_format)
        blueprint_sheet.write(row_index, 1, blueprint.surface, cell_format)
        blueprint_sheet.write(row_index, 2, tr(locale, blueprint.implementation_status), cell_format)
        blueprint_sheet.write(row_index, 3, tr(locale, blueprint.collection_mode), cell_format)
        blueprint_sheet.write(row_index, 4, blueprint.freshness, cell_format)

    workbook.close()
    return buffer.getvalue()


def render_review_campaign_html_report(campaign: AccessReviewCampaignDetailResponse, locale: str = "en") -> str:
    locale = normalize_report_locale(locale)
    item_table = _html_table(
        [tr(locale, "Principal"), tr(locale, "Resource"), tr(locale, "Permissions"), tr(locale, "Risk"), tr(locale, "Decision"), tr(locale, "Remediation")],
        [
            [
                item.principal.name,
                item.resource.name,
                ", ".join(item.permissions),
                str(item.risk_score),
                item.decision,
                item.suggested_remediation or "",
            ]
            for item in campaign.items
        ],
        ["col-principal", "col-resource", "col-permissions", "col-risk", "col-mode", "col-why"],
    )
    return f"""<!DOCTYPE html>
<html lang="{locale}">
<head>
  <meta charset="utf-8" />
  <title>{escape(tr(locale, "Access Review Campaign"))}</title>
  <style>{_report_html_styles()}</style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div>{escape(tr(locale, PRODUCT_NAME))}</div>
      <h1>{escape(campaign.summary.name)}</h1>
      <p>{escape(campaign.summary.description or tr(locale, 'Review Campaign'))}</p>
    </section>
    <section class="section">
      <div class="metrics">
        <div class="metric"><div>{escape(tr(locale, "Total items"))}</div><strong>{campaign.summary.total_items}</strong></div>
        <div class="metric"><div>{escape(tr(locale, "Pending"))}</div><strong>{campaign.summary.pending_items}</strong></div>
        <div class="metric"><div>{escape(tr(locale, "Revoke"))}</div><strong>{campaign.summary.revoke_count}</strong></div>
        <div class="metric"><div>{escape(tr(locale, "Follow up"))}</div><strong>{campaign.summary.follow_up_count}</strong></div>
      </div>
    </section>
    <section class="section">
      <h2>{escape(tr(locale, "Reviewed access"))}</h2>
      <p class="section-copy">{escape(tr(locale, "Campaign evidence is formatted for auditability: affected identity, target resource, effective permissions, reviewer decision and suggested remediation."))}</p>
      {item_table}
    </section>
  </div>
</body>
</html>
"""


def render_review_campaign_pdf_report(campaign: AccessReviewCampaignDetailResponse, locale: str = "en") -> bytes:
    locale = normalize_report_locale(locale)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReviewTableCell",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=11,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReviewTableHeader",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
            textColor=colors.whitesmoke,
            spaceAfter=0,
        )
    )
    story = [
        Paragraph(campaign.summary.name, styles["Title"]),
        Spacer(1, 6),
        Paragraph(escape(campaign.summary.description or tr(locale, "Review Campaign")), styles["BodyText"]),
        Spacer(1, 10),
    ]
    summary_table = Table(
        [
            [tr(locale, "Total items"), tr(locale, "Pending"), tr(locale, "Keep"), tr(locale, "Revoke"), tr(locale, "Follow up")],
            [
                str(campaign.summary.total_items),
                str(campaign.summary.pending_items),
                str(campaign.summary.keep_count),
                str(campaign.summary.revoke_count),
                str(campaign.summary.follow_up_count),
            ],
        ],
        colWidths=[34 * mm, 28 * mm, 28 * mm, 28 * mm, 32 * mm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#11201f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d4cb")),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 10)])
    item_table = Table(
        [[
            _pdf_paragraph(tr(locale, "Principal"), styles["ReviewTableHeader"]),
            _pdf_paragraph(tr(locale, "Resource"), styles["ReviewTableHeader"]),
            _pdf_paragraph(tr(locale, "Permissions"), styles["ReviewTableHeader"]),
            _pdf_paragraph(tr(locale, "Risk"), styles["ReviewTableHeader"]),
            _pdf_paragraph(tr(locale, "Decision"), styles["ReviewTableHeader"]),
            _pdf_paragraph(tr(locale, "Remediation"), styles["ReviewTableHeader"]),
        ]]
        + [
            [
                _pdf_paragraph(item.principal.name, styles["ReviewTableCell"]),
                _pdf_paragraph(item.resource.name, styles["ReviewTableCell"]),
                _pdf_paragraph(", ".join(item.permissions), styles["ReviewTableCell"]),
                _pdf_paragraph(str(item.risk_score), styles["ReviewTableCell"]),
                _pdf_paragraph(item.decision, styles["ReviewTableCell"]),
                _pdf_paragraph(item.suggested_remediation or "", styles["ReviewTableCell"]),
            ]
            for item in campaign.items[:20]
        ],
        colWidths=[26 * mm, 28 * mm, 40 * mm, 14 * mm, 22 * mm, 54 * mm],
        repeatRows=1,
    )
    item_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#305653")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d4cb")),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(item_table)
    doc.build(story)
    return buffer.getvalue()


def render_review_campaign_excel_report(campaign: AccessReviewCampaignDetailResponse, locale: str = "en") -> bytes:
    locale = normalize_report_locale(locale)
    buffer = BytesIO()
    workbook = xlsxwriter.Workbook(buffer, {"in_memory": True})
    title_format = workbook.add_format({"bold": True, "font_size": 15, "font_color": "#11201f"})
    header_format = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#11201f", "border": 1})
    cell_format = workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    number_format = workbook.add_format({"border": 1, "align": "center", "valign": "top"})
    sheet = workbook.add_worksheet("Review Campaign")
    sheet.freeze_panes(5, 0)
    sheet.set_default_row(24)
    sheet.set_column("A:B", 24)
    sheet.set_column("C:C", 34)
    sheet.set_column("D:E", 14)
    sheet.set_column("F:F", 52)
    sheet.write("A1", campaign.summary.name, title_format)
    sheet.write("A3", tr(locale, "Description"), header_format)
    sheet.write("B3", campaign.summary.description or "", cell_format)
    sheet.write_row("A5", [tr(locale, "Principal"), tr(locale, "Resource"), tr(locale, "Permissions"), tr(locale, "Risk"), tr(locale, "Decision"), tr(locale, "Remediation")], header_format)
    for row_index, item in enumerate(campaign.items, start=5):
        sheet.write(row_index, 0, item.principal.name, cell_format)
        sheet.write(row_index, 1, item.resource.name, cell_format)
        sheet.write(row_index, 2, ", ".join(item.permissions), cell_format)
        sheet.write(row_index, 3, item.risk_score, number_format)
        sheet.write(row_index, 4, item.decision, cell_format)
        sheet.write(row_index, 5, item.suggested_remediation or "", cell_format)
    workbook.close()
    return buffer.getvalue()
