import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { RechargeCard } from '../components/RechargeCard'
import { YesterdayProgress } from '../components/YesterdayProgress'

// AI Copilot = two cards (Recharge & Reconnect, Progress) + a warm chat.
//
// Coordinate lives on Home only. It's a task hand-off tool, not a conversation, and having it
// here duplicated the same card on two pages. The component and its backend (/delegation/suggest,
// /tasks) are untouched — task load also feeds scoring.behavioral_score(), which the intervention
// threshold depends on, so nothing about tasks can be removed safely.
//
// The capacity-aware opening line was removed from this page on purpose: it told the user to
// skip their check-in, but by the time they reach Copilot they've already passed Check-in, so
// the advice arrived too late to act on. The /companion/opening endpoint is still live and
// still returns the register, note and suggested action — re-mount it on the Home page (above
// the check-in entry point) rather than restoring it here.
export function CompanionPage() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    api.companionMessages().then(setMessages).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend(e) {
    e.preventDefault()
    const content = input.trim()
    if (!content || sending) return
    setInput('')
    setSending(true)
    const optimisticId = `pending-${Date.now()}`
    setMessages((prev) => [...prev, { id: optimisticId, role: 'user', content, created_at: new Date().toISOString() }])
    try {
      const res = await api.companionChat(content)
      setMessages((prev) => [...prev.filter((m) => m.id !== optimisticId), res.user_message, res.assistant_message])
    } catch {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimisticId),
        { id: `error-${Date.now()}`, role: 'assistant', content: "I couldn't reach the server just now — please try again.", created_at: new Date().toISOString() },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="page companion-page">
      <h1>AI Copilot</h1>
      <p className="page-subtitle">Warm support, a recovery plan, and help coordinating care.</p>

      <RechargeCard />
      <YesterdayProgress />

      <div className="understand-section">
        <h2>Talk it through</h2>
        <div className="chat-window">
          {messages.length === 0 && <p className="empty">Say hello — this is a space just for you.</p>}
          {messages.map((m) => (
            <div key={m.id} className={`chat-bubble chat-${m.role}`}>
              {m.content}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleSend} className="chat-input-row">
          <input type="text" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type how you're feeling…" />
          <button type="submit" disabled={sending || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
