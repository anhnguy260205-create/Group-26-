import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { estimateHeartRate, estimateRespirationRate, meanGreen } from '../rppg'

const SAMPLE_INTERVAL_MS = 100 // ~10Hz, plenty for heart-rate-range signals
const ANALYZE_INTERVAL_MS = 5000
const BUFFER_WINDOW_MS = 30000
const CAMERA_TIMEOUT_MS = 6000
const LOW_SIGNAL_GRACE_ANALYSES = 3 // how many bad analyses before falling back to manual

/**
 * Runs quietly in the background: samples the webcam, estimates heart/respiration rate via
 * rPPG, and periodically reports a stress reading to the backend. Falls back to a manual
 * self-report if the camera is unavailable, denied, or the signal stays too noisy to trust —
 * the app must keep working either way.
 */
export function useStressMonitor({ enabled }) {
  const [status, setStatus] = useState('idle') // idle | starting | active | manual-fallback
  const [latest, setLatest] = useState(null)
  const [manualValue, setManualValue] = useState(5)

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const bufferRef = useRef([])
  const lowSignalStreakRef = useRef(0)
  const timersRef = useRef([])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  const submitManual = useCallback(async (value) => {
    try {
      const reading = await api.ingestStress({ source: 'manual', self_reported_stress: value })
      setLatest(reading)
    } catch {
      // Offline demo fallback: keep the UI responsive even if the API call fails.
    }
  }, [])

  useEffect(() => {
    if (!enabled) {
      stopCamera()
      timersRef.current.forEach(clearInterval)
      timersRef.current = []
      setStatus('idle')
      return
    }

    let cancelled = false
    setStatus('starting')

    const fallbackTimer = setTimeout(() => {
      if (!cancelled && streamRef.current == null) setStatus('manual-fallback')
    }, CAMERA_TIMEOUT_MS)

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setStatus('manual-fallback')
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
        setStatus('active')
      } catch {
        if (!cancelled) setStatus('manual-fallback')
      }
    }
    start()

    const sampleTimer = setInterval(() => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!video || !canvas || video.readyState < 2) return
      const ctx = canvas.getContext('2d', { willReadFrequently: true })
      const size = 60 // small center crop, stand-in for a face ROI
      ctx.drawImage(
        video,
        video.videoWidth / 2 - size / 2,
        video.videoHeight / 2 - size / 2,
        size,
        size,
        0,
        0,
        size,
        size
      )
      const frame = ctx.getImageData(0, 0, size, size)
      const now = performance.now()
      bufferRef.current.push({ t: now, v: meanGreen(frame) })
      bufferRef.current = bufferRef.current.filter((s) => now - s.t <= BUFFER_WINDOW_MS)
    }, SAMPLE_INTERVAL_MS)

    const analyzeTimer = setInterval(async () => {
      if (streamRef.current == null) return
      const samples = bufferRef.current
      const hr = estimateHeartRate(samples)
      const resp = estimateRespirationRate(samples)

      if (hr.bpm == null || hr.confidence < 0.35) {
        lowSignalStreakRef.current += 1
        if (lowSignalStreakRef.current >= LOW_SIGNAL_GRACE_ANALYSES) {
          setStatus('manual-fallback')
        }
        return
      }
      lowSignalStreakRef.current = 0

      try {
        const reading = await api.ingestStress({
          source: 'rppg',
          heart_rate_bpm: hr.bpm,
          respiration_rate_bpm: resp.bpm ?? undefined,
          signal_quality: hr.confidence,
        })
        setLatest(reading)
      } catch {
        // Backend unreachable — keep sensing locally, just skip this report.
      }
    }, ANALYZE_INTERVAL_MS)

    timersRef.current = [sampleTimer, analyzeTimer]

    return () => {
      cancelled = true
      clearTimeout(fallbackTimer)
      clearInterval(sampleTimer)
      clearInterval(analyzeTimer)
      stopCamera()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled])

  return {
    status,
    latest,
    manualValue,
    setManualValue,
    submitManual,
    videoRef,
    canvasRef,
  }
}
