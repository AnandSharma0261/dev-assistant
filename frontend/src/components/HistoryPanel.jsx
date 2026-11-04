const STATUS_LABEL = { done: 'done', failed: 'failed', cancelled: 'cancelled', running: 'running', queued: 'queued' }

function timeAgo(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

/** This browser's past runs; refinements are nested under the run they refined. */
export default function HistoryPanel({ items, activeId, onOpen, onNew, error }) {
  const ids = new Set(items.map((r) => r.id))
  const children = {}
  for (const r of items) if (r.parent_id && ids.has(r.parent_id)) (children[r.parent_id] ||= []).push(r)
  const roots = items.filter((r) => !(r.parent_id && ids.has(r.parent_id)))

  const Row = ({ run, child }) => (
    <li>
      <button
        className={`history-item ${child ? 'is-child' : ''} ${run.id === activeId ? 'is-active' : ''}`}
        onClick={() => onOpen(run.id)}
        aria-current={run.id === activeId ? 'true' : undefined}
      >
        <span className={`status-dot status-${run.status}`} aria-label={STATUS_LABEL[run.status]} />
        <span className="history-text">
          {child ? <>↳ <em>{run.instruction}</em></> : run.requirement}
        </span>
        <span className="history-time">{timeAgo(run.created_at)}</span>
      </button>
      {!child && children[run.id] && (
        <ul>{[...children[run.id]].reverse().map((c) => <Row key={c.id} run={c} child />)}</ul>
      )}
    </li>
  )

  return (
    <section className="panel history" aria-label="History">
      <div className="panel-head">
        <h2>History</h2>
        <button className="btn-ghost btn-sm" onClick={onNew}>+ New</button>
      </div>
      {error && <p className="dim small">{error}</p>}
      {!error && items.length === 0 && <p className="dim small">Your runs will appear here.</p>}
      <ul className="history-list">
        {roots.map((r) => <Row key={r.id} run={r} />)}
      </ul>
    </section>
  )
}
