// ============================================================
//  Phase 7: Frontend — "Midnight IDE" theme
//  Framer Motion (animations) + react-syntax-highlighter (code)
// ============================================================

import { useState } from 'react'
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
const STAGES = ['Planner', 'Architect', 'Developer', 'Reviewer', 'QA']

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
  const [error, setError] = useState('')

  const handleGenerate = async () => {
    if (!requirement.trim()) { setError('Pehle requirement likho.'); return }
    setError(''); setLoading(true); setResult(null)
    try {
      const res = await fetch(`${API_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requirement, max_dev_tasks: 2 }),
      })
      if (!res.ok) throw new Error('Server ne ' + res.status + ' diya')
      const json = await res.json()
      setResult(json.data)
    } catch (e) {
      setError('Error: ' + e.message + ' — backend chal raha hai? (port 8000)')
    } finally {
      setLoading(false)
    }
  }

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

      {/* ---- Loading: animated agent pipeline ---- */}
      <AnimatePresence>
        {loading && (
          <motion.div
            className="loader"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          >
            <div className="pipeline">
              {STAGES.map((s, i) => (
                <motion.div
                  key={s}
                  className="stage"
                  animate={{ opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
                  transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.22 }}
                >
                  {s}
                </motion.div>
              ))}
            </div>
            <p className="loader-text">AI team kaam kar rahi hai… thoda time lagega ⏳</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ---- Results ---- */}
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
      <motion.section className="card" variants={item}>
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
      </motion.section>

      {/* Architecture */}
      <motion.section className="card" variants={item}>
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
      </motion.section>

      {/* Generated code */}
      <motion.section className="card" variants={item}>
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
      </motion.section>

      {/* Review */}
      <motion.section className="card" variants={item}>
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
      </motion.section>

      {/* Tests */}
      <motion.section className="card" variants={item}>
        <h2><span className="h-mark">▸</span> Test Cases</h2>
        <ul className="test-list">
          {data.tests?.test_cases?.map((tc) => (
            <li key={tc.id}>
              <strong>{tc.title}</strong>
              <div className="dim">✅ {tc.expected}</div>
            </li>
          ))}
        </ul>
      </motion.section>
    </motion.div>
  )
}

export default App
