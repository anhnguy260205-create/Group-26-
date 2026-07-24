import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import { Layout } from './components/Layout'
import { CheckinPage } from './pages/CheckinPage'
import { CompanionPage } from './pages/CompanionPage'
import { HomePage } from './pages/HomePage'
import { MePage } from './pages/MePage'
import { ProgressPage } from './pages/ProgressPage'
import { ResourceFinderPage } from './pages/ResourceFinderPage'
import { UnderstandMePage } from './pages/UnderstandMePage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/checkin" element={<CheckinPage />} />
          <Route path="/understand-me" element={<UnderstandMePage />} />
          <Route path="/companion" element={<CompanionPage />} />
          <Route path="/progress" element={<ProgressPage />} />
          <Route path="/me" element={<MePage />} />
          {/* Kept, but off the main nav. */}
          <Route path="/resources" element={<ResourceFinderPage />} />
          {/* Removed screens redirect so old links still land somewhere sensible. */}
          <Route path="/journal" element={<Navigate to="/checkin" replace />} />
          <Route path="/burnout" element={<Navigate to="/understand-me" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
