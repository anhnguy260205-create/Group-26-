import { useEffect, useState } from 'react'
import { api } from '../api'

const REGIONS = ['All', 'Singapore', 'Malaysia']

export function ResourceFinderPage() {
  const [region, setRegion] = useState('All')
  const [resources, setResources] = useState([])

  useEffect(() => {
    api.listResources(region === 'All' ? null : region).then(setResources).catch(() => {})
  }, [region])

  return (
    <div className="page resource-page">
      <h1>Resource Finder</h1>
      <p className="page-subtitle">Local support, region by region.</p>

      <div className="region-tabs">
        {REGIONS.map((r) => (
          <button
            type="button"
            key={r}
            className={`region-tab${region === r ? ' selected' : ''}`}
            onClick={() => setRegion(r)}
          >
            {r}
          </button>
        ))}
      </div>

      <ul className="resource-list">
        {resources.length === 0 && <p className="empty">No resources found for this region.</p>}
        {resources.map((r) => (
          <li key={r.name} className={`resource-card resource-${r.category}`}>
            <div className="resource-header">
              <span className="resource-name">{r.name}</span>
              {r.category === 'crisis' && <span className="resource-crisis-tag">Crisis line</span>}
            </div>
            <p className="resource-description">{r.description}</p>
            <p className="resource-contact">{r.contact}</p>
          </li>
        ))}
      </ul>

      <p className="resource-disclaimer">
        Contact details shown are a starting point — please verify current numbers before relying
        on them in an emergency. If you're in immediate danger, contact local emergency services.
      </p>
    </div>
  )
}
