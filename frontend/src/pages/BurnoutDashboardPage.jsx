import { useEffect, useState } from 'react'
import { api } from '../api'

const RISK_LABEL = { low: 'Low', moderate: 'Moderate', high: 'High' }
const TREND_LABEL = { rising: 'Rising', falling: 'Easing', steady: 'Steady' }
const ARROW = { up: '↑', down: '↓', flat: '→' }

// History (avg_stress_score) + forecast (predicted_score) drawn on one 0-1 axis,
// with the forecast segment dashed and a shaded confidence band.
function ForecastChart({ history, forecast }) {
  const hist = history.map((p) => ({ v: p.avg_stress_score, kind: 'hist' }))
  const fut = forecast.map((p) => ({ v: p.predicted_score, lower: p.lower, upper: p.upper, kind: 'fut' }))
  const all = [...hist, ...fut]
  if (all.length < 2) return <p className="empty">Not enough data yet — check in daily to build the forecast.</p>

  const width = 560
  const height = 170
  const pad = 24
  const x = (i) => pad + (i / Math.max(all.length - 1, 1)) * (width - pad * 2)
  const y = (v) => height - pad - v * (height - pad * 2)

  const histCoords = hist.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(p.v)}`).join(' ')
  const joinIdx = hist.length - 1
  const futCoords = fut
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(joinIdx + 1 + i)} ${y(p.v)}`)
    .join(' ')
  // Connector from last history point into the forecast.
  const connector =
    hist.length && fut.length
      ? `M ${x(joinIdx)} ${y(hist[joinIdx].v)} L ${x(joinIdx + 1)} ${y(fut[0].v)}`
      : ''
  const bandPath =
    fut.length >= 1
      ? [
          ...fut.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(joinIdx + 1 + i)} ${y(p.upper)}`),
          ...fut.map((p, i) => `L ${x(joinIdx + 1 + (fut.length - 1 - i))} ${y(fut[fut.length - 1 - i].lower)}`),
          'Z',
        ].join(' ')
      : ''

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="trend-chart" role="img" aria-label="Stress history and forecast">
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} className="trend-axis" />
      {bandPath && <path d={bandPath} fill="rgba(220,80,80,0.12)" stroke="none" />}
      <path d={histCoords} className="trend-line" fill="none" />
      {connector && <path d={connector} className="trend-line" fill="none" strokeDasharray="5 4" opacity="0.7" />}
      {futCoords && <path d={futCoords} className="trend-line" fill="none" strokeDasharray="5 4" opacity="0.7" />}
      {hist.map((p, i) => (
        <circle key={`h${i}`} cx={x(i)} cy={y(p.v)} r={4} className="trend-dot" />
      ))}
      {fut.map((p, i) => (
        <circle key={`f${i}`} cx={x(joinIdx + 1 + i)} cy={y(p.v)} r={4} className="trend-dot" fill="#c85050" />
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
      <p className="page-subtitle">A read from your recent check-ins — support and signposting, not a diagnosis.</p>

      {forecast && (
        <div className={`twin-card twin-${forecast.trend}`}>
          <div className="twin-head">
            <span className="twin-badge">Digital Twin · {TREND_LABEL[forecast.trend]}</span>
            {forecast.main_driver && <span className="twin-driver">driver: {forecast.main_driver}</span>}
          </div>
          <p className="twin-narrative">{forecast.narrative}</p>
          <ForecastChart history={trends} forecast={forecast.points} />
          {forecast.days_of_history < 3 && (
            <p className="twin-note">Seed a few days of check-ins to unlock the forecast.</p>
          )}
        </div>
      )}

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

      {weekly && (
        <section className="weekly-card">
          <h2>This week</h2>
          <p className="weekly-metrics">
            Sleep {ARROW[weekly.sleep_trend]} · Stress {ARROW[weekly.stress_trend]} · Mood {ARROW[weekly.mood_trend]}
          </p>
          <p className="weekly-summary">{weekly.summary}</p>
        </section>
      )}

      <section>
        <h2>Stress trend (last 14 days)</h2>
        <ForecastChart history={trends} forecast={[]} />
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
