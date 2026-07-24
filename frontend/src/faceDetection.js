// Detects whether a face is present in the webcam feed — presence only, no biometric
// measurement. Uses TinyFaceDetector — a small (~190KB), fast model, good enough for a
// bounding box (we don't need landmarks or recognition). Weights are served locally from
// /public/models, no CDN/network needed.
//
// face-api.js bundles TF.js internally (~1.3MB) — dynamically imported here so it only
// loads once the camera actually starts, not as part of the initial app bundle.

const MODEL_URL = '/models'

let loadPromise = null
let faceapiModule = null

export function loadFaceDetectionModel() {
  if (!loadPromise) {
    loadPromise = import('@vladmandic/face-api').then(async (faceapi) => {
      faceapiModule = faceapi
      await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL)
    })
  }
  return loadPromise
}

export async function detectFaceBox(videoEl) {
  if (!faceapiModule) return null
  const options = new faceapiModule.TinyFaceDetectorOptions({ inputSize: 160, scoreThreshold: 0.5 })
  const result = await faceapiModule.detectSingleFace(videoEl, options)
  if (!result) return null
  const { x, y, width, height } = result.box
  return { x, y, width, height }
}
