import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useFacePresence } from '../hooks/useFacePresence'
import { Intervention } from './Intervention'
import { PresenceIndicator } from './PresenceIndicator'
import { Reflection } from './Reflection'

const THRESHOLD_POLL_MS = 15000
// Give a just-finished recovery session room to actually land before checking again —
// otherwise a caregiver whose task load hasn't changed gets re-interrupted immediately.
const POST_SESSION_COOLDOWN_MS = 90000

const NAV_ITEMS = [
  { to: '/', label: 'Home', end: true },
  { to: '/checkin', label: 'Check-in' },
  { to: '/understand-me', label: 'Understand Me' },
  { to: '/companion', label: 'AI Copilot' },
  { to: '/progress', label: 'Progress' },
  { to: '/me', label: 'Me' },
]

export function Layout() {
  const location = useLocation()
  const [monitoringEnabled, setMonitoringEnabled] = useState(true)
  const [overlay, setOverlay] = useState('none') // none | intervention | reflection
  const [session, setSession] = useState(null) // { id, reasoning }
  const [reflection, setReflection] = useState(null)
  const cooldownUntilRef = useRef(0)

  const presence = useFacePresence({ enabled: monitoringEnabled })

  // The AI brain: while not already mid-session, periodically check whether behavioral
  // load + physiological stress have crossed the intervene threshold — from any page.
  useEffect(() => {
    if (overlay !== 'none') return
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
          setOverlay('intervention')
        }
      } catch {
        // No backend reachable — the caregiver can still use the app normally.
      }
    }, THRESHOLD_POLL_MS)
    return () => clearInterval(id)
  }, [overlay])

  async function handleInterventionFinished(sessionId) {
    setOverlay('reflection')
    try {
      const result = await api.generateReflection(sessionId)
      setReflection(result)
    } catch {
      setReflection({ message: 'That pause mattered — thank you for taking it.' })
    }
  }

  function handleReturnFromReflection() {
    cooldownUntilRef.current = Date.now() + POST_SESSION_COOLDOWN_MS
    setSession(null)
    setReflection(null)
    setOverlay('none')
  }

  if (overlay === 'intervention' && session) {
    return (
      <Intervention
        sessionId={session.id}
        triggerReasoning={session.reasoning}
        onFinished={handleInterventionFinished}
      />
    )
  }

  if (overlay === 'reflection') {
    return <Reflection reflection={reflection} onReturn={handleReturnFromReflection} />
  }

  return (
    <div className="shell">
      <nav className="sidebar">
        <div className="sidebar-brand">
          <h1>Group-26</h1>
          <p className="app-tagline">We watch over you, not your to-do list.</p>
        </div>
        <ul className="nav-list">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
        <PresenceIndicator
          presence={presence}
          enabled={monitoringEnabled}
          onToggleEnabled={() => setMonitoringEnabled((v) => !v)}
        />
      </nav>
      <main className="content">
        <Outlet />
        {/* Standing footer on every page: family hand-offs and self-care both have a ceiling,
            and the caregiver shouldn't have to go hunting for the door past it. Hidden on the
            resources page itself, and absent from the intervention/reflection overlays above —
            mid-breathing is not the moment to offer someone a link. */}
        {location.pathname !== '/resources' && (
          <p className="outside-help">
            Need outside help? <Link to="/resources">Find support resources</Link>
          </p>
        )}
      </main>
    </div>
  )
}
