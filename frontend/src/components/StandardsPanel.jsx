import { useRef, useState } from 'react'
import { getStandards, resetStandards, uploadStandards } from '../api'

/** Shows which coding standards RAG uses, and lets you upload your own document. */
export default function StandardsPanel({ disabled }) {
  const [open, setOpen] = useState(false)
  const [info, setInfo] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const fileRef = useRef(null)

  const run = async (fn) => {
    setBusy(true); setMessage('')
    try {
      setInfo(await fn())
    } catch (e) {
      setMessage(e.message)
    } finally {
      setBusy(false)
    }
  }

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next && !info) run(getStandards)
  }

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (file.size > 100_000) { setMessage('File is too large (max 100 KB).'); return }
    const text = await file.text()
    run(() => uploadStandards(text))
  }

  return (
    <div className="standards-panel">
      <button className="link-btn" onClick={toggle} aria-expanded={open}>
        {open ? '▾' : '▸'} Coding standards
        {info && <span className="dim"> · {info.source === 'custom' ? 'your document' : 'built-in'} · {info.rules.length} rules</span>}
      </button>
      {open && (
        <div className="standards-body">
          {info && (
            <ul className="rule-chips">
              {info.rules.map((r) => (
                <li key={r.title} className={r.always_on ? 'always' : ''} title={r.always_on ? 'Applied to every file' : 'Retrieved when relevant'}>
                  {r.title}{r.always_on && <span className="mono"> always</span>}
                </li>
              ))}
            </ul>
          )}
          <p className="dim small">
            Upload a Markdown/text file: one <code>## Heading</code> per rule. End a heading with{' '}
            <code>[always]</code> for rules that apply to every file; the rest are retrieved per task (RAG).
          </p>
          <div className="btn-row left">
            <input ref={fileRef} type="file" accept=".md,.markdown,.txt,text/plain,text/markdown" hidden onChange={onFile} />
            <button className="btn-ghost" disabled={busy || disabled} onClick={() => fileRef.current?.click()}>
              {busy ? 'Indexing…' : 'Upload your standards'}
            </button>
            {info?.source === 'custom' && (
              <button className="btn-ghost" disabled={busy || disabled} onClick={() => run(resetStandards)}>
                Reset to built-in
              </button>
            )}
          </div>
          {message && <p className="error">{message}</p>}
        </div>
      )}
    </div>
  )
}
