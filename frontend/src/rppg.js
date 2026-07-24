// Minimal remote-photoplethysmography signal processing.
//
// Not currently wired into the live app — the camera pipeline (useFacePresence.js) only
// does face-presence detection now. Kept here for the spec's optional "Quick Pulse Check"
// bonus feature (a user-triggered 20-second reading), which can reuse this as-is: sample
// the mean green value of a skin-region crop on every capture tick, then run peak detection
// over a rolling window to estimate heart rate. Intentionally simple — good enough for a
// discreet signal, not a medical device.

export function meanGreen(imageData) {
  const { data } = imageData
  let sum = 0
  const pixelCount = data.length / 4
  for (let i = 0; i < data.length; i += 4) {
    sum += data[i + 1] // green channel
  }
  return sum / pixelCount
}

function movingAverage(values, windowSize) {
  const out = new Array(values.length)
  let sum = 0
  for (let i = 0; i < values.length; i++) {
    sum += values[i]
    if (i >= windowSize) sum -= values[i - windowSize]
    out[i] = sum / Math.min(i + 1, windowSize)
  }
  return out
}

/**
 * Detect peaks in a detrended signal and estimate a rate in beats/breaths per minute.
 * @param {{t: number, v: number}[]} samples - chronological {timestamp(ms), value} pairs
 * @param {number} minPeriodMs - minimum allowed spacing between peaks
 * @param {number} maxPeriodMs - maximum allowed spacing between peaks
 */
export function estimateRateBpm(samples, minPeriodMs, maxPeriodMs) {
  if (samples.length < 10) return { bpm: null, confidence: 0 }

  const values = samples.map((s) => s.v)
  const smooth = movingAverage(values, 3)
  const trend = movingAverage(values, Math.max(5, Math.floor(samples.length / 3)))
  const detrended = smooth.map((v, i) => v - trend[i])

  const std = Math.sqrt(detrended.reduce((a, v) => a + v * v, 0) / detrended.length) || 1
  const peakThreshold = 0.3 * std

  const peaks = []
  for (let i = 1; i < detrended.length - 1; i++) {
    const isLocalMax = detrended[i] > detrended[i - 1] && detrended[i] >= detrended[i + 1]
    if (!isLocalMax || detrended[i] <= peakThreshold) continue
    const lastPeak = peaks[peaks.length - 1]
    if (lastPeak && samples[i].t - lastPeak.t < minPeriodMs) continue
    peaks.push(samples[i])
  }

  if (peaks.length < 3) return { bpm: null, confidence: 0 }

  const intervals = []
  for (let i = 1; i < peaks.length; i++) {
    const gap = peaks[i].t - peaks[i - 1].t
    if (gap >= minPeriodMs && gap <= maxPeriodMs) intervals.push(gap)
  }
  if (intervals.length < 2) return { bpm: null, confidence: 0 }

  const meanInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length
  const variance = intervals.reduce((a, v) => a + (v - meanInterval) ** 2, 0) / intervals.length
  const coeffVariation = Math.sqrt(variance) / meanInterval

  const bpm = 60000 / meanInterval
  // Regular spacing -> higher confidence; erratic spacing (motion, bad lighting) -> lower.
  const confidence = Math.max(0, Math.min(1, 1 - coeffVariation * 2))

  return { bpm: Math.round(bpm * 10) / 10, confidence: Math.round(confidence * 100) / 100 }
}

export function estimateHeartRate(samples) {
  // 40-180 bpm -> 333ms-1500ms period
  return estimateRateBpm(samples, 333, 1500)
}

export function estimateRespirationRate(samples) {
  // 6-24 breaths/min -> 2500ms-10000ms period, needs a longer buffer than heart rate
  return estimateRateBpm(samples, 2500, 10000)
}
