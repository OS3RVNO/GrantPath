import type { MetricCard as MetricCardModel } from '../types'
import { useI18n } from '../i18n'

interface MetricCardProps {
  metric: MetricCardModel
}

export function MetricCard({ metric }: MetricCardProps) {
  const { t } = useI18n()
  return (
    <article className={`metric-card metric-card--${metric.tone}`}>
      <div className="eyebrow">{t(metric.title)}</div>
      <div className="metric-card__value">{metric.value}</div>
      <div className="metric-card__delta">{t(metric.delta)}</div>
      <p>{t(metric.description)}</p>
    </article>
  )
}
