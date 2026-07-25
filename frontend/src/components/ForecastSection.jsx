import { useEffect, useState } from 'react'
import { api } from '../api'

const RISK_LABEL = { low: 'Low', moderate: 'Moderate', high: 'High' }
const TREND_LABEL = { declining: 'Declining', steady: 'Holding steady', improving: 'Improving' }

// Solid line = what actually happened. Dashed line = where it's heading if nothing changes.
// The horizontal rule is the low-capacity line; the point where the dashed line crosses it
// is the whole argument of this screen, so it gets its own marker and label.
function CapacityTrendChart({ points, projection, lowLine, riskDay }) {
  if (points.length < 2) {
    return <p className="empty">A couple more days of check-ins and your trend line appears here.</p>
  }
  const width = 640
  const height = 200
  const padLeft = 30
  const padRight = 60
  const padY = 26

  const history = points.map((p) => ({ capacity: p.capacity, label: null, projected: false }))
  const future = (projection || []).map((p) => ({
    capacity: p.capacity,
    label: p.weekday.slice(0, 3),
    projected: true,
    isRiskDay: riskDay != null && p.date === riskDay,
  }))
  const series = [...history, ...future]

  const xAt = (i) => padLeft + (i / (series.length - 1)) * (width - padLeft - padRight)
  const yAt = (c) => height - padY - (c / 100) * (height - padY * 2)
  const coords = series.map((s, i) => ({ ...s, x: xAt(i), y: yAt(s.capacity) }))

  const solid = coords.filter((c) => !c.projected)
  const dashed = coords.filter((c) => c.projected)
  const lastSolid = solid[solid.length - 1]

  const line = (pts) => pts.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x} ${c.y}`).join(' ')
  // Start the dashed run at the last real point so the projection visibly continues the line.
  const dashedPath = dashed.length ? line([lastSolid, ...dashed]) : ''

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label="Capacity trend and projection">
      <line x1={padLeft} y1={height - padY} x2={width - padRight} y2={height - padY} className="trend-axis" />

      {lowLine != null && (
        <>
          <line x1={padLeft} y1={yAt(lowLine)} x2={width - padRight} y2={yAt(lowLine)} className="trend-lowline" />
          <text x={width - padRight + 6} y={yAt(lowLine) + 4} className="trend-lowline-label">
            low
          </text>
        </>
      )}

      <path d={line(solid)} className="trend-line" fill="none" />
      {dashedPath && <path d={dashedPath} className="trend-line trend-line-projected" fill="none" />}

      {solid.map((c, i) => (
        <circle key={`h${i}`} cx={c.x} cy={c.y} r={3.5} className="trend-dot" />
      ))}
      {dashed.map((c, i) => (
        <g key={`p${i}`}>
          <circle
            cx={c.x}
            cy={c.y}
            r={c.isRiskDay ? 6 : 4}
            className={`trend-dot trend-dot-projected${c.isRiskDay ? ' trend-dot-risk' : ''}`}
          />
          <text x={c.x} y={height - padY + 15} textAnchor="middle" className="trend-tick">
            {c.label}
          </text>
        </g>
      ))}
    </svg>
  )
}

// Forecast card + capacity trend. Self-fetches. Renders nothing until there's data.
export function ForecastSection() {
  const [forecast, setForecast] = useState(null)
  useEffect(() => {
    api.capacityForecast(14).then(setForecast).catch(() => {})
  }, [])

  if (!forecast || forecast.days_of_data === 0) return null

  const projection = forecast.projection || []

  return (
    <div className="understand-section">
      <h2>What's next</h2>
      <div className={`forecast-card risk-${forecast.risk}`}>
        <div className="forecast-head">
          <span className="risk-badge">{RISK_LABEL[forecast.risk]} risk ahead</span>
          <span className="forecast-trend">Trend: {TREND_LABEL[forecast.trend]}</span>
        </div>

        {/* The projection as a chain, which is the point: not one number, a direction. */}
        {projection.length > 0 && (
          <div className="projection-chain">
            <span className="projection-step now">
              <span className="projection-value">{forecast.points[forecast.points.length - 1].capacity}</span>
              <span className="projection-label">today</span>
            </span>
            {projection.map((p) => (
              <span key={p.date} className={`projection-step${p.date === forecast.risk_day ? ' risk' : ''}`}>
                <span className="projection-arrow">→</span>
                <span className="projection-value">{p.capacity}</span>
                <span className="projection-label">{p.weekday.slice(0, 3)}</span>
              </span>
            ))}
          </div>
        )}

        {forecast.risk_day_weekday && (
          <p className="forecast-riskday">
            On this trend you're most likely to be running low on{' '}
            <strong>{forecast.risk_day_weekday}</strong>.
          </p>
        )}

        <div className="forecast-metrics">
          {forecast.consecutive_decline_days > 0 && (
            <div className="forecast-metric">
              <span className="forecast-metric-value">↓ {forecast.consecutive_decline_days}d</span>
              <span className="forecast-metric-label">declining streak</span>
            </div>
          )}
          {forecast.recurring_driver && (
            <div className="forecast-metric">
              <span className="forecast-metric-value">{forecast.recurring_driver}</span>
              <span className="forecast-metric-label">recurring driver</span>
            </div>
          )}
          {forecast.weekday_pattern && (
            <div className="forecast-metric">
              <span className="forecast-metric-value">{forecast.weekday_pattern}s</span>
              <span className="forecast-metric-label">hardest day, repeatedly</span>
            </div>
          )}
        </div>

        <p className="forecast-text">{forecast.forecast}</p>

        {forecast.weekday_pattern_note && (
          <p className="forecast-pattern">{forecast.weekday_pattern_note}</p>
        )}

        {forecast.suggestions?.length > 0 && (
          <ul className="risk-suggestions">
            {forecast.suggestions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        )}
      </div>

      <h3 className="trend-heading">Capacity trend (last {forecast.days_of_data} days) and projection</h3>
      <CapacityTrendChart
        points={forecast.points}
        projection={projection}
        lowLine={forecast.low_capacity_line}
        riskDay={forecast.risk_day}
      />
      <p className="factor-note">
        Solid line = your check-ins. Dashed line = projected from your recent trend, assuming
        nothing changes. It's a direction, not a diagnosis.
      </p>
    </div>
  )
}
