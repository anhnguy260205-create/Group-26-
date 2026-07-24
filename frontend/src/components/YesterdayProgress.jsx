import { useEffect, useState } from 'react'
import { api } from '../api'

// Progress / Evidence: yesterday's recharge actions vs. today's capacity change.
// The payoff line — "Breathing ✓, Capacity +8" — that makes recovery feel worth it.
export function YesterdayProgress() {
  const [progress, setProgress] = useState(null)
  useEffect(() => {
    api.progress().then(setProgress).catch(() => {})
  }, [])

  if (!progress) return null
  const change = progress.capacity_change

  return (
    <div className="understand-section">
      <h2>Yesterday's improvement</h2>
      <div className={`progress-card${progress.has_evidence ? ' has-evidence' : ''}`}>
        {progress.done_actions.length > 0 && (
          <div className="progress-chips">
            {progress.done_actions.map((a) => (
              <span key={a} className="progress-chip">
                {a} ✓
              </span>
            ))}
            {change != null && (
              <span className={`progress-chip capacity${change > 0 ? ' up' : ''}`}>
                Capacity {change > 0 ? `+${change}` : change}
              </span>
            )}
          </div>
        )}
        <p className="progress-evidence">{progress.evidence}</p>
      </div>
    </div>
  )
}
