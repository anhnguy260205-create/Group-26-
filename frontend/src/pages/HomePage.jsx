import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { CapacitySection } from '../components/CapacitySection'
import { CoordinateCard } from '../components/CoordinateCard'
import { ForecastSection } from '../components/ForecastSection'
import { RechargeCard } from '../components/RechargeCard'
import { WhySection } from '../components/WhySection'
import { YesterdayProgress } from '../components/YesterdayProgress'

// Home = the single-page flow:
// Capacity -> Forecast -> Why -> Recharge & Reconnect -> Coordinate -> Yesterday's improvement.
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
          <CoordinateCard />
          <YesterdayProgress />
        </>
      )}
    </div>
  )
}
