import { useEffect, useState } from 'react'
import { api } from '../api'

const RISK_LABEL = { low: 'Low', moderate: 'Moderate', high: 'High' }

function TrendChart({ points }) {
  if (points.length === 0) return <p className="empty">Not enough data yet — check in daily to build a trend.</p>

  const width = 560
  const height = 160
  const padding = 24
  const maxScore = 1

  const coords = points.map((p, i) => {
    const x = padding + (i / Math.max(points.length - 1, 1)) * (width - padding * 2)
    const y = height - padding - (p.avg_stress_score / maxScore) * (height - padding * 2)
    return { x, y, ...p }
  })
  const path = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x} ${c.y}`).join(' ')

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label="Stress trend over time">
      <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} className="trend-axis" />
      <path d={path} className="trend-line" fill="none" />
      {coords.map((c) => (
        <circle key={c.date} cx={c.x} cy={c.y} r={4} className="trend-dot" />
      ))}
    </svg>
  )
}

const EMOTION_BARS = [
  { key: 'happy', label: 'Happy / content', className: 'emotion-happy' },
  { key: 'sad', label: 'Sad', className: 'emotion-sad' },
  { key: 'low_mood', label: 'Low mood / heaviness', className: 'emotion-low-mood' },
]

function EmotionalTrends({ emotions }) {
  if (!emotions) return null

  if (emotions.entry_count === 0 || emotions.source === 'unavailable') {
    return <p className="empty">{emotions.summary}</p>
  }

  return (
    <>
      <div className="emotion-bars">
        {EMOTION_BARS.map((bar) => (
          <div key={bar.key} className="emotion-bar-row">
            <span className="emotion-bar-label">{bar.label}</span>
            <span className="emotion-bar-track">
              <span
                className={`emotion-bar-fill ${bar.className}`}
                style={{ width: `${emotions[bar.key]}%` }}
              />
            </span>
            <span className="emotion-bar-value">{emotions[bar.key]}</span>
          </div>
        ))}
      </div>
      <p className="emotion-summary">{emotions.summary}</p>
    </>
  )
}

const REFRESH_INTERVAL_MS = 15000

export function BurnoutDashboardPage() {
  const [trends, setTrends] = useState([])
  const [risk, setRisk] = useState(null)
  const [emotions, setEmotions] = useState(null)

  useEffect(() => {
    function refresh() {
      api.stressTrends(14).then(setTrends).catch(() => {})
      api.burnoutRisk(7).then(setRisk).catch(() => {})
      api.journalEmotions().then(setEmotions).catch(() => {})
    }
    // The camera sensor and check-ins post new readings in the background while this page
    // sits open — poll so the numbers actually move without a manual reload.
    refresh()
    const id = setInterval(refresh, REFRESH_INTERVAL_MS)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="page burnout-page">
      <h1>Burnout Dashboard</h1>
      <p className="page-subtitle">A current-state read from your recent check-ins — not a diagnosis.</p>

      {risk && (
        <div className={`risk-card risk-${risk.level}`}>
          <div className="risk-level">
            <span className="risk-badge">{RISK_LABEL[risk.level]} risk</span>
            {risk.avg_stress_score != null && (
              <span className="risk-avg">avg stress {Math.round(risk.avg_stress_score * 100)}/100</span>
            )}
          </div>
          <p className="risk-basis">Based on {risk.days_of_data} day{risk.days_of_data === 1 ? '' : 's'} of recent data.</p>
          <ul className="risk-suggestions">
            {risk.suggestions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      <section>
        <h2>Stress trend (last 14 days)</h2>
        <TrendChart points={trends} />
      </section>

      <section>
        <h2>Emotional tone (from your journal)</h2>
        <p className="emotion-disclaimer">
          A descriptive read of tone in your recent entries — not a diagnosis of any kind.
        </p>
        <EmotionalTrends emotions={emotions} />
      </section>
    </div>
  )
}
