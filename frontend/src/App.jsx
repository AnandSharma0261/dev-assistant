// ============================================================
//  dev.assistant — workspace layout
//  Left: requirement + history. Right: live agent graph + tabbed results.
// ============================================================

import { useCallback, useEffect, useRef, useState } from 'react'

// fonts (npm package se — internet par depend nahi)
import '@fontsource/inter/400.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/800.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/700.css'

import './App.css'
import { cancelRun, eventsUrl, getRun, listRuns, refineRun, startRun } from './api'
import {
  REFINE_STAGES, STAGES, applyToResult, applyToStreams, emptyStreams, initialStages, stageStatus, stagesFromResult,
} from './runEvents'
import HistoryPanel from './components/HistoryPanel'
import Pipeline from './components/Pipeline'
import ResultsTabs from './components/ResultsTabs'
import StandardsPanel from './components/StandardsPanel'

const EXAMPLES = [
  { label: 'Calculator', blurb: 'Keyboard support, decimals, clean UI', text: 'Ek simple calculator web app banao: + − × ÷, clear, backspace aur decimal support. Keyboard se bhi chale.' },
  { label: 'To-do + login', blurb: 'Auth, CRUD and a security review', text: "Ek To-Do list web app banao jisme user signup/login kare aur tasks add, delete aur 'complete' mark kar sake." },
  { label: 'Blog', blurb: 'Posts, editing and comments', text: 'Ek blog platform banao jisme author posts likh, edit aur publish kar sake, aur readers comment kar sakein.' },
  { label: 'Expense tracker', blurb: 'Categories and monthly totals', text: 'Ek expense tracker banao: expenses add karo category ke saath, monthly total aur category-wise breakdown dikhao.' },
]
const LABEL = Object.fromEntries(STAGES.map((s) => [s.key, s.label]))

const setUrlRun = (runId) => {
  const url = runId ? `?run=${runId}` : window.location.pathname
  window.history.replaceState(null, '', url)
}

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'dark')
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('devassistant.theme', next) } catch { /* ignore */ }
    setTheme(next)
  }
  return [theme, toggle]
}

function App() {
  const [theme, toggleTheme] = useTheme()
  const [requirement, setRequirement] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [resultKey, setResultKey] = useState(0)          // new run => fresh tab state
  const [stages, setStages] = useState(initialStages)
  const [times, setTimes] = useState({})                 // stage -> {start, end} for live timers
  const [streams, setStreams] = useState(emptyStreams)
  const [devTasks, setDevTasks] = useState([])
  const [devProgress, setDevProgress] = useState({ done: 0, total: 0 })
  const [currentId, setCurrentId] = useState(null)       // run shown on screen
  const [doneRunId, setDoneRunId] = useState(null)       // latest successful run (download / refine)
  const [refineHistory, setRefineHistory] = useState([])
  const [history, setHistory] = useState([])
  const [historyError, setHistoryError] = useState('')
  const [announcement, setAnnouncement] = useState('')   // for screen readers
  const [error, setError] = useState('')
  const sourceRef = useRef(null)
  const runIdRef = useRef(null)   // the run in progress, if any

  const refreshHistory = useCallback(async () => {
    try {
      setHistory((await listRuns()).items)
      setHistoryError('')
    } catch (e) {
      setHistoryError(e.message)
    }
  }, [])

  const closeStream = () => {
    sourceRef.current?.close()
    sourceRef.current = null
  }

  const resetView = () => {
    closeStream()
    setError(''); setResult(null); setDoneRunId(null); setRefineHistory([]); setTimes({})
    setStages(initialStages()); setStreams(emptyStreams()); setDevTasks([]); setDevProgress({ done: 0, total: 0 })
    setResultKey((k) => k + 1)
  }

  const finish = (errorMessage) => {
    runIdRef.current = null
    closeStream()
    setLoading(false)
    setStreams(emptyStreams())
    refreshHistory()
    if (errorMessage) {
      setError(errorMessage)
      setStages((s) => Object.fromEntries(Object.entries(s).map(([k, v]) => [k, v === 'running' ? 'failed' : v])))
    }
  }

  // Subscribe to a run's live progress (Server-Sent Events)
  const listen = (runId) => {
    runIdRef.current = runId
    setLoading(true)
    const es = new EventSource(eventsUrl(runId))
    sourceRef.current = es

    es.addEventListener('stage', (e) => {
      const event = JSON.parse(e.data)
      const { stage, status, data } = event
      const shown = stageStatus(event)
      setStages((s) => ({ ...s, [stage]: shown }))
      if (status === 'started') {
        setTimes((t) => ({ ...t, [stage]: { start: Date.now() } }))
        setAnnouncement(`${LABEL[stage]} started`)
      }
      if (status === 'done' || status === 'failed') {
        setTimes((t) => ({ ...t, [stage]: { start: t[stage]?.start ?? Date.now(), end: Date.now() } }))
        setAnnouncement(`${LABEL[stage]} ${shown}`)
      }
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
        setAnnouncement('Run finished')
        finish()
      } catch (e) {
        finish(e.message)
      }
    })
    es.addEventListener('failed', (e) => finish(JSON.parse(e.data).message))
    es.addEventListener('cancelled', () => finish('Run cancelled.'))
    // Network blips: EventSource reconnects by itself (resuming via Last-Event-ID).
    // It only gives up (CLOSED) on a hard failure such as a 404/410.
    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) finish('Lost connection to the server.')
    }
  }

  // Open a run from history or from a ?run= link
  const openRun = useCallback(async (runId) => {
    if (runIdRef.current) return   // don't abandon a run in progress
    resetView()
    setCurrentId(runId)
    setUrlRun(runId)
    try {
      const run = await getRun(runId)
      setRequirement(run.requirement)
      if (run.instruction) setRefineHistory([{ instruction: run.instruction, target: run.result?.refinement?.target || '' }])
      if (run.status === 'queued' || run.status === 'running') {
        setResult({})
        listen(runId)   // events replay from the start, then continue live
      } else if (run.status === 'done' && run.result) {
        setResult(run.result)
        setStages(stagesFromResult(run.result))
        setDoneRunId(runId)
      } else {
        setError(run.error || `This run ${run.status}.`)
      }
    } catch (e) {
      setError(e.status === 404 ? 'Run not found.' : e.message)
      setUrlRun(null)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Close the SSE connection if the component unmounts mid-run
  useEffect(() => closeStream, [])

  // First load: history, plus the run in the URL if there is one
  useEffect(() => {
    refreshHistory()
    const runId = new URLSearchParams(window.location.search).get('run')
    if (runId) openRun(runId)
  }, [refreshHistory, openRun])

  // Leaving the page cancels the run in progress, so it stops using LLM quota.
  // keepalive lets the request finish even while the page is unloading.
  useEffect(() => {
    const onPageHide = () => {
      if (runIdRef.current) cancelRun(runIdRef.current, { keepalive: true }).catch(() => {})
    }
    window.addEventListener('pagehide', onPageHide)
    return () => window.removeEventListener('pagehide', onPageHide)
  }, [])

  // `text` lets an example card start a run in one click (state updates are async)
  const handleGenerate = async (text = requirement) => {
    if (loading) return
    if (text.trim().length < 10) { setError('Requirement thoda detail mein likho (kam se kam 10 characters).'); return }
    resetView()
    setLoading(true)
    try {
      const { run_id: runId } = await startRun(text)
      setCurrentId(runId)
      setUrlRun(runId)
      listen(runId)
      refreshHistory()
    } catch (e) {
      finish(e.message)
    }
  }

  const handleRefine = async (instruction, target) => {
    if (!doneRunId || loading) return
    setError('')
    // Only the refined part re-runs; every other stage keeps the parent's result
    const rerun = REFINE_STAGES[target]
    setStages((s) => Object.fromEntries(Object.keys(s).map((k) => [k, rerun.includes(k) ? 'pending' : s[k]])))
    setTimes((t) => Object.fromEntries(Object.entries(t).filter(([k]) => !rerun.includes(k))))
    try {
      const { run_id: runId } = await refineRun(doneRunId, instruction, target)
      setRefineHistory((h) => [...h, { instruction, target }])
      setCurrentId(runId)
      setUrlRun(runId)
      listen(runId)
      refreshHistory()
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

  const handleNew = () => {
    if (runIdRef.current) return
    resetView()
    setCurrentId(null)
    setRequirement('')
    setUrlRun(null)
  }

  const running = STAGES.filter(({ key }) => stages[key] === 'running').map((s) => s.label)
  const statusText = loading
    ? running.length ? `${running.join(' + ')} working${running.length > 1 ? ' in parallel' : ''}…` : 'Starting…'
    : doneRunId ? 'Finished' : error ? 'Stopped' : 'Idle'

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">◆</span>
          <span className="brand-name">dev<span className="accent">.assistant</span></span>
          <span className="tagline">a team of AI agents: plan · design · code · preview · review · fix · test</span>
        </div>
        <button className="icon-btn" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
          {theme === 'dark' ? '☀︎' : '☾'}
        </button>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <section className="panel composer" aria-label="Requirement">
            <label className="label" htmlFor="requirement">What should the team build?</label>
            <textarea
              id="requirement"
              className="textarea"
              rows={6}
              placeholder="e.g. Ek blog website banao jisme user post likh sake…"
              value={requirement}
              maxLength={4000}
              onChange={(e) => setRequirement(e.target.value)}
              onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleGenerate() }}
            />
            <div className="chips" aria-label="Examples">
              {EXAMPLES.map((ex) => (
                <button key={ex.label} className="chip" disabled={loading} onClick={() => setRequirement(ex.text)}>{ex.label}</button>
              ))}
            </div>
            <div className="btn-row">
              <span className="dim small hint">⌘/Ctrl + Enter</span>
              {loading && <button className="btn-ghost" onClick={handleCancel}>Cancel</button>}
              <button className="btn-primary" onClick={() => handleGenerate()} disabled={loading}>
                {loading ? 'Running…' : 'Generate'}
              </button>
            </div>
            {error && <p className="error" role="alert">{error}</p>}
            <StandardsPanel disabled={loading} />
          </section>

          <HistoryPanel items={history} activeId={currentId} onOpen={openRun} onNew={handleNew} error={historyError} />
        </aside>

        <main className="main">
          <section className="panel pipeline-panel" aria-label="Agent pipeline">
            <div className="panel-head">
              <h2>Agent pipeline</h2>
              <span className={`run-status ${loading ? 'is-live' : ''}`}>{statusText}</span>
            </div>
            <Pipeline stages={stages} times={times} devProgress={devProgress} />
            <p className="sr-only" aria-live="polite">{announcement}</p>
          </section>

          {result ? (
            <ResultsTabs
              key={resultKey}
              data={result}
              streams={streams}
              devTasks={devTasks}
              stages={stages}
              runId={doneRunId}
              busy={loading}
              onRefine={handleRefine}
              refineHistory={refineHistory}
            />
          ) : (
            <section className="panel empty">
              <h2>Describe an app, watch the team build it</h2>
              <p className="dim">Write your own requirement on the left, or try one of these:</p>
              <div className="example-cards">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex.label}
                    className="example-card"
                    onClick={() => { setRequirement(ex.text); handleGenerate(ex.text) }}
                  >
                    <strong>{ex.label}</strong>
                    <span className="dim small">{ex.blurb}</span>
                    <span className="example-go">Run →</span>
                  </button>
                ))}
              </div>
              <h3 className="subhead">What you'll see</h3>
              <ul className="feature-list">
                <li><strong>Live</strong> — every agent streams its work; code appears as it is typed.</li>
                <li><strong>Parallel</strong> — independent agents run side by side, as the graph shows.</li>
                <li><strong>Self-correcting</strong> — review findings go back to the developer, then get re-checked.</li>
                <li><strong>Clickable prototype</strong> — runs in a locked-down sandbox; refine it in plain words.</li>
                <li><strong>Your rules</strong> — company coding standards are retrieved per task (RAG).</li>
              </ul>
            </section>
          )}
        </main>
      </div>
    </div>
  )
}

export default App
