const BASE = ''

async function request(url, opts = {}) {
  const r = await fetch(BASE + url, opts)
  if (!r.ok) {
    const txt = await r.text().catch(() => r.statusText)
    throw new Error(txt)
  }
  return r.json()
}

export async function fetchClips() {
  return request('/api/clips')
}

export async function fetchClip(clipId) {
  return request(`/api/clips/${clipId}`)
}

export async function fetchTags(clipId) {
  return request(`/api/clips/${clipId}/tags`)
}

export async function saveTags(clipId, tags) {
  return request(`/api/clips/${clipId}/tags`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags }),
  })
}

export async function fetchConfig() {
  return request('/api/config')
}

export async function submitJobs(
  clipIds,
  config,
  checkpoint,
  visualizationMode,
  configB,
  checkpointB,
  reuseCompleted = true,
) {
  const body = { clip_ids: clipIds }
  if (config) body.config = config
  if (checkpoint) body.checkpoint = checkpoint
  if (visualizationMode) body.visualization_mode = visualizationMode
  if (configB) body.config_b = configB
  if (checkpointB) body.checkpoint_b = checkpointB
  body.reuse_completed = !!reuseCompleted
  return request('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export async function fetchJobs() {
  return request('/api/jobs')
}

export async function deleteJob(jobId) {
  return request(`/api/jobs/${jobId}`, { method: 'DELETE' })
}

export async function fetchJobReview(jobId) {
  return request(`/api/jobs/${jobId}/review`)
}

export async function setJobReview(jobId, reviewStatus, note) {
  return request(`/api/jobs/${jobId}/review`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ review_status: reviewStatus, note: note ?? '' }),
  })
}

export async function starJob(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/star`, { method: 'POST' })
}

export async function unstarJob(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/star`, { method: 'DELETE' })
}

export async function submitAIOptimization(jobId, description) {
  return request('/api/ai/optimization', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ jobId, description }),
  })
}

export async function fetchAIOptimizations() {
  return request('/api/ai/optimizations')
}

export async function deleteAIOptimization(id) {
  return request(`/api/ai/optimizations/${id}`, { method: 'DELETE' })
}

export function videoUrl(jobId) {
  return `${BASE}/api/jobs/${jobId}/video`
}

export async function fetchJobAnnotations(jobId) {
  return request(`/api/jobs/${jobId}/annotations`)
}

export async function saveJobAnnotations(jobId, note, markers) {
  return request(`/api/jobs/${jobId}/annotations`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note, markers }),
  })
}

export function resolveImgSrc(p) {
  if (!p) return ''
  if (p.startsWith('../')) return '/' + p.slice(3)
  return p
}
