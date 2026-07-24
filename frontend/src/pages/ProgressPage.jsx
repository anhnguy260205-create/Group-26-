import { ForecastSection } from '../components/ForecastSection'
import { YesterdayProgress } from '../components/YesterdayProgress'

// Progress = the evidence that recovery works: yesterday's actions vs. today's capacity,
// plus the longer trend so improvement is visible over days.
export function ProgressPage() {
  return (
    <div className="page progress-page">
      <h1>Progress</h1>
      <p className="page-subtitle">Proof that recharging adds up — day by day.</p>
      <YesterdayProgress />
      <ForecastSection />
    </div>
  )
}
