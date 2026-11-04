import { STAGES } from '../runEvents'

const LABEL = Object.fromEntries(STAGES.map((s) => [s.key, s.label]))
const secs = (ms) => `${(ms / 1000).toFixed(1)}s`
const fmtTokens = (n) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n))
const fmtCost = (usd) => (usd == null ? 'n/a' : usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(3)}`)

/** Run stats: when each stage ran (Gantt bars) plus per-agent calls, tokens and cost. */
export default function Timeline({ metrics }) {
  const { total_ms: total, sequential_ms: sequential, speedup, stages, llm_calls: calls, totals } = metrics

  const byAgent = {}
  for (const c of calls) {
    const a = (byAgent[c.agent] ||= { calls: 0, ms: 0, input: 0, output: 0, cost: 0, unknownCost: false })
    a.calls += 1
    a.ms += c.duration_ms
    a.input += c.input_tokens
    a.output += c.output_tokens
    if (c.cost_usd == null) a.unknownCost = true
    else a.cost += c.cost_usd
  }

  return (
    <div className="timeline">
      <div className="stat-row">
        <div className="stat"><span className="stat-value">{secs(total)}</span><span className="dim">total</span></div>
        {speedup > 1 && (
          <div className="stat">
            <span className="stat-value">{speedup}×</span>
            <span className="dim">faster than sequential ({secs(sequential)})</span>
          </div>
        )}
        <div className="stat"><span className="stat-value">{totals.calls}</span><span className="dim">LLM calls{totals.retries ? ` · ${totals.retries} retried` : ''}</span></div>
        <div className="stat"><span className="stat-value">{fmtTokens(totals.input_tokens + totals.output_tokens)}</span><span className="dim">tokens</span></div>
        <div className="stat"><span className="stat-value">{fmtCost(totals.cost_usd)}</span><span className="dim">est. cost at paid rates</span></div>
      </div>

      <div className="gantt">
        {stages.map((s) => {
          const end = s.end_ms ?? total
          return (
            <div className="gantt-row" key={s.stage}>
              <span className="gantt-label">{LABEL[s.stage] || s.stage}</span>
              <div className="gantt-track">
                <div
                  className="gantt-bar"
                  style={{ background: `var(--agent-${s.stage})`, left: `${(s.start_ms / total) * 100}%`, width: `${Math.max(((end - s.start_ms) / total) * 100, 0.8)}%` }}
                  title={`${secs(s.start_ms)} → ${secs(end)}`}
                />
              </div>
              <span className="gantt-time dim">{secs(end - s.start_ms)}</span>
            </div>
          )
        })}
      </div>

      <table className="agent-table">
        <thead>
          <tr><th>Agent</th><th>Calls</th><th>LLM time</th><th>Tokens in / out</th><th>Est. cost</th></tr>
        </thead>
        <tbody>
          {Object.entries(byAgent).map(([agent, a]) => (
            <tr key={agent}>
              <td>{LABEL[agent] || agent}</td>
              <td>{a.calls}</td>
              <td>{secs(a.ms)}</td>
              <td>{fmtTokens(a.input)} / {fmtTokens(a.output)}</td>
              <td>{a.unknownCost ? 'n/a' : fmtCost(a.cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
