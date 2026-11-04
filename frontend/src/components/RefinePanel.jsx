import { useState } from 'react'

const TARGETS = [
  { key: 'preview', label: 'Preview', hint: 'e.g. "buttons gol kar do, dark mode add karo"' },
  { key: 'code', label: 'Code', hint: 'e.g. "rate limiting add karo, sab endpoints mein input validation"' },
]

/** Follow-up request on a finished run: regenerates only the chosen part. */
export default function RefinePanel({ onRefine, disabled, history }) {
  const [instruction, setInstruction] = useState('')
  const [target, setTarget] = useState('preview')
  const hint = TARGETS.find((t) => t.key === target).hint

  const submit = (e) => {
    e.preventDefault()
    if (instruction.trim().length < 3) return
    onRefine(instruction.trim(), target)
    setInstruction('')
  }

  return (
    <form className="refine" onSubmit={submit}>
      <div className="refine-head">
        <span className="label">$ refine</span>
        <div className="segmented" role="radiogroup" aria-label="What to change">
          {TARGETS.map((t) => (
            <button
              type="button"
              key={t.key}
              role="radio"
              aria-checked={target === t.key}
              className={target === t.key ? 'active' : ''}
              onClick={() => setTarget(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="refine-row">
        <input
          className="refine-input"
          placeholder={hint}
          value={instruction}
          maxLength={2000}
          onChange={(e) => setInstruction(e.target.value)}
          disabled={disabled}
        />
        <button className="btn-primary" type="submit" disabled={disabled || instruction.trim().length < 3}>
          Apply
        </button>
      </div>
      {history.length > 0 && (
        <ol className="refine-history dim">
          {history.map((h, i) => <li key={i}><span className="mono">[{h.target}]</span> {h.instruction}</li>)}
        </ol>
      )}
    </form>
  )
}
