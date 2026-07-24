import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const STORAGE_KEY = 'group26.profile'
const EMPTY = { name: '', caringFor: '', region: '' }

function loadProfile() {
  try {
    return { ...EMPTY, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') }
  } catch {
    return { ...EMPTY }
  }
}

// Me = a light profile / settings page. Preferences persist locally in the browser.
export function MePage() {
  const [profile, setProfile] = useState(EMPTY)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setProfile(loadProfile())
  }, [])

  function set(field, value) {
    setProfile((p) => ({ ...p, [field]: value }))
    setSaved(false)
  }

  function save(e) {
    e.preventDefault()
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile))
    setSaved(true)
  }

  return (
    <div className="page me-page">
      <h1>Me</h1>
      <p className="page-subtitle">Your profile and settings.</p>

      <form className="me-form" onSubmit={save}>
        <label className="field">
          Your name
          <input type="text" value={profile.name} onChange={(e) => set('name', e.target.value)} placeholder="e.g. Hong" />
        </label>
        <label className="field">
          Who you're caring for
          <input type="text" value={profile.caringFor} onChange={(e) => set('caringFor', e.target.value)} placeholder="e.g. my mother" />
        </label>
        <label className="field">
          Region (for support resources)
          <input type="text" value={profile.region} onChange={(e) => set('region', e.target.value)} placeholder="e.g. Singapore" />
        </label>
        <button type="submit">Save</button>
        {saved && <span className="me-saved">Saved ✓</span>}
      </form>

      <div className="understand-section">
        <h2>Your data</h2>
        <p className="section-sub">
          Check-ins, capacity, and journal entries stay on your own backend. Camera readings only
          enrich your capacity score and are never stored as images.
        </p>
        <p className="section-sub">
          Coordinate care in <Link to="/companion">AI Copilot</Link>, or find outside help in{' '}
          <Link to="/resources">Resource Finder</Link>.
        </p>
      </div>

      <div className="understand-section">
        <h2>About</h2>
        <p className="section-sub">
          A support tool for family caregivers — not a medical device, and not a diagnosis. If you're
          in crisis, please reach out to local emergency services or a crisis line.
        </p>
      </div>
    </div>
  )
}
