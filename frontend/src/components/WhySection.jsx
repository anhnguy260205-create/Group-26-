import { useEffect, useState } from 'react'
import { api } from '../api'

const BASE_FACTORS = [
  { key: 'mood', label: 'Mood' },
  { key: 'sleep', label: 'Sleep' },
  { key: 'energy', label: 'Energy' },
  { key: 'night_care', label: 'Night Care' },
  { key: 'free_time', label: 'Free Time' },
]

const EMOTION_BARS = [
  { key: 'happy', label: 'Happy / content', className: 'emotion-happy' },
  { key: 'sad', label: 'Sad', className: 'emotion-sad' },
  { key: 'low_mood', label: 'Low mood / heaviness', className: 'emotion-low-mood' },
]

function factorRows(checkin) {
  const rows = BASE_FACTORS.map((f) => ({ ...f, value: checkin[f.key] }))
  if (checkin.face_stress != null) {
    rows.push({ key: 'face', label: 'Facial Signs', value: Math.round((1 - checkin.face_stress) * 10) })
  }
  return rows
}

// Why capacity is where it is: reason + factor breakdown + journal + emotional tone.
export function WhySection({ checkin }) {
  const [emotions, setEmotions] = useState(null)
  useEffect(() => {
    api.journalEmotions().then(setEmotions).catch(() => {})
  }, [])

  if (!checkin) return null

  return (
    <div className="understand-section">
      <h2>Why</h2>
      <p className="understand-reason">{checkin.reason}</p>

      <div className="factor-bars">
        {factorRows(checkin).map((f) => {
          const isDriver = f.label === checkin.main_driver
          return (
            <div className={`factor-bar${isDriver ? ' driver' : ''}`} key={f.key}>
              <span className="factor-label">{f.label}</span>
              <span className="factor-track">
                <span className="factor-fill" style={{ width: `${f.value * 10}%` }} />
              </span>
              <span className="factor-value">{f.value}</span>
            </div>
          )
        })}
      </div>
      {checkin.face_stress != null && (
        <p className="factor-note">
          Facial Signs came from your camera at check-in — a calm face reads high, a tense face reads low.
        </p>
      )}
      {checkin.journal && <blockquote className="understand-journal">“{checkin.journal}”</blockquote>}

      {emotions && emotions.entry_count > 0 && emotions.source !== 'unavailable' && (
        <div className="emotion-block">
          <h3 className="trend-heading">Emotional tone (from your journal)</h3>
          <div className="emotion-bars">
            {EMOTION_BARS.map((bar) => (
              <div key={bar.key} className="emotion-bar-row">
                <span className="emotion-bar-label">{bar.label}</span>
                <span className="emotion-bar-track">
                  <span className={`emotion-bar-fill ${bar.className}`} style={{ width: `${emotions[bar.key]}%` }} />
                </span>
                <span className="emotion-bar-value">{emotions[bar.key]}</span>
              </div>
            ))}
          </div>
          <p className="emotion-summary">{emotions.summary}</p>
        </div>
      )}
    </div>
  )
}
