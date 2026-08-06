const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options)
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = payload.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message || `Request failed (${response.status})`
    throw new Error(message)
  }
  return payload
}

export function getHealth() {
  return request('/api/health')
}

export function getPeople() {
  return request('/api/people')
}

export function recognizeImage(blob, threshold) {
  const form = new FormData()
  form.append('image', blob, 'camera-frame.jpg')
  form.append('threshold', String(threshold))
  return request('/api/recognize', { method: 'POST', body: form })
}

export function getRobotStatus() {
  return request('/api/robot/status')
}

export function connectRobotCamera() {
  return request('/api/robot/connect', { method: 'POST' })
}

export function getRobotStreamUrl() {
  return `${API_URL}/api/robot/stream`
}

export async function getRobotSnapshot() {
  const response = await fetch(`${API_URL}/api/robot/snapshot`, { cache: 'no-store' })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || `Robot snapshot failed (${response.status})`)
  }
  return response.blob()
}

export function recognizeRobotFrame(threshold) {
  const query = new URLSearchParams({ threshold: String(threshold) })
  return request(`/api/robot/recognize?${query}`, { method: 'POST' })
}

export function enrollPerson(name, files) {
  const form = new FormData()
  form.append('name', name)
  files.forEach((file) => form.append('images', file, file.name))
  return request('/api/enroll', { method: 'POST', body: form })
}
