export function capacityBand(score) {
  if (score < 40) return { label: 'Running low', tone: 'low' }
  if (score < 70) return { label: 'Holding steady', tone: 'mid' }
  return { label: 'In a good place', tone: 'high' }
}

// Capacity gauge + band + main driver. Pure render — parent supplies the check-in.
export function CapacitySection({ checkin }) {
  if (!checkin) return null
  const b = capacityBand(checkin.capacity_score)
  return (
    <div className="understand-section">
      <div className={`capacity-card tone-${b.tone}`}>
        <div className="capacity-gauge">
          <div className="capacity-score">{checkin.capacity_score}</div>
          <p className="capacity-score-label">capacity (0-100)</p>
        </div>
        <div className="capacity-band">{b.label}</div>
      </div>
      <div className="capacity-driver">
        <span className="capacity-driver-tag">Main driver</span>
        <strong>{checkin.main_driver}</strong>
      </div>
    </div>
  )
}
