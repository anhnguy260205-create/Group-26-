import { useEffect, useRef, useState } from 'react'

const CAPTURE_TIMEOUT_MS = 7000
// Always show the scanning moment for at least this long, even if a face is caught
// instantly — otherwise it can flash and vanish before it reads as anything.
const MIN_DISPLAY_MS = 1200

const SCORE_BANDS = [
  { max: 0.45, message: 'You seem to be doing okay right now.' },
  { max: 0.7, message: 'You seem a little tense right now.' },
  { max: Infinity, message: 'You seem quite stressed right now.' },
]

function messageForScore(score) {
  return SCORE_BANDS.find((band) => score < band.max).message
}

/**
 * The first thing shown on a fresh page load: a brief visible "checking in" moment using
 * the shared camera (see useFacePresence's captureNow). Shows the captured score if one
 * was read, then hands off to the normal app either way — never a dead end if the camera
 * is denied/unavailable or no face is found in time.
 */
export function EntryScan({ presence, onDone }) {
  const [phase, setPhase] = useState('scanning') // scanning | result
  const [reading, setReading] = useState(null)
  const startedRef = useRef(false)
  const mountedAtRef = useRef(Date.now())

  useEffect(() => {
    if (startedRef.current) return
    // Camera/model pipeline (getUserMedia + loading the face-api bundle + weights) is still
    // starting up — don't start the capture countdown yet, or it can burn its whole timeout
    // on load time alone and never get a real chance to detect a face, especially on a cold
    // cache (exactly the first-ever page load this feature is meant for).
    if (presence.status === 'idle' || presence.status === 'starting') return
    startedRef.current = true

    presence.captureNow({ timeoutMs: CAPTURE_TIMEOUT_MS }).then((result) => {
      const remaining = Math.max(0, MIN_DISPLAY_MS - (Date.now() - mountedAtRef.current))
      setTimeout(() => {
        if (result.outcome === 'captured') {
          setReading(result.reading)
          setPhase('result')
        } else {
          onDone()
        }
      }, remaining)
    })
  }, [presence, onDone])

  if (phase === 'scanning') {
    return (
      <div className="entryscan-overlay">
        {presence.status === 'unavailable' ? (
          <div className="entryscan-video entryscan-video-placeholder" />
        ) : (
          <video ref={presence.attachVideo} muted playsInline className="entryscan-video" />
        )}
        <p className="entryscan-message">Reading how you're doing…</p>
      </div>
    )
  }

  return (
    <div className="entryscan-overlay">
      <div className="checkin-result">
        <div className="checkin-score">{Math.round(reading.stress_score * 100)}</div>
        <p className="checkin-score-label">right now (0-100)</p>
      </div>
      <p className="entryscan-message">{messageForScore(reading.stress_score)}</p>
      <button type="button" onClick={onDone}>
        Continue
      </button>
    </div>
  )
}
