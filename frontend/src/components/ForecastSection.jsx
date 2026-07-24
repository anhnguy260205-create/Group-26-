import { useEffect, useState } from 'react'
import { api } from '../api'

const RISK_LABEL = { low: 'Low', moderate: 'Moderate', high: 'High' }
const TREND_LABEL = { declining: 'Declining', steady: 'Holding steady', improving: 'Improving' }

function CapacityTrendChart({ points, predicted }) {
  if (points.length < 2) {
    return <p className="empty">A couple more days of check-ins and your trend line appears here.</p>
  }
  const width = 560
  const height = 160
  const padding = 24
  const series = points.map((p) => ({ ...p, projected: false }))
  if (predicted != null) series.push({ capacity: predicted, projected: true })

  const xAt = (i) => padding + (i / (series.length - 1)) * (width - padding * 2)
  const yAt = (c) => height - padding - (c / 100) * (height - padding * 2)
  const coords = series.map((s, i) => ({ x: xAt(i), y: yAt(s.capacity), ...s }))
  const solid = coords.filter((c) => !c.projected)
  const solidPath = solid.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x} ${c.y}`).join(' ')
  const lastSolid = solid[solid.length - 1]
  const proj = coords.find((c) => c.projected)

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label="Capacity trend">
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} className="trend-axis" />
      <path d={solidPath} className="trend-line" fill="none" />
      {proj && (
        <path d={`M ${lastSolid.x} ${lastSolid.y} L ${proj.x} ${proj.y}`} className="trend-line trend-line-projected" fill="none" />
      )}
      {solid.map((c, i) => (
        <circle key={i} cx={c.x} cy={c.y} r={4} className="trend-dot" />
      ))}
      {proj && <circle cx={proj.x} cy={proj.y} r={4} className="trend-dot trend-dot-projected" />}
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

  return (
    <div className="understand-section">
      <h2>What's next</h2>
      <div className={`forecast-card risk-${forecast.risk}`}>
        <div className="forecast-head">
          <span className="risk-badge">{RISK_LABEL[forecast.risk]} risk ahead</span>
          <span className="forecast-trend">Trend: {TREND_LABEL[forecast.trend]}</span>
        </div>
        <div className="forecast-metrics">
          {forecast.predicted_capacity != null && (
            <div className="forecast-metric">
              <span className="forecast-metric-value">{forecast.predicted_capacity}</span>
              <span className="forecast-metric-label">projected tomorrow</span>
            </div>
          )}
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
        </div>
        <p className="forecast-text">{forecast.forecast}</p>
        {forecast.suggestions?.length > 0 && (
          <ul className="risk-suggestions">
            {forecast.suggestions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        )}
      </div>

      <h3 className="trend-heading">Capacity trend (last {forecast.days_of_data} days)</h3>
      <CapacityTrendChart points={forecast.points} predicted={forecast.predicted_capacity} />
      <p className="factor-note">Solid line = your check-ins. Dashed point = projected tomorrow.</p>
    </div>
  )
}
