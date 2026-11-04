// ============================================================
//  Phase 7: Frontend — "Midnight IDE" theme
//  Framer Motion (animations) + react-syntax-highlighter (code)
// ============================================================

import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

// fonts (npm package se — internet par depend nahi)
import '@fontsource/inter/400.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/800.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/700.css'

import './App.css'

// Local par localhost; deploy par Vercel mein VITE_API_URL set karenge (Render ka backend URL)
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const EXAMPLE = "Ek To-Do list web app banao jisme user task add, delete, aur 'complete' mark kar sake. User login/signup bhi ho."
const STAGES = [
  { key: 'planner', label: 'Planner' },
  { key: 'architect', label: 'Architect' },
  { key: 'developer', label: 'Developer' },
  { key: 'reviewer', label: 'Reviewer' },
  { key: 'qa', label: 'QA' },
]
// Which part of the report each stage's "done" event fills in
const RESULT_KEY = { planner: 'plan', architect: 'design', reviewer: 'review', qa: 'tests' }
const STATUS_ICON = { pending: '○', running: '◌', done: '✓', failed: '✕' }

const initialStages = () => Object.fromEntries(STAGES.map((s) => [s.key, 'pending']))

// Apply one SSE "stage" event to the partial report
function applyStageEvent(result, { stage, status, data }) {
  if (stage === 'developer' && status === 'progress') {
    return { ...result, dev_outputs: [...(result.dev_outputs || []), data] }
  }
  if (status === 'done' && RESULT_KEY[stage] && data) {
    return { ...result, [RESULT_KEY[stage]]: data }
  }
  return result
}

// Developer ke code se markdown fences (```) hatao taaki saaf highlight ho
function cleanCode(raw) {
  if (!raw) return ''
  return raw.trim().replace(/^```[a-zA-Z]*\n?/, '').replace(/\n?```$/, '').trim()
}

// Framer Motion variants — results cards ek-ek karke (stagger) andar aayenge
const container = { hidden: {}, show: { transition: { staggerChildren: 0.1 } } }
const item = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: 'easeOut' } },
}

function App() {
  const [requirement, setRequirement] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [stages, setStages] = useState(initialStages)
  const [devProgress, setDevProgress] = useState({ done: 0, total: 0 })
  const [error, setError] = useState('')
  const sourceRef = useRef(null)

  const closeStream = () => {
    sourceRef.current?.close()
    sourceRef.current = null
  }

  // Close the SSE connection if the component unmounts mid-run
  useEffect(() => closeStream, [])

  const finish = (errorMessage) => {
    closeStream()
    setLoading(false)
    if (errorMessage) {
      setError(errorMessage)
      setStages((s) => Object.fromEntries(
        Object.entries(s).map(([k, v]) => [k, v === 'running' ? 'failed' : v]),
      ))
    }
  }

  // Subscribe to the run's live progress (Server-Sent Events)
  const listen = (runId) => {
    const es = new EventSource(`${API_URL}/runs/${runId}/events`)
    sourceRef.current = es

    es.addEventListener('stage', (e) => {
      const event = JSON.parse(e.data)
      const { stage, status, data } = event
      setStages((s) => ({ ...s, [stage]: status === 'done' ? 'done' : 'running' }))
      if (stage === 'developer') {
        if (status === 'started') setDevProgress({ done: 0, total: data?.total || 0 })
        if (status === 'progress') setDevProgress((p) => ({ ...p, done: p.done + 1 }))
      }
      setResult((r) => applyStageEvent(r || {}, event))
    })
    es.addEventListener('done', () => finish())
    es.addEventListener('failed', (e) => finish(JSON.parse(e.data).message))
    // Network blips: EventSource reconnects by itself (resuming via Last-Event-ID).
    // It only gives up (CLOSED) on a hard failure such as a 404.
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) finish('Lost connection to the server.')
    }
  }

  const handleGenerate = async () => {
    if (!requirement.trim()) { setError('Pehle requirement likho.'); return }
    closeStream()
    setError(''); setLoading(true); setResult(null)
    setStages(initialStages()); setDevProgress({ done: 0, total: 0 })
    try {
      const res = await fetch(`${API_URL}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requirement, max_dev_tasks: 2 }),
      })
      const json = await res.json().catch(() => ({}))
      if (!res.ok) {
        finish(json.detail || `Server error (${res.status})`)
        return
      }
      listen(json.run_id)
    } catch (e) {
      finish('Error: ' + e.message + ' — backend chal raha hai? (port 8000)')
    }
  }

  const showPipeline = loading || Object.values(stages).some((s) => s !== 'pending')

  return (
    <div className="app">
      {/* ---- Header ---- */}
      <motion.header
        className="header"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <div className="brand">
          <span className="brand-mark">◆</span>
          <h1>dev<span className="accent">.assistant</span></h1>
        </div>
        <p className="tagline">// requirement → plan · design · code · review · tests</p>
      </motion.header>

      {/* ---- Input panel ---- */}
      <motion.section
        className="card input-card"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
      >
        <div className="label">$ requirement</div>
        <textarea
          className="textarea"
          rows={5}
          placeholder="e.g. Ek blog website banao jisme user post likh sake..."
          value={requirement}
          onChange={(e) => setRequirement(e.target.value)}
        />
        <div className="btn-row">
          <button className="btn-ghost" onClick={() => setRequirement(EXAMPLE)} disabled={loading}>
            Try Example
          </button>
          <motion.button
            className="btn-primary"
            onClick={handleGenerate}
            disabled={loading}
            whileHover={{ scale: loading ? 1 : 1.04 }}
            whileTap={{ scale: loading ? 1 : 0.96 }}
          >
            {loading ? 'Running…' : '⚡ Generate'}
          </motion.button>
        </div>
        {error && <p className="error">{error}</p>}
      </motion.section>

      {/* ---- Live agent pipeline (driven by SSE stage events) ---- */}
      <AnimatePresence>
        {showPipeline && (
          <motion.div
            className="loader"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          >
            <div className="pipeline">
              {STAGES.map(({ key, label }) => {
                const status = stages[key]
                return (
                  <motion.div
                    key={key}
                    className={`stage stage-${status}`}
                    animate={status === 'running' ? { opacity: [0.5, 1, 0.5] } : { opacity: 1 }}
                    transition={status === 'running' ? { duration: 1.2, repeat: Infinity } : { duration: 0.2 }}
                  >
                    <span className="stage-icon">{STATUS_ICON[status]}</span> {label}
                    {key === 'developer' && devProgress.total > 0 && status !== 'pending' && (
                      <span className="stage-count"> {devProgress.done}/{devProgress.total}</span>
                    )}
                  </motion.div>
                )
              })}
            </div>
            {loading && (
              <p className="loader-text">
                {(() => {
                  // Several agents can run at once (parallel Developer tasks, Reviewer + QA)
                  const running = STAGES.filter(({ key }) => stages[key] === 'running').map((s) => s.label)
                  if (running.length === 0) return 'Run shuru ho raha hai…'
                  return running.length === 1
                    ? `${running[0]} kaam kar raha hai…`
                    : `${running.join(' + ')} parallel mein kaam kar rahe hain…`
                })()}
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ---- Results (each section appears as soon as its agent finishes) ---- */}
      {result && <Results data={result} />}
    </div>
  )
}

// ============================================================
//  Results — saari report sections, stagger animation ke saath
// ============================================================
function Results({ data }) {
  return (
    <motion.div className="results" variants={container} initial="hidden" animate="show">
      {/* Plan */}
      {data.plan && <motion.section className="card" variants={item}>
        <h2><span className="h-mark">▸</span> Plan</h2>
        <ul className="task-list">
          {data.plan?.tasks?.map((t) => (
            <li key={t.id}>
              <span className={`badge ${t.priority?.toLowerCase()}`}>{t.priority}</span>
              <strong>{t.title}</strong>
              <div className="dim">{t.description}</div>
            </li>
          ))}
        </ul>
      </motion.section>}

      {/* Architecture */}
      {data.design && <motion.section className="card" variants={item}>
        <h2><span className="h-mark">▸</span> Architecture</h2>
        <div className="stack">
          {data.design?.tech_stack &&
            Object.entries(data.design.tech_stack).map(([k, v]) => (
              <div key={k} className="stack-item">
                <span className="stack-key">{k}</span>
                <span>{Array.isArray(v) ? v.join(', ') : v}</span>
              </div>
            ))}
        </div>
      </motion.section>}

      {/* Generated code */}
      {data.dev_outputs?.length > 0 && <motion.section className="card" variants={item}>
        <h2><span className="h-mark">▸</span> Generated Code</h2>
        {data.dev_outputs?.map((d, i) => (
          <div key={i} className="code-block">
            <div className="code-title">{d.task}</div>
            <SyntaxHighlighter
              language="javascript"
              style={oneDark}
              customStyle={{ borderRadius: 12, fontSize: 13, margin: 0, background: '#0d1117' }}
            >
              {cleanCode(d.code)}
            </SyntaxHighlighter>
          </div>
        ))}
      </motion.section>}

      {/* Review */}
      {data.review && <motion.section className="card" variants={item}>
        <h2><span className="h-mark">▸</span> Code Review</h2>
        <ul className="findings">
          {data.review?.findings?.map((f, i) => (
            <li key={i}>
              <span className={`badge ${f.severity?.toLowerCase()}`}>{f.severity}</span>
              <strong>{f.issue}</strong>
              <div className="dim">💡 {f.suggestion}</div>
            </li>
          ))}
        </ul>
        {data.review?.overall_summary && (
          <p className="summary">{data.review.overall_summary}</p>
        )}
      </motion.section>}

      {/* Tests */}
      {data.tests && <motion.section className="card" variants={item}>
        <h2><span className="h-mark">▸</span> Test Cases</h2>
        <ul className="test-list">
          {data.tests?.test_cases?.map((tc) => (
            <li key={tc.id}>
              <strong>{tc.title}</strong>
              <div className="dim">✅ {tc.expected}</div>
            </li>
          ))}
        </ul>
      </motion.section>}
    </motion.div>
  )
}

export default App
