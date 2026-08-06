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

export function enrollPerson(name, files) {
  const form = new FormData()
  form.append('name', name)
  files.forEach((file) => form.append('images', file, file.name))
  return request('/api/enroll', { method: 'POST', body: form })
}
