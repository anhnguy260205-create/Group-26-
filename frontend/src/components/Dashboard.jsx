import { useState } from 'react'

const KIND_LABEL = { medication: 'Medication', appointment: 'Appointment', todo: 'To-do' }

function formatDue(due_at) {
  if (!due_at) return null
  const d = new Date(due_at)
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function dueStatus(task) {
  if (!task.due_at || task.done) return null
  return new Date(task.due_at) < new Date() ? 'overdue' : 'upcoming'
}

export function Dashboard({ tasks, onCreateTask, onToggleTask, onDeleteTask }) {
  const [title, setTitle] = useState('')
  const [kind, setKind] = useState('todo')
  const [dueAt, setDueAt] = useState('')

  const pending = tasks.filter((t) => !t.done)
  const done = tasks.filter((t) => t.done)

  function handleSubmit(e) {
    e.preventDefault()
    if (!title.trim()) return
    onCreateTask({ title: title.trim(), kind, due_at: dueAt ? new Date(dueAt).toISOString() : null })
    setTitle('')
    setDueAt('')
  }

  return (
    <div className="dashboard">
      <h1>Care Dashboard</h1>

      <form className="task-form" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Add medication, appointment, or to-do…"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="todo">To-do</option>
          <option value="medication">Medication</option>
          <option value="appointment">Appointment</option>
        </select>
        <input type="datetime-local" value={dueAt} onChange={(e) => setDueAt(e.target.value)} />
        <button type="submit">Add</button>
      </form>

      <section>
        <h2>Today ({pending.length})</h2>
        {pending.length === 0 && <p className="empty">Nothing pending — nice.</p>}
        <ul className="task-list">
          {pending.map((task) => {
            const status = dueStatus(task)
            return (
              <li key={task.id} className="task-item">
                <label>
                  <input type="checkbox" checked={task.done} onChange={() => onToggleTask(task.id)} />
                  <span className="task-kind">{KIND_LABEL[task.kind]}</span>
                  <span className="task-title">{task.title}</span>
                  {task.due_at && <span className="task-due">{formatDue(task.due_at)}</span>}
                  {status && (
                    <span className={`due-tag due-tag-${status}`}>
                      {status === 'overdue' ? 'Overdue' : 'Upcoming'}
                    </span>
                  )}
                </label>
                <button type="button" className="link-button" onClick={() => onDeleteTask(task.id)}>
                  remove
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      {done.length > 0 && (
        <section>
          <h2>Done ({done.length})</h2>
          <ul className="task-list done">
            {done.map((task) => (
              <li key={task.id} className="task-item">
                <label>
                  <input type="checkbox" checked={task.done} onChange={() => onToggleTask(task.id)} />
                  <span className="task-title">{task.title}</span>
                </label>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
