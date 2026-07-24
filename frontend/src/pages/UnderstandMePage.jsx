import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { CapacitySection } from '../components/CapacitySection'
import { ForecastSection } from '../components/ForecastSection'
import { WhySection } from '../components/WhySection'

// Understand Me = the full read on the caregiver: today's Capacity, the near-term forecast
// with the burnout trend + risk, and why capacity is where it is (factors + emotional tone).
export function UnderstandMePage() {
  const [checkin, setCheckin] = useState(null)
  const [state, setState] = useState('loading') // loading | ready | empty

  useEffect(() => {
    api
      .latestCheckin()
      .then((data) => {
        setCheckin(data)
        setState('ready')
      })
      .catch(() => setState('empty'))
  }, [])

  if (state === 'loading') {
    return (
      <div className="page understand-page">
        <h1>Understand Me</h1>
        <p className="empty">Reading your latest check-in…</p>
      </div>
    )
  }

  if (state === 'empty') {
    return (
      <div className="page understand-page">
        <h1>Understand Me</h1>
        <p className="page-subtitle">Your capacity, where it's heading, and why.</p>
        <p className="empty">
          No check-in yet. <Link to="/checkin">Do a Daily Check-in</Link> and your reading — plus
          the burnout trend and forecast — shows up here.
        </p>
      </div>
    )
  }

  return (
    <div className="page understand-page">
      <h1>Understand Me</h1>
      <p className="page-subtitle">Your capacity, where it's heading, and why.</p>

      <CapacitySection checkin={checkin} />
      <ForecastSection />
      <WhySection checkin={checkin} />
    </div>
  )
}
