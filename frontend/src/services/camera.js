import { connectRobotCamera, getRobotStatus } from './api'


export function captureVideoFrame(video, maxWidth = 640, quality = 0.8) {
  if (!video?.videoWidth) return Promise.resolve(null)

  const width = Math.min(video.videoWidth, maxWidth)
  const height = Math.round((width * video.videoHeight) / video.videoWidth)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  canvas.getContext('2d').drawImage(video, 0, 0, width, height)
  return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
}

export async function waitForRobotCamera() {
  await connectRobotCamera()
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const status = await getRobotStatus()
    if (status.connected) return status
    if (status.state === 'error') {
      throw new Error(status.error || 'Robot camera failed.')
    }
    await new Promise((resolve) => window.setTimeout(resolve, 250))
  }
  throw new Error('Timed out waiting for the robot camera.')
}
