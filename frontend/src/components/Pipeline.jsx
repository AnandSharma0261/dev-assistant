import { useEffect, useState } from 'react'
import { EDGES, STAGES, STATUS_ICON } from '../runEvents'

const BY_KEY = Object.fromEntries(STAGES.map((s) => [s.key, s]))
const fmt = (ms) => (ms < 60000 ? `${Math.round(ms / 1000)}s` : `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`)

// A curved edge between two node centres (viewBox is 0..100 in both axes)
function edgePath(a, b) {
  const mx = (a.x + b.x) / 2
  return `M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`
}

/**
 * The agents as their real dependency graph: parallel branches sit side by
 * side, edges light up as work flows through them. `times` holds client-side
 * {start, end} per stage for the live timers.
 */
export default function Pipeline({ stages, times, devProgress, compact }) {
  const anyRunning = Object.values(stages).includes('running')
  const [, tick] = useState(0)
  useEffect(() => {
    if (!anyRunning) return undefined
    const id = setInterval(() => tick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [anyRunning])

  const subtitle = (key, status) => {
    if (key === 'developer' && devProgress.total > 0 && status !== 'pending') return `${devProgress.done}/${devProgress.total} files`
    if (status === 'skipped') return 'nothing to fix'
    const t = times[key]
    if (t?.start) return fmt((t.end ?? Date.now()) - t.start)
    return BY_KEY[key].desc
  }

  return (
    <div className={`dag ${compact ? 'dag-compact' : ''}`} role="list" aria-label="Agent pipeline">
      <svg className="dag-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {EDGES.map(([from, to]) => {
          const target = stages[to]
          const state = target === 'running' ? 'active' : target === 'done' || target === 'skipped' ? 'done' : 'idle'
          return (
            <path
              key={`${from}-${to}`}
              d={edgePath(BY_KEY[from], BY_KEY[to])}
              className={`edge edge-${state}`}
              style={{ '--edge-color': `var(--agent-${to})` }}
              vectorEffect="non-scaling-stroke"
            />
          )
        })}
      </svg>
      {STAGES.map(({ key, label, x, y }) => {
        const status = stages[key]
        return (
          <div
            key={key}
            role="listitem"
            className={`node node-${status}`}
            style={{ '--x': x, '--y': y, '--agent': `var(--agent-${key})` }}
            title={BY_KEY[key].desc}
          >
            <div className="node-head">
              <span className="node-dot" />
              <span className="node-label">{label}</span>
              <span className="node-icon" aria-label={status}>{STATUS_ICON[status]}</span>
            </div>
            <div className="node-sub">{subtitle(key, status)}</div>
          </div>
        )
      })}
    </div>
  )
}
