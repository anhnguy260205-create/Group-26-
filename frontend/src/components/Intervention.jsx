import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'

const PACE_REFRESH_MS = 5000
const MIN_SESSION_MS = 45000
const MAX_SESSION_MS = 180000
const RELIEF_STRESS_SCORE = 0.5

const PHASE_LABEL = { inhale: 'Breathe in', hold: 'Hold', exhale: 'Breathe out' }

export function Intervention({ sessionId, triggerReasoning, latestStressScore, onFinished }) {
  const [pace, setPace] = useState({
    inhale_seconds: 4,
    hold_seconds: 4,
    exhale_seconds: 4,
    guidance: 'Let’s take a moment together.',
  })
  const [phase, setPhase] = useState('inhale')
  const startRef = useRef(Date.now())
  const endingRef = useRef(false)

  // Keep the pace synced to real-time stress — the AI adjusts rhythm mid-session.
  useEffect(() => {
    let cancelled = false
    async function refresh() {
      try {
        const next = await api.getPace(sessionId)
        if (!cancelled) setPace(next)
      } catch {
        // Keep the last known pace if the backend is briefly unreachable.
      }
    }
    refresh()
    const id = setInterval(refresh, PACE_REFRESH_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [sessionId])

  // Cycle inhale -> hold -> exhale -> inhale, driven by the current pace.
  useEffect(() => {
    const durations = {
      inhale: pace.inhale_seconds * 1000,
      hold: pace.hold_seconds * 1000,
      exhale: pace.exhale_seconds * 1000,
    }
    const order = ['inhale', 'hold', 'exhale']
    const timer = setTimeout(() => {
      const next = order[(order.indexOf(phase) + 1) % order.length]
      setPhase(next)
    }, durations[phase])
    return () => clearTimeout(timer)
  }, [phase, pace])

  const finish = useCallback(async () => {
    if (endingRef.current) return
    endingRef.current = true
    try {
      await api.endSession(sessionId)
    } finally {
      onFinished(sessionId)
    }
  }, [sessionId, onFinished])

  // Auto-end once the caregiver has genuinely settled, with a hard safety cap either way.
  useEffect(() => {
    const id = setInterval(() => {
      const elapsed = Date.now() - startRef.current
      const settled = latestStressScore != null && latestStressScore < RELIEF_STRESS_SCORE
      if ((elapsed >= MIN_SESSION_MS && settled) || elapsed >= MAX_SESSION_MS) {
        finish()
      }
    }, 2000)
    return () => clearInterval(id)
  }, [latestStressScore, finish])

  const scale = phase === 'inhale' ? 1.35 : phase === 'exhale' ? 0.85 : 1.1
  const duration = { inhale: pace.inhale_seconds, hold: pace.hold_seconds, exhale: pace.exhale_seconds }[phase]

  return (
    <div className="intervention-overlay">
      <p className="intervention-reasoning">{triggerReasoning}</p>
      <div className="breathing-ring">
        <div
          className="breathing-circle"
          style={{ transform: `scale(${scale})`, transitionDuration: `${duration}s` }}
        />
      </div>
      <p className="breathing-phase">{PHASE_LABEL[phase]}</p>
      <p className="breathing-guidance">{pace.guidance}</p>
      {pace.guidance_source === 'llm' && (
        <p className="breathing-guidance-tag">AI-adjusted</p>
      )}
      <button type="button" className="link-button" onClick={finish}>
        End session
      </button>
    </div>
  )
}

