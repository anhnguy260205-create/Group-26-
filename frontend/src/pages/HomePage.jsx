import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { CapacitySection } from '../components/CapacitySection'
import { ForecastSection } from '../components/ForecastSection'
import { RechargeCard } from '../components/RechargeCard'
import { WhySection } from '../components/WhySection'
import { YesterdayProgress } from '../components/YesterdayProgress'

// Home = the single-page flow:
// Capacity -> Forecast -> Why -> Recharge & Reconnect -> Yesterday's improvement.
//
// Coordinate (task hand-off) is no longer rendered anywhere: a to-do list works against a
// burnout app, since it makes the load countable and never empties. The component and its
// endpoints (/tasks, /delegation/suggest) are untouched, and seeded tasks still feed
// scoring.behavioral_score(), which the intervention threshold reads — so task load remains a
// background stress signal even though the caregiver is no longer asked to maintain a list.
//
// The one piece kept from that card is the route out to external support, which now lives in
// Layout as a standing footer on every page rather than only here.
export function HomePage() {
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

  return (
    <div className="page home-page">
      <h1>Today</h1>

      {state === 'empty' && (
        <p className="empty">
          Start with a <Link to="/checkin">Daily Check-in</Link> — your capacity, forecast, and
          recovery plan build from it.
        </p>
      )}

      {state === 'ready' && (
        <>
          <CapacitySection checkin={checkin} />
          <ForecastSection />
          <WhySection checkin={checkin} />
          <RechargeCard />
          <YesterdayProgress />
        </>
      )}
    </div>
  )
}
