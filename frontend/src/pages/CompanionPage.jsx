import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { CoordinateCard } from '../components/CoordinateCard'
import { RechargeCard } from '../components/RechargeCard'
import { YesterdayProgress } from '../components/YesterdayProgress'

// AI Copilot = proactive opening line + three cards (Recharge & Reconnect, Coordinate,
// Progress) + a warm chat.
export function CompanionPage() {
  const [opening, setOpening] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    api.companionOpening().then(setOpening).catch(() => {})
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

      {opening && <div className="copilot-opening">{opening.opening}</div>}

      <RechargeCard />
      <CoordinateCard />
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
