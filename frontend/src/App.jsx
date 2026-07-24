import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { api } from './api'
import { Dashboard } from './components/Dashboard'
import { Intervention } from './components/Intervention'
import { Reflection } from './components/Reflection'
import { StressMonitor } from './components/StressMonitor'
import { useStressMonitor } from './hooks/useStressMonitor'

const THRESHOLD_POLL_MS = 15000
// Give a just-finished recovery session room to actually land before checking again —
// otherwise a caregiver whose task load hasn't changed gets re-interrupted immediately.
const POST_SESSION_COOLDOWN_MS = 90000

function App() {
  const [tasks, setTasks] = useState([])
  const [monitoringEnabled, setMonitoringEnabled] = useState(true)
  const [view, setView] = useState('dashboard') // dashboard | intervention | reflection
  const [session, setSession] = useState(null) // { id, reasoning }
  const [reflection, setReflection] = useState(null)
  const cooldownUntilRef = useRef(0)

  const monitor = useStressMonitor({ enabled: monitoringEnabled })

  const refreshTasks = useCallback(() => {
    api.listTasks().then(setTasks).catch(() => {})
  }, [])

  useEffect(() => {
    refreshTasks()
  }, [refreshTasks])

  // The AI brain: while on the dashboard, periodically check whether behavioral load +
  // physiological stress have crossed the intervene threshold.
  useEffect(() => {
    if (view !== 'dashboard') return
    const id = setInterval(async () => {
      if (Date.now() < cooldownUntilRef.current) return
      try {
        const result = await api.checkThreshold()
        if (result.intervene) {
          const started = await api.startSession({
            trigger_score: result.combined_score,
            trigger_reasoning: result.reasoning,
          })
          setSession({ id: started.id, reasoning: result.reasoning })
          setView('intervention')
        }
      } catch {
        // No backend reachable — the caregiver can still use the dashboard normally.
      }
    }, THRESHOLD_POLL_MS)
    return () => clearInterval(id)
  }, [view])

  async function handleCreateTask(task) {
    const created = await api.createTask(task)
    setTasks((prev) => [...prev, created])
  }

  async function handleToggleTask(id) {
    const updated = await api.toggleTask(id)
    setTasks((prev) => prev.map((t) => (t.id === id ? updated : t)))
  }

  async function handleDeleteTask(id) {
    await api.deleteTask(id)
    setTasks((prev) => prev.filter((t) => t.id !== id))
  }

  async function handleInterventionFinished(sessionId) {
    setView('reflection')
    try {
      const result = await api.generateReflection(sessionId)
      setReflection(result)
    } catch {
      setReflection({ message: 'That pause mattered — thank you for taking it.' })
    }
  }

  function handleReturnToDashboard() {
    cooldownUntilRef.current = Date.now() + POST_SESSION_COOLDOWN_MS
    setSession(null)
    setReflection(null)
    setView('dashboard')
    refreshTasks()
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Group-26</h1>
        <p className="app-tagline">Everyone cares for the patient. We watch over the caregiver.</p>
      </header>

      <StressMonitor
        monitor={monitor}
        enabled={monitoringEnabled}
        onToggleEnabled={() => setMonitoringEnabled((v) => !v)}
      />

      {view === 'dashboard' && (
        <Dashboard
          tasks={tasks}
          onCreateTask={handleCreateTask}
          onToggleTask={handleToggleTask}
          onDeleteTask={handleDeleteTask}
        />
      )}

      {view === 'intervention' && session && (
        <Intervention
          sessionId={session.id}
          triggerReasoning={session.reasoning}
          latestStressScore={monitor.latest?.stress_score}
          onFinished={handleInterventionFinished}
        />
      )}

      {view === 'reflection' && (
        <Reflection reflection={reflection} onReturn={handleReturnToDashboard} />
      )}
    </div>
  )
}

export default App
