import { useState } from 'react'
import CodeBlock from './CodeBlock'
import LivePreview from './LivePreview'
import RefinePanel from './RefinePanel'
import Timeline from './Timeline'
import { downloadUrl } from '../api'

function SelfCorrection({ sc, files }) {
  const { before, after } = sc
  const rows = [
    ['High findings', before.High, after.High],
    ['Medium findings', before.Medium, after.Medium],
    ['Failed standards', before.standards_failed, after.standards_failed],
  ]
  return (
    <div className="callout callout-success">
      <div className="callout-title">🔁 Self-correction: findings went back to the Developer, then the Reviewer verified the fix</div>
      <div className="sc-grid">
        {rows.map(([label, b, a]) => (
          <div key={label} className="sc-item">
            <span className="dim small">{label}</span>
            <span className="mono">{b} → <strong className={a < b ? 'better' : a > b ? 'worse' : ''}>{a}</strong></span>
          </div>
        ))}
      </div>
      <div className="dim small">Revised: {sc.files_fixed.map((i) => files[i]?.filename || `file ${i + 1}`).join(', ')}</div>
    </div>
  )
}

const Section = ({ title, agent, children }) => (
  <section className="section" style={{ '--agent': `var(--agent-${agent})` }}>
    <h3 className="section-title">{title}</h3>
    {children}
  </section>
)

function PlanTab({ data }) {
  return (
    <>
      {data.plan && (
        <Section title="Plan" agent="planner">
          <ul className="item-list">
            {data.plan.tasks.map((t) => (
              <li key={t.id}>
                <span className={`badge ${t.priority?.toLowerCase()}`}>{t.priority}</span>
                <strong>{t.title}</strong>
                <div className="dim">{t.description}</div>
              </li>
            ))}
          </ul>
        </Section>
      )}
      {data.design && (
        <Section title="Architecture" agent="architect">
          <dl className="stack">
            {Object.entries(data.design.tech_stack || {}).map(([k, v]) => (
              <div key={k} className="stack-item">
                <dt>{k}</dt>
                <dd>{Array.isArray(v) ? v.join(', ') || '—' : v}</dd>
              </div>
            ))}
          </dl>
          {data.design.api_endpoints?.length > 0 && (
            <table className="data-table">
              <thead><tr><th>Method</th><th>Path</th><th>Purpose</th></tr></thead>
              <tbody>
                {data.design.api_endpoints.map((e) => (
                  <tr key={`${e.method} ${e.path}`}><td className="mono">{e.method}</td><td className="mono">{e.path}</td><td>{e.purpose}</td></tr>
                ))}
              </tbody>
            </table>
          )}
          {data.design.data_models?.length > 0 && (
            <ul className="model-list">
              {data.design.data_models.map((m) => (
                <li key={m.name}><strong className="mono">{m.name}</strong> <span className="dim">{m.fields.join(', ')}</span></li>
              ))}
            </ul>
          )}
        </Section>
      )}
    </>
  )
}

function ReviewTab({ review, sc, files }) {
  return (
    <Section title="Code review" agent="reviewer">
      {sc && <SelfCorrection sc={sc} files={files} />}
      {review.findings.length === 0 && <p className="dim">No findings.</p>}
      <ul className="item-list">
        {review.findings.map((f, i) => (
          <li key={i}>
            <span className={`badge ${f.severity?.toLowerCase()}`}>{f.severity}</span>
            <strong>{f.issue}</strong>
            {f.location && <div className="dim mono small">{files[f.file - 1]?.filename ? `${files[f.file - 1].filename} · ` : ''}{f.location}</div>}
            <div className="dim">💡 {f.suggestion}</div>
          </li>
        ))}
      </ul>
      {review.standards_check?.length > 0 && (
        <>
          <h4 className="subhead">Company standards</h4>
          <ul className="standards">
            {review.standards_check.map((c) => (
              <li key={c.standard} className={`standard-${c.status}`}>
                <span className="standard-icon">{c.status === 'pass' ? '✓' : '✕'}</span>
                <strong>{c.standard}</strong>
                <span className="dim"> — {c.note}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {review.overall_summary && <p className="summary">{review.overall_summary}</p>}
    </Section>
  )
}

function TestsTab({ tests }) {
  return (
    <Section title={`Test cases · ${tests.test_cases.length}`} agent="qa">
      <ul className="item-list">
        {tests.test_cases.map((tc) => (
          <li key={tc.id}>
            <details>
              <summary><strong>{tc.title}</strong></summary>
              {tc.steps?.length > 0 && <ol className="steps">{tc.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>}
            </details>
            <div className="dim">✅ {tc.expected}</div>
          </li>
        ))}
      </ul>
    </Section>
  )
}

const PENDING_TEXT = {
  preview: 'Preview agent is building the prototype…',
  code: 'Developer is writing the code…',
  plan: 'Planner and Architect are working…',
  review: 'Reviewer is checking the code…',
  tests: 'QA is writing test cases…',
}

function Skeleton({ text }) {
  return (
    <div className="skeleton" aria-busy="true">
      <p className="dim">{text}</p>
      {[92, 78, 85, 60].map((w) => <div key={w} className="skeleton-line" style={{ width: `${w}%` }} />)}
    </div>
  )
}

/** The report as tabs; a tab can be opened as soon as its agent starts (showing a placeholder until output arrives). */
export default function ResultsTabs({ data, streams, devTasks, stages, runId, busy, onRefine, refineHistory }) {
  const [userTab, setUserTab] = useState(null)
  const dev = data.dev_outputs || []
  const streamingIdx = [...Object.keys(streams.developer), ...Object.keys(streams.fix)].map(Number)
  const fileCount = Math.max(dev.length, ...streamingIdx.map((i) => i + 1), 0)
  const highs = data.review?.findings?.filter((f) => f.severity === 'High').length || 0
  const canRefine = Boolean(runId) && !busy

  const tabs = [
    { key: 'preview', label: 'Preview', agent: 'preview', ready: Boolean(data.preview?.html || streams.preview != null), running: stages.preview === 'running' },
    { key: 'code', label: 'Code', agent: 'developer', ready: fileCount > 0, running: stages.developer === 'running' || stages.fix === 'running', count: fileCount || null },
    { key: 'plan', label: 'Plan & design', agent: 'architect', ready: Boolean(data.plan), running: stages.planner === 'running' || stages.architect === 'running' },
    { key: 'review', label: 'Review', agent: 'reviewer', ready: Boolean(data.review), running: stages.reviewer === 'running', count: data.review ? (highs ? `${highs} high` : data.review.findings.length) : null, alert: highs > 0 },
    { key: 'tests', label: 'Tests', agent: 'qa', ready: Boolean(data.tests), running: stages.qa === 'running', count: data.tests?.test_cases.length },
    { key: 'timeline', label: 'Timeline', agent: 'fix', ready: Boolean(data.metrics), running: false },
  ]
  const openable = tabs.filter((t) => t.ready || t.running)
  // Follow the most interesting output until the user picks a tab themselves
  const active = openable.find((t) => t.key === userTab)?.key
    || tabs.find((t) => t.ready)?.key || openable[0]?.key
  const activeTab = tabs.find((t) => t.key === active)

  return (
    <section className="results panel" aria-label="Results">
      <div className="tabs-bar">
        <div className="tabs" role="tablist">
          {tabs.map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={active === t.key}
              disabled={!t.ready && !t.running}
              className={`tab ${active === t.key ? 'active' : ''}`}
              style={{ '--agent': `var(--agent-${t.agent})` }}
              onClick={() => setUserTab(t.key)}
            >
              {t.running && <span className="tab-pulse" aria-hidden="true" />}
              {t.label}
              {t.count != null && <span className={`tab-count ${t.alert ? 'alert' : ''}`}>{t.count}</span>}
            </button>
          ))}
        </div>
        {canRefine && <a className="btn-ghost btn-sm download" href={downloadUrl(runId)}>⬇ ZIP</a>}
      </div>

      <div className="tab-panel" role="tabpanel">
        {!active && <Skeleton text="Agents are starting… results appear here as each one works." />}
        {activeTab && !activeTab.ready && <Skeleton text={PENDING_TEXT[active]} />}

        {active === 'preview' && activeTab.ready && (
          <>
            <LivePreview html={data.preview?.html} streaming={streams.preview} />
            {(canRefine || refineHistory.length > 0) && (
              <RefinePanel key="preview" initialTarget="preview" onRefine={onRefine} disabled={!canRefine} history={refineHistory} />
            )}
          </>
        )}

        {active === 'code' && activeTab.ready && (
          <Section title={`Generated code · ${fileCount} file${fileCount === 1 ? '' : 's'}`} agent="developer">
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
            {(canRefine || refineHistory.length > 0) && (
              <RefinePanel key="code" initialTarget="code" onRefine={onRefine} disabled={!canRefine} history={refineHistory} />
            )}
          </Section>
        )}

        {active === 'plan' && activeTab.ready && <PlanTab data={data} />}
        {active === 'review' && activeTab.ready && <ReviewTab review={data.review} sc={data.self_correction} files={dev} />}
        {active === 'tests' && activeTab.ready && <TestsTab tests={data.tests} />}
        {active === 'timeline' && activeTab.ready && (
          <Section title="Run timeline" agent="fix"><Timeline metrics={data.metrics} /></Section>
        )}
      </div>
    </section>
  )
}
