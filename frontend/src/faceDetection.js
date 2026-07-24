// Detects a face in the webcam feed (presence + bounding box) and, in the same pass,
// its facial expression — used as a fallback/enrichment stress signal alongside Daily
// Check-in (see scoring.expression_to_stress_score on the backend). Uses TinyFaceDetector
// + a small expression-classification head (~190KB + ~330KB), weights served locally from
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
      await Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL),
        faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL),
      ])
    })
  }
  return loadPromise
}

/**
 * Returns { box, expressions } for the first detected face, or null if none found.
 * expressions is a plain object with 7 keys (neutral/happy/sad/angry/fearful/disgusted/
 * surprised), each a 0-1 probability summing to ~1 across all seven.
 */
export async function detectFace(videoEl) {
  if (!faceapiModule) return null
  const options = new faceapiModule.TinyFaceDetectorOptions({ inputSize: 160, scoreThreshold: 0.5 })
  const result = await faceapiModule.detectSingleFace(videoEl, options).withFaceExpressions()
  if (!result) return null
  const { x, y, width, height } = result.detection.box
  const { neutral, happy, sad, angry, fearful, disgusted, surprised } = result.expressions
  return {
    box: { x, y, width, height },
    expressions: { neutral, happy, sad, angry, fearful, disgusted, surprised },
  }
}
