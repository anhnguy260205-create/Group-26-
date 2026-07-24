import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

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
    // Optimistic user bubble so the chat feels responsive while the reply is generated.
    const optimisticId = `pending-${Date.now()}`
    setMessages((prev) => [
      ...prev,
      { id: optimisticId, role: 'user', content, created_at: new Date().toISOString() },
    ])
    try {
      const res = await api.companionChat(content)
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimisticId),
        res.user_message,
        res.assistant_message,
      ])
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
      <h1>AI Companion</h1>
      <p className="page-subtitle">Warm, supportive chat — not therapy, always here to listen.</p>

      <div className="chat-window">
        {messages.length === 0 && (
          <p className="empty">Say hello — this is a space just for you.</p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`chat-bubble chat-${m.role}`}>
            {m.content}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="chat-input-row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type how you're feeling…"
        />
        <button type="submit" disabled={sending || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
