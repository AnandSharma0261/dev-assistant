import { motion } from 'framer-motion'
import CodeBlock from './CodeBlock'
import LivePreview from './LivePreview'
import RefinePanel from './RefinePanel'
import Timeline from './Timeline'
import { container, item } from '../motion'
import { downloadUrl } from '../api'

const H = ({ children }) => <h2><span className="h-mark">▸</span> {children}</h2>

function SelfCorrection({ sc, files }) {
  const { before, after } = sc
  const rows = [
    ['High findings', before.High, after.High],
    ['Medium findings', before.Medium, after.Medium],
    ['Failed standards', before.standards_failed, after.standards_failed],
  ]
  return (
    <div className="self-correction">
      <div className="sc-title">🔁 Self-correction: reviewer findings went back to the Developer, then the fix was reviewed again</div>
      <div className="sc-grid">
        {rows.map(([label, b, a]) => (
          <div key={label} className="sc-item">
            <span className="dim">{label}</span>
            <span className="mono">{b} → <strong className={a < b ? 'better' : a > b ? 'worse' : ''}>{a}</strong></span>
          </div>
        ))}
      </div>
      <div className="dim small">Fixed: {sc.files_fixed.map((i) => files[i]?.filename || `file ${i + 1}`).join(', ')}</div>
    </div>
  )
}

/** All report sections; each appears as soon as its agent has something to show. */
export default function Results({ data, streams, devTasks, runId, busy, onRefine, refineHistory }) {
  const dev = data.dev_outputs || []
  const streamingIdx = [...Object.keys(streams.developer), ...Object.keys(streams.fix)].map(Number)
  const fileCount = Math.max(dev.length, ...streamingIdx.map((i) => i + 1), 0)
  const finished = Boolean(runId) && !busy

  return (
    <motion.div className="results" variants={container} initial="hidden" animate="show">
      {finished && (
        <motion.div className="result-actions" variants={item}>
          <a className="btn-ghost" href={downloadUrl(runId)}>⬇ Download ZIP</a>
        </motion.div>
      )}

      {(data.preview?.html || streams.preview != null) && (
        <LivePreview html={data.preview?.html} streaming={streams.preview}>
          {(finished || refineHistory.length > 0) && (
            <RefinePanel onRefine={onRefine} disabled={busy} history={refineHistory} />
          )}
        </LivePreview>
      )}

      {data.plan && (
        <motion.section className="card" variants={item}>
          <H>Plan</H>
          <ul className="task-list">
            {data.plan.tasks.map((t) => (
              <li key={t.id}>
                <span className={`badge ${t.priority?.toLowerCase()}`}>{t.priority}</span>
                <strong>{t.title}</strong>
                <div className="dim">{t.description}</div>
              </li>
            ))}
          </ul>
        </motion.section>
      )}

      {data.design && (
        <motion.section className="card" variants={item}>
          <H>Architecture</H>
          <div className="stack">
            {Object.entries(data.design.tech_stack || {}).map(([k, v]) => (
              <div key={k} className="stack-item">
                <span className="stack-key">{k}</span>
                <span>{Array.isArray(v) ? v.join(', ') : v}</span>
              </div>
            ))}
          </div>
        </motion.section>
      )}

      {fileCount > 0 && (
        <motion.section className="card" variants={item}>
          <H>Generated Code</H>
          {Array.from({ length: fileCount }, (_, i) => {
            const fixing = streams.fix[i]
            const writing = streams.developer[i]
            return (
              // index + task: separate tasks can pick the same filename (e.g. server.js)
              <CodeBlock
                key={`${i}-${dev[i]?.task || devTasks[i]}`}
                output={dev[i]}
                task={devTasks[i]}
                streaming={fixing ?? writing}
                streamingLabel={fixing !== undefined ? 'fixing review findings…' : 'writing…'}
              />
            )
          })}
        </motion.section>
      )}

      {data.review && (
        <motion.section className="card" variants={item}>
          <H>Code Review</H>
          {data.self_correction && <SelfCorrection sc={data.self_correction} files={dev} />}
          <ul className="findings">
            {data.review.findings.map((f, i) => (
              <li key={i}>
                <span className={`badge ${f.severity?.toLowerCase()}`}>{f.severity}</span>
                <strong>{f.issue}</strong>
                {f.location && <div className="dim mono">{dev[f.file - 1]?.filename ? `${dev[f.file - 1].filename} · ` : ''}{f.location}</div>}
                <div className="dim">💡 {f.suggestion}</div>
              </li>
            ))}
          </ul>
          {data.review.findings.length === 0 && <p className="dim">No findings.</p>}
          {data.review.standards_check?.length > 0 && (
            <>
              <h3 className="subhead">Company standards</h3>
              <ul className="standards">
                {data.review.standards_check.map((c) => (
                  <li key={c.standard} className={`standard-${c.status}`}>
                    <span className="standard-icon">{c.status === 'pass' ? '✓' : '✕'}</span>
                    <strong>{c.standard}</strong>
                    <span className="dim"> — {c.note}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {data.review.overall_summary && <p className="summary">{data.review.overall_summary}</p>}
        </motion.section>
      )}

      {data.tests && (
        <motion.section className="card" variants={item}>
          <H>Test Cases</H>
          <ul className="test-list">
            {data.tests.test_cases.map((tc) => (
              <li key={tc.id}>
                <strong>{tc.title}</strong>
                <div className="dim">✅ {tc.expected}</div>
              </li>
            ))}
          </ul>
        </motion.section>
      )}

      {data.metrics && <Timeline metrics={data.metrics} />}
    </motion.div>
  )
}
