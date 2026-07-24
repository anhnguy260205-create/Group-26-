const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function request(path, options) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`${options?.method || 'GET'} ${path} failed: ${res.status}`)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),

  listTasks: () => request('/tasks'),
  createTask: (task) => request('/tasks', { method: 'POST', body: JSON.stringify(task) }),
  toggleTask: (id) => request(`/tasks/${id}/toggle`, { method: 'POST' }),
  deleteTask: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),
  assignTask: (id, assigned_to) =>
    request(`/tasks/${id}/assign`, { method: 'POST', body: JSON.stringify({ assigned_to }) }),
  suggestDelegation: () => request('/delegation/suggest'),

  ingestStress: (reading) => request('/stress', { method: 'POST', body: JSON.stringify(reading) }),
  listStress: (limit = 100) => request(`/stress?limit=${limit}`),

  checkThreshold: () => request('/threshold/check'),

  startSession: (trigger) => request('/intervention/start', { method: 'POST', body: JSON.stringify(trigger) }),
  getPace: (sessionId) => request(`/intervention/${sessionId}/pace`),
  endSession: (sessionId, body = {}) =>
    request(`/intervention/${sessionId}/end`, { method: 'POST', body: JSON.stringify(body) }),

  generateReflection: (sessionId) => request(`/reflection/${sessionId}`, { method: 'POST' }),

  submitCheckin: (checkin) => request('/checkin', { method: 'POST', body: JSON.stringify(checkin) }),
  latestCheckin: () => request('/checkin/latest'),
  capacityForecast: (days = 14) => request(`/capacity/forecast?days=${days}`),
  capacityOutlook: () => request('/capacity/outlook'),
  rechargeToday: () => request('/recharge/today'),
  setRechargeStatus: (id, status) =>
    request(`/recharge/${id}/status`, { method: 'POST', body: JSON.stringify({ status }) }),
  progress: () => request('/progress'),
  companionOpening: () => request('/companion/opening'),
  stressTrends: (days = 7) => request(`/stress/trends?days=${days}`),
  burnoutRisk: (days = 7) => request(`/stress/burnout-risk?days=${days}`),
  stressForecast: (days = 3) => request(`/stress/forecast?days=${days}`),
  weeklySummary: () => request('/summary/weekly'),
  dailySuggestions: () => request('/suggestions/daily'),
  analyzeEmotion: (text) => request('/emotion', { method: 'POST', body: JSON.stringify({ text }) }),

  listJournal: (limit = 50) => request(`/journal?limit=${limit}`),
  createJournalEntry: (entry) => request('/journal', { method: 'POST', body: JSON.stringify(entry) }),
  journalSummary: () => request('/journal/summary'),

  companionChat: (content) => request('/companion/chat', { method: 'POST', body: JSON.stringify({ content }) }),
  companionMessages: (limit = 50) => request(`/companion/messages?limit=${limit}`),

  listResources: (region) => request(`/resources${region ? `?region=${encodeURIComponent(region)}` : ''}`),
}
