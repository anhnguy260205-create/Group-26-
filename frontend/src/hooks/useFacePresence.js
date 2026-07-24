import { useEffect, useRef, useState } from 'react'
import { detectFaceBox, loadFaceDetectionModel } from '../faceDetection'

const CAMERA_TIMEOUT_MS = 6000
const DETECT_INTERVAL_MS = 1000

// Maps getUserMedia failure modes to a short, human-readable reason so the UI
// can tell the user something more useful than just "unavailable".
function describeError(err) {
  if (!window.isSecureContext) return 'Camera requires HTTPS (or localhost)'
  switch (err?.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'Camera permission denied'
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return 'No camera found'
    case 'NotReadableError':
    case 'TrackStartError':
      return 'Camera is in use by another app'
    case 'OverconstrainedError':
      return 'No camera matches the required settings'
    default:
      return 'Camera unavailable'
  }
}

/**
 * Quietly checks whether a face is present in the webcam feed — presence only, no
 * biometric measurement, nothing posted to the backend. Purely a background indicator;
 * the app never depends on this for anything functional, so any failure (camera denied,
 * no camera, detection model unavailable) just settles into 'unavailable'/'absent'. The
 * specific reason is still logged to the console and exposed via `reason` so it can be
 * surfaced in the UI instead of a single generic message.
 */
export function useFacePresence({ enabled }) {
  const [status, setStatus] = useState('idle') // idle | starting | present | absent | unavailable
  const [reason, setReason] = useState('')

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const timersRef = useRef([])

  const fail = (message, err) => {
    if (err) console.error('[useFacePresence]', message, err)
    else console.error('[useFacePresence]', message)
    setReason(message)
    setStatus('unavailable')
  }

  useEffect(() => {
    if (!enabled) {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      timersRef.current.forEach(clearInterval)
      timersRef.current = []
      setStatus('idle')
      setReason('')
      return
    }

    let cancelled = false
    setStatus('starting')
    setReason('')

    const fallbackTimer = setTimeout(() => {
      if (!cancelled && streamRef.current == null) fail('Timed out starting camera')
    }, CAMERA_TIMEOUT_MS)

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        fail(!window.isSecureContext ? 'Camera requires HTTPS (or localhost)' : 'Camera not supported in this browser')
        return
      }
      let stream
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 160, height: 120, facingMode: 'user' },
          audio: false,
        })
      } catch (err) {
        if (!cancelled) fail(describeError(err), err)
        return
      }
      if (cancelled) {
        stream.getTracks().forEach((t) => t.stop())
        return
      }
      streamRef.current = stream
      const video = videoRef.current
      video.srcObject = stream
      await video.play()
      clearTimeout(fallbackTimer)

      try {
        await loadFaceDetectionModel()
      } catch (err) {
        // Camera works but no detection model available — can't tell presence either way.
        if (!cancelled) fail('Face detection model failed to load', err)
        return
      }
      if (cancelled) return
      setStatus('absent')

      const detectTimer = setInterval(async () => {
        const v = videoRef.current
        if (!v || v.readyState < 2) return
        try {
          const box = await detectFaceBox(v)
          setStatus(box ? 'present' : 'absent')
        } catch (err) {
          // Transient detection error on this frame — leave status as-is, try again next tick.
          console.error('[useFacePresence] frame detection error', err)
        }
      }, DETECT_INTERVAL_MS)
      timersRef.current.push(detectTimer)
    }
    start()

    return () => {
      cancelled = true
      clearTimeout(fallbackTimer)
      timersRef.current.forEach(clearInterval)
      timersRef.current = []
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [enabled])

  return { status, reason, videoRef }
}
