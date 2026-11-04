// ============================================================
//  Frontend — "Midnight IDE" theme
//  Framer Motion (animations) + react-syntax-highlighter (code)
// ============================================================

import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

// fonts (npm package se — internet par depend nahi)
import '@fontsource/inter/400.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/800.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/700.css'

import './App.css'
import { cancelRun, eventsUrl, getRun, refineRun, startRun } from './api'
import {
  REFINE_STAGES, STAGES, STATUS_ICON, applyToResult, applyToStreams, emptyStreams, initialStages, stageStatus,
} from './runEvents'
import Results from './components/Results'
import StandardsPanel from './components/StandardsPanel'

const EXAMPLE = "Ek To-Do list web app banao jisme user task add, delete, aur 'complete' mark kar sake. User login/signup bhi ho."

function App() {
  const [requirement, setRequirement] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [stages, setStages] = useState(initialStages)
  const [streams, setStreams] = useState(emptyStreams)
  const [devTasks, setDevTasks] = useState([])
  const [devProgress, setDevProgress] = useState({ done: 0, total: 0 })
  const [doneRunId, setDoneRunId] = useState(null)       // latest successful run (download / refine)
  const [refineHistory, setRefineHistory] = useState([])
  const [error, setError] = useState('')
  const sourceRef = useRef(null)
  const runIdRef = useRef(null)   // the run in progress, if any

  const closeStream = () => {
    sourceRef.current?.close()
    sourceRef.current = null
  }

  // Close the SSE connection if the component unmounts mid-run
  useEffect(() => closeStream, [])

  // Leaving the page cancels the run in progress, so it stops using LLM quota.
  // keepalive lets the request finish even while the page is unloading.
  useEffect(() => {
    const onPageHide = () => {
      if (runIdRef.current) cancelRun(runIdRef.current, { keepalive: true }).catch(() => {})
    }
    window.addEventListener('pagehide', onPageHide)
    return () => window.removeEventListener('pagehide', onPageHide)
  }, [])

  const finish = (errorMessage) => {
    runIdRef.current = null
    closeStream()
    setLoading(false)
    setStreams(emptyStreams())
    if (errorMessage) {
      setError(errorMessage)
      setStages((s) => Object.fromEntries(
        Object.entries(s).map(([k, v]) => [k, v === 'running' ? 'failed' : v]),
      ))
    }
  }

  // Subscribe to a run's live progress (Server-Sent Events)
  const listen = (runId) => {
    runIdRef.current = runId
    const es = new EventSource(eventsUrl(runId))
    sourceRef.current = es

    es.addEventListener('stage', (e) => {
      const event = JSON.parse(e.data)
      const { stage, status, data } = event
      setStages((s) => ({ ...s, [stage]: stageStatus(event) }))
      if (stage === 'developer') {
        if (status === 'started') {
          setDevTasks(data?.tasks || [])
          setDevProgress({ done: 0, total: data?.total || 0 })
        }
        if (status === 'progress') setDevProgress((p) => ({ ...p, done: p.done + 1 }))
      }
      if (status === 'delta' || status === 'progress' || status === 'done' || status === 'failed') {
        setStreams((st) => applyToStreams(st, event))
      }
      if (status !== 'delta') setResult((r) => applyToResult(r || {}, event))
    })
    es.addEventListener('done', async () => {
      // The final report also carries the run metrics (timeline, tokens, cost)
      try {
        const run = await getRun(runId)
        setResult(run.result)
        setDoneRunId(runId)
        finish()
      } catch (e) {
        finish(e.message)
      }
    })
    es.addEventListener('failed', (e) => finish(JSON.parse(e.data).message))
    es.addEventListener('cancelled', () => finish('Run cancelled.'))
    // Network blips: EventSource reconnects by itself (resuming via Last-Event-ID).
    // It only gives up (CLOSED) on a hard failure such as a 404.
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) finish('Lost connection to the server.')
    }
  }

  const handleGenerate = async () => {
    if (!requirement.trim()) { setError('Pehle requirement likho.'); return }
    closeStream()
    setError(''); setLoading(true); setResult(null); setDoneRunId(null); setRefineHistory([])
    setStages(initialStages()); setStreams(emptyStreams()); setDevTasks([]); setDevProgress({ done: 0, total: 0 })
    try {
      const { run_id: runId } = await startRun(requirement)
      listen(runId)
    } catch (e) {
      finish(e.message)
    }
  }

  const handleRefine = async (instruction, target) => {
    if (!doneRunId) return
    setError(''); setLoading(true)
    // Only the refined part re-runs; every other stage keeps the parent's result
    const rerun = REFINE_STAGES[target]
    setStages((s) => Object.fromEntries(Object.keys(s).map((k) => [k, rerun.includes(k) ? 'pending' : s[k]])))
    try {
      const { run_id: runId } = await refineRun(doneRunId, instruction, target)
      setRefineHistory((h) => [...h, { instruction, target }])
      listen(runId)
    } catch (e) {
      finish(e.message)
    }
  }

  const handleCancel = async () => {
    const runId = runIdRef.current
    if (!runId) return
    // The server confirms with a "cancelled" SSE event, which calls finish()
    try {
      await cancelRun(runId)
    } catch (e) {
      if (e.status === 409) finish()   // it had already finished
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
        <p className="tagline">// requirement → plan · design · code · preview · review · fix · tests</p>
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
          {loading ? (
            <button className="btn-ghost" onClick={handleCancel}>Cancel</button>
          ) : (
            <button className="btn-ghost" onClick={() => setRequirement(EXAMPLE)}>Try Example</button>
          )}
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
        <StandardsPanel disabled={loading} />
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
                    title={status === 'skipped' ? 'No high-severity findings, so nothing to fix' : undefined}
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
                  // Several agents can run at once (parallel Developer tasks, Preview, Reviewer + QA)
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

      {/* ---- Results (each section appears as soon as its agent has output) ---- */}
      {result && (
        <Results
          data={result}
          streams={streams}
          devTasks={devTasks}
          runId={doneRunId}
          busy={loading}
          onRefine={handleRefine}
          refineHistory={refineHistory}
        />
      )}
    </div>
  )
}

export default App
