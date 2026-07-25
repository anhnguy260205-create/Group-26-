import { useEffect, useState } from 'react'
import { api } from '../api'

// Recharge & Reconnect: today's recovery actions picked from the capacity driver.
// Each can be marked Done or Skip; state persists on the backend for Progress to read.
export function RechargeCard() {
  const [actions, setActions] = useState(null)
  const [busy, setBusy] = useState(null)

  useEffect(() => {
    api.rechargeToday().then(setActions).catch(() => setActions([]))
  }, [])

  async function update(id, status) {
    setBusy(id)
    try {
      const updated = await api.setRechargeStatus(id, status)
      setActions((prev) => prev.map((a) => (a.id === id ? updated : a)))
    } catch {
      // leave as-is
    } finally {
      setBusy(null)
    }
  }

  if (!actions) return null

  // Every action in a day's plan shares the same reasoning (it comes from the same cause),
  // so it's shown once above the list rather than repeated on each row.
  const why = actions.find((a) => a.why)?.why

  return (
    <div className="understand-section">
      <h2>Recharge &amp; Reconnect</h2>
      {why && <p className="recharge-why">{why}</p>}
      {actions.length === 0 ? (
        <p className="empty">Do a check-in and I'll suggest a recovery action here.</p>
      ) : (
        <div className="recharge-list">
          {actions.map((a) => (
            <div key={a.id} className={`recharge-item status-${a.status}`}>
              <div className="recharge-body">
                <span className="recharge-label">
                  {a.label}
                  {a.reconnect && <span className="recharge-tag">reconnect</span>}
                </span>
                <span className="recharge-detail">{a.detail}</span>
                {a.driver && (
                  <span className="recharge-because">Chosen because your main driver today is {a.driver.toLowerCase()}</span>
                )}
              </div>
              {a.status === 'pending' ? (
                <div className="recharge-actions">
                  <button type="button" disabled={busy === a.id} onClick={() => update(a.id, 'done')}>
                    Done
                  </button>
                  <button type="button" className="ghost" disabled={busy === a.id} onClick={() => update(a.id, 'skipped')}>
                    Skip
                  </button>
                </div>
              ) : (
                <span className={`recharge-status-tag ${a.status}`}>
                  {a.status === 'done' ? '✓ Done' : 'Skipped'}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
