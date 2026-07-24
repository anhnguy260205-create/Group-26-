import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './App.css'
import { Layout } from './components/Layout'
import { BurnoutDashboardPage } from './pages/BurnoutDashboardPage'
import { CheckinPage } from './pages/CheckinPage'
import { CompanionPage } from './pages/CompanionPage'
import { HomePage } from './pages/HomePage'
import { JournalPage } from './pages/JournalPage'
import { ResourceFinderPage } from './pages/ResourceFinderPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/checkin" element={<CheckinPage />} />
          <Route path="/companion" element={<CompanionPage />} />
          <Route path="/journal" element={<JournalPage />} />
          <Route path="/burnout" element={<BurnoutDashboardPage />} />
          <Route path="/resources" element={<ResourceFinderPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
