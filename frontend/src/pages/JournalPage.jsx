import { useEffect, useState } from 'react'
import { api } from '../api'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function JournalPage() {
  const [entries, setEntries] = useState([])
  const [text, setText] = useState('')
  const [summary, setSummary] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  function refresh() {
    api.listJournal().then(setEntries).catch(() => {})
    api.journalSummary().then(setSummary).catch(() => {})
  }

  useEffect(() => {
    refresh()
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || submitting) return
    setSubmitting(true)
    try {
      await api.createJournalEntry({ text: trimmed })
      setText('')
      refresh()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page journal-page">
      <h1>Journal</h1>
      <p className="page-subtitle">One line a day — what happened today?</p>

      <form onSubmit={handleSubmit} className="journal-form">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Today was..."
          maxLength={500}
        />
        <button type="submit" disabled={submitting || !text.trim()}>
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
