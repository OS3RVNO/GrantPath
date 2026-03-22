import { useEffect, useState } from 'react'

import {
  createReportSchedule,
  deleteReportSchedule,
  fetchReportSchedule,
  fetchReportSchedules,
  runReportSchedule,
  updateReportSchedule,
} from '../../api'
import { PRODUCT_NAME } from '../../branding'
import { useI18n } from '../../i18n'

import type {
  AccessReviewCampaignSummary,
  EntitySummary,
  ReportScheduleDetailResponse,
  ReportScheduleListResponse,
  ScenarioChoice,
} from '../../types'

type Draft = {
  name: string
  description: string
  enabled: boolean
  cadence: 'hourly' | 'daily' | 'weekly' | 'monthly'
  timezone: string
  hour: number
  minute: number
  day_of_week: string
  day_of_month: string
  kind: 'access_review' | 'review_campaign'
  locale: 'en' | 'it' | 'de' | 'fr' | 'es'
  formats: Array<'html' | 'pdf' | 'xlsx'>
  principal_id: string
  resource_id: string
  scenario_edge_id: string
  campaign_id: string
  title_override: string
  archive_enabled: boolean
  archive_directory: string
  email_enabled: boolean
  smtp_host: string
  smtp_port: number
  smtp_security: 'none' | 'starttls' | 'ssl'
  smtp_username: string
  smtp_password_env: string
  from_address: string
  to: string
  subject_template: string
  message_body: string
  webhook_enabled: boolean
  webhook_url: string
  webhook_secret_env: string
}

const DEFAULT_SUBJECT = `${PRODUCT_NAME} report: {schedule_name}`
const DEFAULT_BODY = `Your scheduled ${PRODUCT_NAME} report is attached.`

function makeDraft(locale: Draft['locale']): Draft {
  return {
    name: '',
    description: '',
    enabled: true,
    cadence: 'daily',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
    hour: 8,
    minute: 0,
    day_of_week: '1',
    day_of_month: '1',
    kind: 'access_review',
    locale,
    formats: ['pdf'],
    principal_id: '',
    resource_id: '',
    scenario_edge_id: '',
    campaign_id: '',
    title_override: '',
    archive_enabled: true,
    archive_directory: '',
    email_enabled: false,
    smtp_host: '',
    smtp_port: 587,
    smtp_security: 'starttls',
    smtp_username: '',
    smtp_password_env: '',
    from_address: '',
    to: '',
    subject_template: DEFAULT_SUBJECT,
    message_body: DEFAULT_BODY,
    webhook_enabled: false,
    webhook_url: '',
    webhook_secret_env: '',
  }
}

function splitCsv(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function draftFromDetail(detail: ReportScheduleDetailResponse): Draft {
  return {
    name: detail.summary.name,
    description: detail.summary.description ?? '',
    enabled: detail.summary.enabled,
    cadence: detail.summary.cadence,
    timezone: detail.summary.timezone,
    hour: detail.summary.hour,
    minute: detail.summary.minute,
    day_of_week: detail.summary.day_of_week == null ? '1' : String(detail.summary.day_of_week),
    day_of_month: detail.summary.day_of_month == null ? '1' : String(detail.summary.day_of_month),
    kind: detail.config.kind,
    locale: detail.config.locale,
    formats: [...detail.config.formats],
    principal_id: detail.config.principal_id ?? '',
    resource_id: detail.config.resource_id ?? '',
    scenario_edge_id: detail.config.scenario_edge_id ?? '',
    campaign_id: detail.config.campaign_id ?? '',
    title_override: detail.config.title_override ?? '',
    archive_enabled: detail.delivery.archive.enabled,
    archive_directory: detail.delivery.archive.directory ?? '',
    email_enabled: detail.delivery.email.enabled,
    smtp_host: detail.delivery.email.smtp_host ?? '',
    smtp_port: detail.delivery.email.smtp_port,
    smtp_security: detail.delivery.email.security,
    smtp_username: detail.delivery.email.username ?? '',
    smtp_password_env: detail.delivery.email.password_env ?? '',
    from_address: detail.delivery.email.from_address ?? '',
    to: detail.delivery.email.to.join(', '),
    subject_template: detail.delivery.email.subject_template,
    message_body: detail.delivery.email.message_body,
    webhook_enabled: detail.delivery.webhook.enabled,
    webhook_url: detail.delivery.webhook.url ?? '',
    webhook_secret_env: detail.delivery.webhook.secret_env ?? '',
  }
}

interface Props {
  principalOptions: EntitySummary[]
  resourceOptions: EntitySummary[]
  scenarioOptions: ScenarioChoice[]
  accessReviews: AccessReviewCampaignSummary[]
  canManage: boolean
}

export function ReportSchedulesPanel({
  principalOptions,
  resourceOptions,
  scenarioOptions,
  accessReviews,
  canManage,
}: Props) {
  const { locale, t, languageOptions, formatDateTime } = useI18n()
  const [list, setList] = useState<ReportScheduleListResponse | null>(null)
  const [detail, setDetail] = useState<ReportScheduleDetailResponse | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [draft, setDraft] = useState<Draft>(() => makeDraft(locale))
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  async function refresh(nextId?: string) {
    const schedules = await fetchReportSchedules()
    setList(schedules)
    const activeId = nextId ?? selectedId ?? schedules.schedules[0]?.id ?? ''
    setSelectedId(activeId)
    if (!activeId) {
      setDetail(null)
      setDraft(makeDraft(locale))
      return
    }
    const next = await fetchReportSchedule(activeId)
    setDetail(next)
    setDraft(draftFromDetail(next))
  }

  useEffect(() => {
    void (async () => {
      try {
        const schedules = await fetchReportSchedules()
        setList(schedules)
        const activeId = schedules.schedules[0]?.id ?? ''
        setSelectedId(activeId)
        if (!activeId) {
          setDetail(null)
          setDraft(makeDraft(locale))
          return
        }
        const next = await fetchReportSchedule(activeId)
        setDetail(next)
        setDraft(draftFromDetail(next))
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to load report schedules.')
      }
    })()
  }, [locale])

  function toggleFormat(format: 'html' | 'pdf' | 'xlsx') {
    setDraft((current) => ({
      ...current,
      formats: current.formats.includes(format)
        ? current.formats.filter((item) => item !== format)
        : [...current.formats, format],
    }))
  }

  function payload() {
    return {
      name: draft.name,
      description: draft.description || undefined,
      enabled: draft.enabled,
      cadence: draft.cadence,
      timezone: draft.timezone,
      hour: draft.hour,
      minute: draft.minute,
      day_of_week: draft.cadence === 'weekly' ? Number(draft.day_of_week || '1') : null,
      day_of_month: draft.cadence === 'monthly' ? Number(draft.day_of_month || '1') : null,
      config: {
        kind: draft.kind,
        locale: draft.locale,
        formats: draft.formats,
        principal_id: draft.principal_id || null,
        resource_id: draft.resource_id || null,
        scenario_edge_id: draft.scenario_edge_id || null,
        campaign_id: draft.campaign_id || null,
        title_override: draft.title_override || null,
      },
      delivery: {
        archive: { enabled: draft.archive_enabled, directory: draft.archive_directory || null },
        email: {
          enabled: draft.email_enabled,
          smtp_host: draft.smtp_host || null,
          smtp_port: draft.smtp_port,
          security: draft.smtp_security,
          username: draft.smtp_username || null,
          password_env: draft.smtp_password_env || null,
          from_address: draft.from_address || null,
          to: splitCsv(draft.to),
          cc: [],
          bcc: [],
          subject_template: draft.subject_template,
          message_body: draft.message_body,
          attach_formats: draft.formats,
          include_html_body: true,
        },
        webhook: {
          enabled: draft.webhook_enabled,
          url: draft.webhook_url || null,
          secret_env: draft.webhook_secret_env || null,
          secret_header: 'X-EIP-Webhook-Secret',
          include_summary: true,
        },
      },
    }
  }

  async function save() {
    if (!canManage) {
      setError(t('Your application role cannot manage scheduled reports.'))
      return
    }
    setBusy('save')
    setError('')
    try {
      const next = detail
        ? await updateReportSchedule(detail.summary.id, payload())
        : await createReportSchedule(payload())
      await refresh(next.summary.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save the report schedule.')
    } finally {
      setBusy('')
    }
  }

  return (
    <article className="panel panel--compact">
      <div className="panel__header">
        <div>
          <div className="eyebrow">{t('Scheduled Reports')}</div>
          <h2>{t('Automated delivery')}</h2>
        </div>
        <button
          type="button"
          className="mini-action"
          onClick={() => {
            setDetail(null)
            setSelectedId('')
            setDraft(makeDraft(locale))
          }}
          disabled={!canManage}
        >
          {t('New schedule')}
        </button>
      </div>
      {!canManage ? (
        <p className="admin-copy">
          {t('Your current application role can review scheduled reports but cannot change or run them.')}
        </p>
      ) : null}
      {error ? <div className="error-banner">{error}</div> : null}
      <div className="split-panel">
        <div className="split-panel__nav">
          <div className="list-stack">
            {(list?.schedules ?? []).map((schedule) => (
              <button key={schedule.id} type="button" className={`list-row ${selectedId === schedule.id ? 'list-row--selected' : 'list-row--static'}`} onClick={() => void refresh(schedule.id)}>
                <div>
                  <div className="table-primary">{schedule.name}</div>
                  <div className="table-secondary">{schedule.cadence} · {schedule.formats.join(', ')} · {schedule.channels.join(', ')}</div>
                </div>
                <span className={`status-pill status-pill--${schedule.enabled ? 'healthy' : 'idle'}`}>{schedule.last_status}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="split-panel__body">
          <form className="target-form" onSubmit={(event) => { event.preventDefault(); void save() }}>
            <div className="control-grid">
              <label className="field"><span>{t('Schedule name')}</span><input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} /></label>
              <label className="field"><span>{t('Language')}</span><select value={draft.locale} onChange={(event) => setDraft((current) => ({ ...current, locale: event.target.value as Draft['locale'] }))}>{languageOptions.map((option) => <option key={option.code} value={option.code}>{option.label}</option>)}</select></label>
            </div>
            <label className="field field--full"><span>{t('Description')}</span><input value={draft.description} onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} /></label>
            <div className="control-grid control-grid--tight">
              <label className="field"><span>{t('Report type')}</span><select value={draft.kind} onChange={(event) => setDraft((current) => ({ ...current, kind: event.target.value as Draft['kind'] }))}><option value="access_review">{t('Access review')}</option><option value="review_campaign">{t('Review campaign')}</option></select></label>
              <label className="field"><span>{t('Cadence')}</span><select value={draft.cadence} onChange={(event) => setDraft((current) => ({ ...current, cadence: event.target.value as Draft['cadence'] }))}><option value="hourly">{t('Hourly')}</option><option value="daily">{t('Daily')}</option><option value="weekly">{t('Weekly')}</option><option value="monthly">{t('Monthly')}</option></select></label>
              <label className="field"><span>{t('Timezone')}</span><input value={draft.timezone} onChange={(event) => setDraft((current) => ({ ...current, timezone: event.target.value }))} /></label>
              <label className="field"><span>{t('Hour')}</span><input type="number" min={0} max={23} value={draft.hour} onChange={(event) => setDraft((current) => ({ ...current, hour: Number(event.target.value) }))} /></label>
              <label className="field"><span>{t('Minute')}</span><input type="number" min={0} max={59} value={draft.minute} onChange={(event) => setDraft((current) => ({ ...current, minute: Number(event.target.value) }))} /></label>
            </div>
            <div className="summary-strip summary-strip--stacked">{(['html', 'pdf', 'xlsx'] as const).map((format) => <button key={format} type="button" className={`summary-chip summary-chip--button ${draft.formats.includes(format) ? 'summary-chip--active' : ''}`} onClick={() => toggleFormat(format)}><span>{t('Format')}</span><strong>{format.toUpperCase()}</strong></button>)}</div>
            {draft.kind === 'access_review' ? <div className="control-grid"><label className="field"><span>{t('Principal')}</span><select value={draft.principal_id} onChange={(event) => setDraft((current) => ({ ...current, principal_id: event.target.value }))}><option value="">{t('Select principal')}</option>{principalOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>{t('Resource')}</span><select value={draft.resource_id} onChange={(event) => setDraft((current) => ({ ...current, resource_id: event.target.value }))}><option value="">{t('Select resource')}</option>{resourceOptions.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>{t('Scenario')}</span><select value={draft.scenario_edge_id} onChange={(event) => setDraft((current) => ({ ...current, scenario_edge_id: event.target.value }))}><option value="">{t('Select scenario')}</option>{scenarioOptions.map((item) => <option key={item.edge_id} value={item.edge_id}>{item.label}</option>)}</select></label></div> : <label className="field"><span>{t('Review campaign')}</span><select value={draft.campaign_id} onChange={(event) => setDraft((current) => ({ ...current, campaign_id: event.target.value }))}><option value="">{t('Select campaign')}</option>{accessReviews.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
            <label className="field field--full"><span>{t('Title override')}</span><input value={draft.title_override} onChange={(event) => setDraft((current) => ({ ...current, title_override: event.target.value }))} /></label>
            <article className="context-card">
              <div className="context-card__header"><strong>{t('Delivery channels')}</strong></div>
              <div className="control-grid"><label className="field field--checkbox"><input type="checkbox" checked={draft.archive_enabled} onChange={(event) => setDraft((current) => ({ ...current, archive_enabled: event.target.checked }))} /><span>{t('Archive files locally')}</span></label><label className="field field--checkbox"><input type="checkbox" checked={draft.email_enabled} onChange={(event) => setDraft((current) => ({ ...current, email_enabled: event.target.checked }))} /><span>{t('Send email')}</span></label><label className="field field--checkbox"><input type="checkbox" checked={draft.webhook_enabled} onChange={(event) => setDraft((current) => ({ ...current, webhook_enabled: event.target.checked }))} /><span>{t('Send webhook')}</span></label></div>
              {draft.archive_enabled ? <label className="field field--full"><span>{t('Archive directory')}</span><input value={draft.archive_directory} onChange={(event) => setDraft((current) => ({ ...current, archive_directory: event.target.value }))} placeholder="C:\\Reports\\EIP" /></label> : null}
              {draft.email_enabled ? <><div className="control-grid"><label className="field"><span>{t('SMTP host')}</span><input value={draft.smtp_host} onChange={(event) => setDraft((current) => ({ ...current, smtp_host: event.target.value }))} /></label><label className="field"><span>{t('SMTP port')}</span><input type="number" min={1} max={65535} value={draft.smtp_port} onChange={(event) => setDraft((current) => ({ ...current, smtp_port: Number(event.target.value) }))} /></label><label className="field"><span>{t('Security')}</span><select value={draft.smtp_security} onChange={(event) => setDraft((current) => ({ ...current, smtp_security: event.target.value as Draft['smtp_security'] }))}><option value="starttls">STARTTLS</option><option value="ssl">SSL</option><option value="none">{t('None')}</option></select></label></div><div className="control-grid"><label className="field"><span>{t('SMTP username')}</span><input value={draft.smtp_username} onChange={(event) => setDraft((current) => ({ ...current, smtp_username: event.target.value }))} /></label><label className="field"><span>{t('SMTP password env')}</span><input value={draft.smtp_password_env} onChange={(event) => setDraft((current) => ({ ...current, smtp_password_env: event.target.value }))} /></label><label className="field"><span>{t('From address')}</span><input value={draft.from_address} onChange={(event) => setDraft((current) => ({ ...current, from_address: event.target.value }))} /></label></div><label className="field field--full"><span>{t('Recipients')}</span><input value={draft.to} onChange={(event) => setDraft((current) => ({ ...current, to: event.target.value }))} placeholder="ops@example.com, security@example.com" /></label><label className="field field--full"><span>{t('Subject template')}</span><input value={draft.subject_template} onChange={(event) => setDraft((current) => ({ ...current, subject_template: event.target.value }))} /></label><label className="field field--full"><span>{t('Message body')}</span><textarea className="import-textarea" value={draft.message_body} onChange={(event) => setDraft((current) => ({ ...current, message_body: event.target.value }))} /></label></> : null}
              {draft.webhook_enabled ? <div className="control-grid"><label className="field"><span>{t('Webhook URL')}</span><input value={draft.webhook_url} onChange={(event) => setDraft((current) => ({ ...current, webhook_url: event.target.value }))} /></label><label className="field"><span>{t('Secret env')}</span><input value={draft.webhook_secret_env} onChange={(event) => setDraft((current) => ({ ...current, webhook_secret_env: event.target.value }))} /></label></div> : null}
            </article>
            <div className="target-card__actions"><button className="primary-action" type="submit" disabled={busy === 'save' || !canManage}>{busy === 'save' ? t('Saving...') : detail ? t('Update schedule') : t('Create schedule')}</button>{detail ? <><button type="button" className="mini-action mini-action--strong" onClick={() => { if (!canManage) { setError(t('Your application role cannot manage scheduled reports.')); return } setBusy('run'); void runReportSchedule(detail.summary.id).then((next) => refresh(next.summary.id)).catch((err) => setError(err instanceof Error ? err.message : 'Unable to run the scheduled report.')).finally(() => setBusy('')) }} disabled={busy === 'run' || !canManage}>{busy === 'run' ? t('Running...') : t('Run now')}</button><button type="button" className="mini-action" onClick={() => { if (!canManage) { setError(t('Your application role cannot manage scheduled reports.')); return } setBusy('delete'); void deleteReportSchedule(detail.summary.id).then(() => refresh('')).catch((err) => setError(err instanceof Error ? err.message : 'Unable to delete the scheduled report.')).finally(() => setBusy('')) }} disabled={busy === 'delete' || !canManage}>{busy === 'delete' ? t('Removing...') : t('Delete schedule')}</button></> : null}</div>
          </form>
          {detail ? <div className="context-card"><div className="context-card__header"><strong>{t('Recent runs')}</strong><span className={`status-pill status-pill--${detail.summary.enabled ? 'healthy' : 'idle'}`}>{detail.summary.last_status}</span></div><div className="summary-strip"><div className="summary-chip"><span>{t('Next run')}</span><strong>{formatDateTime(detail.summary.next_run_at)}</strong></div><div className="summary-chip"><span>{t('Last run')}</span><strong>{formatDateTime(detail.summary.last_run_at)}</strong></div><div className="summary-chip"><span>{t('Channels')}</span><strong>{detail.summary.channels.join(', ') || 'n/d'}</strong></div></div><div className="list-stack">{detail.recent_runs.map((run) => <div key={run.id} className="target-card"><div className="target-card__header"><div><div className="table-primary">{formatDateTime(run.started_at)} · {run.trigger}</div><div className="table-secondary">{run.delivered_channels.join(', ')} · {run.message ?? 'n/d'}</div></div><span className={`status-pill status-pill--${run.status === 'success' ? 'healthy' : run.status === 'partial' ? 'warning' : 'critical'}`}>{run.status}</span></div>{run.artifact_paths.length ? <div className="connector-runtime-note">{run.artifact_paths.join('\n')}</div> : null}</div>)}</div></div> : null}
        </div>
      </div>
    </article>
  )
}
