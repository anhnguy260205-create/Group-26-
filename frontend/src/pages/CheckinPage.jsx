import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

// Each slider is 0-10. Endpoint labels frame what low vs high means so the numbers
// stay meaningful without a legend.
const SLIDERS = [
  { key: 'mood', label: 'Mood', low: 'Terrible', high: 'Great' },
  { key: 'sleep', label: 'Sleep', low: 'No rest', high: 'Fully rested' },
  { key: 'energy', label: 'Energy', low: 'Depleted', high: 'Energized' },
  { key: 'night_care', label: 'Night Care', low: 'None', high: 'Heavy' },
  { key: 'free_time', label: 'Free Time', low: 'None', high: 'Plenty' },
]

const DEFAULTS = { mood: 5, sleep: 5, energy: 5, night_care: 0, free_time: 5 }

export function CheckinPage() {
  const navigate = useNavigate()
  const [journal, setJournal] = useState('')
  const [sliders, setSliders] = useState(DEFAULTS)
  const [result, setResult] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  function setSlider(key, value) {
    setSliders((prev) => ({ ...prev, [key]: Number(value) }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await api.submitCheckin({ journal: journal.trim(), ...sliders })
      setResult(res)
    } catch (err) {
      // Surface failures instead of silently doing nothing — a 500 here usually means the
      // backend DB is missing a newer column (run backend/migrate.py or delete app.db).
      setError(
        "Couldn't save your check-in — the backend rejected it. Check that the server is " +
          'running and its database is up to date.'
      )
      // eslint-disable-next-line no-console
      console.error('submitCheckin failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  function startOver() {
    setResult(null)
    setJournal('')
    setSliders(DEFAULTS)
    setError(null)
  }

  if (result) {
    return (
      <div className="page checkin-page">
        <h1>Thanks for checking in</h1>
        <div className="capacity-result">
          <div className="capacity-score">{result.capacity_score}</div>
          <p className="capacity-score-label">today's capacity (0-100)</p>
        </div>
        <div className="capacity-driver">
          <span className="capacity-driver-tag">Main driver</span>
          <strong>{result.main_driver}</strong>
        </div>
        <p className="capacity-reason">{result.reason}</p>
        <p className="checkin-note">
          A support tool, not a diagnosis — just a way to notice how things are trending.
        </p>
        <div className="capacity-actions">
          <button type="button" onClick={() => navigate('/understand-me')}>
            Understand me
          </button>
          <button type="button" className="ghost" onClick={startOver}>
            Check in again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page checkin-page">
      <h1>Daily Check-in</h1>
      <p className="page-subtitle">One minute a day — how are you doing right now?</p>

      <form onSubmit={handleSubmit} className="checkin-form">
        <label className="field">
          Journal — what happened today?
          <textarea
            value={journal}
            onChange={(e) => setJournal(e.target.value)}
            placeholder="Today was..."
            maxLength={500}
            rows={3}
          />
        </label>

        <div className="slider-group">
          {SLIDERS.map((s) => (
            <div className="slider-field" key={s.key}>
              <div className="slider-head">
                <span className="slider-label">{s.label}</span>
                <span className="slider-value">{sliders[s.key]}</span>
              </div>
              <input
                type="range"
                min="0"
                max="10"
                step="1"
                value={sliders[s.key]}
                onChange={(e) => setSlider(s.key, e.target.value)}
              />
              <div className="slider-scale">
                <span>{s.low}</span>
                <span>{s.high}</span>
              </div>
            </div>
          ))}
        </div>

        <button type="submit" disabled={submitting}>
          {submitting ? 'Scoring…' : 'Submit check-in'}
        </button>

        {error && <p className="checkin-error">{error}</p>}
      </form>
    </div>
  )
}
