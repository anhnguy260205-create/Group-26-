import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

// Coordinate: the "ai agent" that helps hand off care tasks to family. It suggests who to
// ask and drafts the message; you add tasks and assign them here. Links out to Resource
// Finder for outside help.
export function CoordinateCard() {
  const [tasks, setTasks] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [title, setTitle] = useState('')
  const [adding, setAdding] = useState(false)

  function refresh() {
    api.listTasks().then(setTasks).catch(() => {})
    api.suggestDelegation().then(setSuggestions).catch(() => setSuggestions([]))
  }

  useEffect(() => {
    refresh()
  }, [])

  async function addTask(e) {
    e.preventDefault()
    const t = title.trim()
    if (!t || adding) return
    setAdding(true)
    try {
      await api.createTask({ title: t, kind: 'todo', due_at: null })
      setTitle('')
      refresh()
    } finally {
      setAdding(false)
    }
  }

  async function handOff(taskId, member) {
    try {
      await api.assignTask(taskId, member)
      refresh()
    } catch {
      // ignore
    }
  }

  const pending = tasks.filter((t) => !t.done && !t.assigned_to)
  const assigned = tasks.filter((t) => t.assigned_to)

  return (
    <div className="understand-section">
      <h2>Coordinate</h2>
      <p className="section-sub">Hand off what you can — I'll suggest who to ask and word it for you.</p>

      <form className="coordinate-add" onSubmit={addTask}>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Add a care task to share…"
        />
        <button type="submit" disabled={adding || !title.trim()}>
          Add
        </button>
      </form>

      {suggestions.length > 0 && (
        <div className="coordinate-suggestions">
          {suggestions.map((s) => (
            <div key={s.task_id} className="coordinate-suggestion">
              <div className="coordinate-task">{s.title}</div>
              <p className="coordinate-message">“{s.message}”</p>
              <button type="button" onClick={() => handOff(s.task_id, s.suggested_to)}>
                Hand off to {s.suggested_to}
              </button>
            </div>
          ))}
        </div>
      )}

      {suggestions.length === 0 && pending.length === 0 && (
        <p className="empty">Nothing to coordinate right now.</p>
      )}

      {assigned.length > 0 && (
        <ul className="coordinate-assigned">
          {assigned.map((t) => (
            <li key={t.id}>
              <span className="coordinate-task">{t.title}</span>
              <span className="coordinate-assigned-to">→ {t.assigned_to}</span>
              <button type="button" className="link-button" onClick={() => handOff(t.id, null)}>
                take back
              </button>
            </li>
          ))}
        </ul>
      )}

      <p className="coordinate-outside">
        Need outside help? <Link to="/resources">Find support resources</Link>
      </p>
    </div>
  )
}
