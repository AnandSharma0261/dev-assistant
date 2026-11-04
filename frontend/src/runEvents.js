// How SSE "stage" events from the backend update the UI state.

export const STAGES = [
  { key: 'planner', label: 'Planner' },
  { key: 'architect', label: 'Architect' },
  { key: 'developer', label: 'Developer' },
  { key: 'preview', label: 'Preview' },
  { key: 'reviewer', label: 'Reviewer' },
  { key: 'fix', label: 'Fix' },
  { key: 'qa', label: 'QA' },
]

export const STATUS_ICON = { pending: '○', running: '◌', done: '✓', failed: '✕', skipped: '–' }

export const initialStages = () => Object.fromEntries(STAGES.map((s) => [s.key, 'pending']))

// Which stages a refinement re-runs; the rest keep the parent's (done) state
export const REFINE_STAGES = { preview: ['preview'], code: ['developer', 'reviewer'] }

export function stageStatus({ stage, status, data }) {
  if (status === 'done') return stage === 'fix' && data?.skipped ? 'skipped' : 'done'
  if (status === 'failed') return 'failed'
  return 'running'   // started / delta / progress
}

const RESULT_KEY = { planner: 'plan', architect: 'design', preview: 'preview', reviewer: 'review', qa: 'tests' }

// Apply one stage event to the (partial) report
export function applyToResult(result, { stage, status, data }) {
  if ((stage === 'developer' || stage === 'fix') && status === 'progress') {
    const { index, ...output } = data
    const dev = [...(result.dev_outputs || [])]
    dev[index] = output
    return { ...result, dev_outputs: dev }
  }
  if (stage === 'fix' && status === 'done' && data?.review) {
    return { ...result, review: data.review, self_correction: data.self_correction }
  }
  if (status === 'done' && RESULT_KEY[stage] && data) {
    return { ...result, [RESULT_KEY[stage]]: data }
  }
  return result
}

// Text being streamed right now: {developer: {index: text}, fix: {index: text}, preview: text|null}
export const emptyStreams = () => ({ developer: {}, fix: {}, preview: null })

export function applyToStreams(streams, { stage, status, data }) {
  if (stage === 'preview') {
    if (status === 'delta') {
      const prev = data.reset ? '' : (streams.preview || '')
      return { ...streams, preview: prev + (data.append || '') }
    }
    if (status === 'done' || status === 'failed') return { ...streams, preview: null }
    return streams
  }
  if (stage === 'developer' || stage === 'fix') {
    if (status === 'delta') {
      const prev = data.reset ? '' : (streams[stage][data.index] || '')
      return { ...streams, [stage]: { ...streams[stage], [data.index]: prev + (data.append || '') } }
    }
    if (status === 'progress') {
      const { [data.index]: _finished, ...rest } = streams[stage]
      return { ...streams, [stage]: rest }
    }
  }
  return streams
}
