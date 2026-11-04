// Backend API client. Every response uses one envelope:
//   {success: true, data} | {success: false, message, errors?}

// Dev: the backend on localhost:8000. Docker: "/api" (nginx proxies it, same origin).
// Another deployment: set VITE_API_URL to the backend URL at build time.
export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// No accounts: each browser gets a random id once. The API uses it to scope
// history, cancel and refine to this browser.
const SESSION_KEY = 'devassistant.session'
function sessionId() {
  try {
    let id = localStorage.getItem(SESSION_KEY)
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem(SESSION_KEY, id)
    }
    return id
  } catch {
    // Storage blocked (private mode): a per-tab id still works for this visit
    return (window.__devAssistantSession ||= crypto.randomUUID())
  }
}

export class ApiError extends Error {}

export async function api(path, { method = 'GET', body, keepalive, headers = {} } = {}) {
  let res
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      keepalive,
      headers: {
        'X-Session-Id': sessionId(),
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
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
export const listRuns = (limit = 30) => api(`/runs?limit=${limit}`)
export const cancelRun = (runId, opts = {}) => api(`/runs/${runId}`, { method: 'DELETE', ...opts })
// Read-only links: run ids are unguessable, so these need no session
export const downloadUrl = (runId) => `${API_URL}/runs/${runId}/download`
export const eventsUrl = (runId) => `${API_URL}/runs/${runId}/events`

export const getStandards = () => api('/standards')
export const uploadStandards = (content, adminToken) =>
  api('/standards', { method: 'PUT', body: { content }, headers: { 'X-Admin-Token': adminToken } })
export const resetStandards = (adminToken) =>
  api('/standards', { method: 'DELETE', headers: { 'X-Admin-Token': adminToken } })
