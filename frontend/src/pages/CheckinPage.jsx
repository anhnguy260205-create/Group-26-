import { useEffect, useState } from 'react'
import { api } from '../api'

const MOODS = [
  { value: 1, emoji: '😀', label: 'Good' },
  { value: 2, emoji: '🙂', label: 'Okay' },
  { value: 3, emoji: '😔', label: 'Drained' },
  { value: 4, emoji: '😭', label: 'Barely holding on' },
]

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function CheckinPage() {
  const [mood, setMood] = useState(null)
  const [hoursSlept, setHoursSlept] = useState('')
  const [careHours, setCareHours] = useState('')
  const [hadMeTime, setHadMeTime] = useState(null)
  const [result, setResult] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const [entries, setEntries] = useState([])
  const [journalText, setJournalText] = useState('')
  const [summary, setSummary] = useState(null)
  const [journalSubmitting, setJournalSubmitting] = useState(false)

  const canSubmit = mood != null && hoursSlept !== '' && careHours !== '' && hadMeTime != null

  function refreshJournal() {
    api.listJournal().then(setEntries).catch(() => {})
    api.journalSummary().then(setSummary).catch(() => {})
  }

  useEffect(() => {
    refreshJournal()
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!canSubmit) return
    setSubmitting(true)
    try {
      const res = await api.submitCheckin({
        mood,
        hours_slept: Number(hoursSlept),
        care_hours: Number(careHours),
        had_me_time: hadMeTime,
      })
      setResult(res)
    } finally {
      setSubmitting(false)
    }
  }

  function startOver() {
    setResult(null)
    setMood(null)
    setHoursSlept('')
    setCareHours('')
    setHadMeTime(null)
  }

  async function handleJournalSubmit(e) {
    e.preventDefault()
    const trimmed = journalText.trim()
    if (!trimmed || journalSubmitting) return
    setJournalSubmitting(true)
    try {
      await api.createJournalEntry({ text: trimmed })
      setJournalText('')
      refreshJournal()
    } finally {
      setJournalSubmitting(false)
    }
  }

  if (result) {
    return (
      <div className="page checkin-page">
        <h1>Thanks for checking in</h1>
        <div className="checkin-result">
          <div className="checkin-score">{result.stress_score_display}</div>
          <p className="checkin-score-label">today's stress score (0-100)</p>
        </div>
        <p className="checkin-note">
          This is a support tool, not a diagnosis — just a way to notice how things are trending.
        </p>
        <button type="button" onClick={startOver}>
          Check in again
        </button>
      </div>
    )
  }

  return (
    <div className="page checkin-page">
      <h1>Daily Check-in</h1>
      <p className="page-subtitle">One minute a day — how are you doing right now?</p>

      <form onSubmit={handleSubmit} className="checkin-form">
        <fieldset>
          <legend>Mood</legend>
          <div className="mood-picker">
            {MOODS.map((m) => (
              <button
                type="button"
                key={m.value}
                className={`mood-option${mood === m.value ? ' selected' : ''}`}
                onClick={() => setMood(m.value)}
              >
                <span className="mood-emoji">{m.emoji}</span>
                <span className="mood-label">{m.label}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <label className="field">
          Hours slept last night
          <input
            type="number"
            min="0"
            max="24"
            step="0.5"
            value={hoursSlept}
            onChange={(e) => setHoursSlept(e.target.value)}
            placeholder="e.g. 6"
          />
        </label>

        <label className="field">
          Hours spent caregiving today
          <input
            type="number"
            min="0"
            max="24"
            step="0.5"
            value={careHours}
            onChange={(e) => setCareHours(e.target.value)}
            placeholder="e.g. 8"
          />
        </label>

        <fieldset>
          <legend>Did you get any time for yourself today?</legend>
          <div className="toggle-row">
            <button
              type="button"
              className={`toggle-option${hadMeTime === true ? ' selected' : ''}`}
              onClick={() => setHadMeTime(true)}
            >
              Yes
            </button>
            <button
              type="button"
              className={`toggle-option${hadMeTime === false ? ' selected' : ''}`}
              onClick={() => setHadMeTime(false)}
            >
              No
            </button>
          </div>
        </fieldset>

        <button type="submit" disabled={!canSubmit || submitting}>
          {submitting ? 'Submitting…' : 'Submit check-in'}
        </button>
      </form>
      <br />
      <h1>Journal</h1>
      <p className="page-subtitle">One line a day — what happened today?</p>

      <form onSubmit={handleJournalSubmit} className="journal-form">
        <input
          type="text"
          value={journalText}
          onChange={(e) => setJournalText(e.target.value)}
          placeholder="Today was..."
          maxLength={500}
        />
        <button type="submit" disabled={journalSubmitting || !journalText.trim()}>
          Add entry
        </button>
      </form>

      {summary && (
        <div className="journal-summary">
          <h2>Pattern across recent entries</h2>
          <p>{summary.summary}</p>
        </div>
      )}

      <ul className="journal-list">
        {entries.length === 0 && <p className="empty">No entries yet.</p>}
        {entries.map((e) => (
          <li key={e.id} className="journal-entry">
            <span className="journal-date">{formatDate(e.created_at)}</span>
            <span className="journal-text">{e.text}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
