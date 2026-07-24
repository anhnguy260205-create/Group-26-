import { useEffect, useRef, useState } from 'react'
import { detectFaceBox, loadFaceDetectionModel } from '../faceDetection'

const CAMERA_TIMEOUT_MS = 6000
const DETECT_INTERVAL_MS = 1000

/**
 * Quietly checks whether a face is present in the webcam feed — presence only, no
 * biometric measurement, nothing posted to the backend. Purely a background indicator;
 * the app never depends on this for anything functional, so any failure (camera denied,
 * no camera, detection model unavailable) just settles into 'unavailable'/'absent'.
 */
export function useFacePresence({ enabled }) {
  const [status, setStatus] = useState('idle') // idle | starting | present | absent | unavailable

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const timersRef = useRef([])

  useEffect(() => {
    if (!enabled) {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      timersRef.current.forEach(clearInterval)
      timersRef.current = []
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
        video.srcObject = stream
        await video.play()
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
            const box = await detectFaceBox(v)
            setStatus(box ? 'present' : 'absent')
          } catch {
            // Transient detection error on this frame — leave status as-is, try again next tick.
          }
        }, DETECT_INTERVAL_MS)
        timersRef.current.push(detectTimer)
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
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [enabled])

  return { status, videoRef }
}
