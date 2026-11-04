// Backend API client. Every response uses one envelope:
//   {success: true, data} | {success: false, message, errors?}

// Local par localhost; deploy par VITE_API_URL set karo (backend URL)
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export class ApiError extends Error {}

export async function api(path, { method = 'GET', body, keepalive } = {}) {
  let res
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      keepalive,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(`Backend se connect nahi ho paaya (${API_URL}). Kya woh chal raha hai?`)
  }
  const json = await res.json().catch(() => ({}))
  if (!res.ok || !json.success) {
    const fieldErrors = (json.errors || []).map((e) => `${e.field}: ${e.message}`).join('; ')
    const err = new ApiError([json.message || `Server error (${res.status})`, fieldErrors].filter(Boolean).join(' '))
    err.status = res.status
    throw err
  }
  return json.data
}

export const startRun = (requirement, maxDevTasks = 2) =>
  api('/runs', { method: 'POST', body: { requirement, max_dev_tasks: maxDevTasks } })
export const refineRun = (runId, instruction, target) =>
  api(`/runs/${runId}/refine`, { method: 'POST', body: { instruction, target } })
export const getRun = (runId) => api(`/runs/${runId}`)
export const cancelRun = (runId, opts = {}) => api(`/runs/${runId}`, { method: 'DELETE', ...opts })
export const downloadUrl = (runId) => `${API_URL}/runs/${runId}/download`
export const eventsUrl = (runId) => `${API_URL}/runs/${runId}/events`

export const getStandards = () => api('/standards')
export const uploadStandards = (content) => api('/standards', { method: 'PUT', body: { content } })
export const resetStandards = () => api('/standards', { method: 'DELETE' })
