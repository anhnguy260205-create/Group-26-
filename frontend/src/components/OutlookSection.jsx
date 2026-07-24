import { useEffect, useState } from 'react'
import { api } from '../api'

const RISK_LABEL = { low: 'Low', moderate: 'Moderate', high: 'High' }

// Outlook = the prediction: WHY the state has stayed low (causes) and what CONTINUING the
// pattern tends to lead to (consequences). Supportive, non-clinical.
export function OutlookSection() {
  const [outlook, setOutlook] = useState(null)

  useEffect(() => {
    api.capacityOutlook().then(setOutlook).catch(() => {})
  }, [])

  if (!outlook) return null

  return (
    <div className="understand-section">
      <div className="outlook-head">
        <h2>Prediction</h2>
        <span className={`risk-badge risk-${outlook.risk}`}>{RISK_LABEL[outlook.risk]} risk</span>
      </div>

      <div className={`outlook-card risk-${outlook.risk}`}>
        <div className="outlook-block">
          <h3>Why this is happening</h3>
          <p>{outlook.causes}</p>
        </div>
        <div className="outlook-block">
          <h3>If nothing changes</h3>
          <p>{outlook.consequences}</p>
        </div>
      </div>

      <p className="factor-note">
        A supportive prediction from your recent pattern — not a diagnosis or a medical forecast.
      </p>
    </div>
  )
}
