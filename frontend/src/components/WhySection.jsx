const BASE_FACTORS = [
  { key: 'mood', label: 'Mood' },
  { key: 'sleep', label: 'Sleep' },
  { key: 'energy', label: 'Energy' },
  { key: 'night_care', label: 'Night Care' },
  { key: 'free_time', label: 'Free Time' },
]

function factorRows(checkin) {
  const rows = BASE_FACTORS.map((f) => ({ ...f, value: checkin[f.key] }))
  if (checkin.face_stress != null) {
    rows.push({ key: 'face', label: 'Facial Signs', value: Math.round((1 - checkin.face_stress) * 10) })
  }
  return rows
}

// Why capacity is where it is: reason + factor breakdown + journal.
export function WhySection({ checkin }) {
  if (!checkin) return null
  return (
    <div className="understand-section">
      <h2>Why</h2>
      <p className="understand-reason">{checkin.reason}</p>

      <div className="factor-bars">
        {factorRows(checkin).map((f) => {
          const isDriver = f.label === checkin.main_driver
          return (
            <div className={`factor-bar${isDriver ? ' driver' : ''}`} key={f.key}>
              <span className="factor-label">{f.label}</span>
              <span className="factor-track">
                <span className="factor-fill" style={{ width: `${f.value * 10}%` }} />
              </span>
              <span className="factor-value">{f.value}</span>
            </div>
          )
        })}
      </div>
      {checkin.face_stress != null && (
        <p className="factor-note">
          Facial Signs came from your camera at check-in — a calm face reads high, a tense face reads low.
        </p>
      )}
      {checkin.journal && <blockquote className="understand-journal">“{checkin.journal}”</blockquote>}
    </div>
  )
}
