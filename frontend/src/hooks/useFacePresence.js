import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { detectFace, loadFaceDetectionModel } from '../faceDetection'

const CAMERA_TIMEOUT_MS = 6000
const DETECT_INTERVAL_MS = 1000
const ANALYZE_INTERVAL_MS = 5000 // how often a detected expression gets posted as a stress reading

/**
 * Quietly checks whether a face is present in the webcam feed, and — when one is — reads
 * its facial expression as a fallback/enrichment stress signal alongside Daily Check-in
 * (see scoring.expression_to_stress_score on the backend). Check-in stays the reliable
 * core; this is a background enrichment that degrades gracefully to presence-only if the
 * camera is denied/missing or detection fails — the app never depends on it.
 *
 * This is the ONLY getUserMedia call site in the app — never open a second camera stream
 * elsewhere. Consumers that need to render the live feed must use the returned
 * `attachVideo` callback ref (not a plain ref) so the stream correctly (re)binds no matter
 * which component currently owns the video DOM node.
 */
export function useFacePresence({ enabled }) {
  const [status, setStatus] = useState('idle') // idle | starting | present | absent | unavailable
  const [latest, setLatest] = useState(null)

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const timersRef = useRef([])
  const expressionRef = useRef(null) // most recent detected expression, or null
  const pendingCaptureRef = useRef(null) // { resolve, timeoutId } for an in-flight captureNow()

  const attachVideo = useCallback((node) => {
    videoRef.current = node
    if (node && streamRef.current) {
      node.srcObject = streamRef.current
      node.play().catch(() => {})
    }
  }, [])

  const settleCapture = useCallback((result) => {
    const pending = pendingCaptureRef.current
    if (!pending) return
    pendingCaptureRef.current = null
    clearTimeout(pending.timeoutId)
    pending.resolve(result)
  }, [])

  const resolveCaptureWithExpression = useCallback(
    async (expression) => {
      try {
        const reading = await api.ingestStress({ source: 'expression', expression })
        setLatest(reading)
        settleCapture({ outcome: 'captured', reading })
      } catch {
        settleCapture({ outcome: 'unavailable', reading: null })
      }
    },
    [settleCapture]
  )

  /**
   * One-off "capture as soon as a face is seen, or give up after timeoutMs" — used for a
   * quick on-entry read rather than waiting on the periodic 5s analyzeTimer cadence.
   * Resolves { outcome: 'captured' | 'no-face' | 'unavailable', reading }.
   */
  const captureNow = useCallback(
    ({ timeoutMs = 4000 } = {}) => {
      return new Promise((resolve) => {
        if (status === 'unavailable') {
          resolve({ outcome: 'unavailable', reading: null })
          return
        }
        const timeoutId = setTimeout(() => {
          pendingCaptureRef.current = null
          resolve({ outcome: 'no-face', reading: null })
        }, timeoutMs)
        pendingCaptureRef.current = { resolve, timeoutId }

        if (expressionRef.current) {
          resolveCaptureWithExpression(expressionRef.current)
        }
      })
    },
    [status, resolveCaptureWithExpression]
  )

  useEffect(() => {
    // Camera never started (or was already unavailable when captureNow was called) — don't
    // make a pending capture wait out its full timeout for something that'll never resolve.
    if (status === 'unavailable') {
      settleCapture({ outcome: 'unavailable', reading: null })
    }
  }, [status, settleCapture])

  useEffect(() => {
    if (!enabled) {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      timersRef.current.forEach(clearInterval)
      timersRef.current = []
      expressionRef.current = null
      settleCapture({ outcome: 'unavailable', reading: null })
      setStatus('idle')
      return
    }

    let cancelled = false
    setStatus('starting')

    const fallbackTimer = setTimeout(() => {
      if (!cancelled && streamRef.current == null) setStatus('unavailable')
    }, CAMERA_TIMEOUT_MS)

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setStatus('unavailable')
        return
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 160, height: 120, facingMode: 'user' },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        const video = videoRef.current
        if (video) {
          video.srcObject = stream
          await video.play()
        }
        clearTimeout(fallbackTimer)

        try {
          await loadFaceDetectionModel()
        } catch {
          // Camera works but no detection model available — can't tell presence either way.
          setStatus('unavailable')
          return
        }
        if (cancelled) return
        setStatus('absent')

        const detectTimer = setInterval(async () => {
          const v = videoRef.current
          if (!v || v.readyState < 2) return
          try {
            const result = await detectFace(v)
            setStatus(result ? 'present' : 'absent')
            expressionRef.current = result?.expressions ?? null
            if (result?.expressions && pendingCaptureRef.current) {
              resolveCaptureWithExpression(result.expressions)
            }
          } catch {
            // Transient detection error on this frame — leave status as-is, try again next tick.
          }
        }, DETECT_INTERVAL_MS)
        timersRef.current.push(detectTimer)

        const analyzeTimer = setInterval(async () => {
          const expression = expressionRef.current
          if (!expression) return
          try {
            const reading = await api.ingestStress({ source: 'expression', expression })
            setLatest(reading)
          } catch {
            // Backend unreachable — keep sensing locally, just skip this report.
          }
        }, ANALYZE_INTERVAL_MS)
        timersRef.current.push(analyzeTimer)
      } catch {
        if (!cancelled) setStatus('unavailable')
      }
    }
    start()

    return () => {
      cancelled = true
      clearTimeout(fallbackTimer)
      timersRef.current.forEach(clearInterval)
      timersRef.current = []
      expressionRef.current = null
      settleCapture({ outcome: 'unavailable', reading: null })
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled])

  return { status, latest, attachVideo, captureNow }
}
