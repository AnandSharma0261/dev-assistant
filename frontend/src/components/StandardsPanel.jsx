import { useEffect, useRef, useState } from 'react'
import { getStandards, resetStandards, uploadStandards } from '../api'

const TOKEN_KEY = 'devassistant.adminToken'
const loadToken = () => { try { return sessionStorage.getItem(TOKEN_KEY) || '' } catch { return '' } }
const saveToken = (t) => { try { sessionStorage.setItem(TOKEN_KEY, t) } catch { /* ignore */ } }

/**
 * Which coding standards RAG uses. Replacing them affects every user, so the
 * server only allows it with its ADMIN_TOKEN (kept in this tab's sessionStorage).
 */
export default function StandardsPanel({ disabled }) {
  const [open, setOpen] = useState(false)
  const [info, setInfo] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [token, setToken] = useState(loadToken)
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

  // Load the summary once so the collapsed header can show it
  useEffect(() => { run(getStandards) }, [])

  const onFile = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (file.size > 100_000) { setMessage('File is too large (max 100 KB).'); return }
    const text = await file.text()
    run(() => uploadStandards(text, token))
  }

  return (
    <div className="standards-panel">
      <button className="link-btn standards-toggle" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {open ? '▾' : '▸'} Coding standards
        {info && <span className="dim"> · {info.source === 'custom' ? 'custom' : 'built-in'} · {info.rules.length} rules</span>}
      </button>
      {open && info && (
        <div className="standards-body">
          <ul className="rule-chips">
            {info.rules.map((r) => (
              <li key={r.title} className={r.always_on ? 'always' : ''} title={r.always_on ? 'Applied to every file' : 'Retrieved when relevant (RAG)'}>
                {r.title}{r.always_on && <span className="chip-tag">always</span>}
              </li>
            ))}
          </ul>
          {info.editable ? (
            <>
              <p className="dim small">
                Upload Markdown/text: one <code>## Heading</code> per rule; end a heading with <code>[always]</code> for
                rules that apply to every file. Applies to all users of this server.
              </p>
              <input
                className="input input-sm"
                type="password"
                placeholder="Admin token"
                value={token}
                autoComplete="off"
                onChange={(e) => { setToken(e.target.value); saveToken(e.target.value) }}
              />
              <div className="btn-row left">
                <input ref={fileRef} type="file" accept=".md,.markdown,.txt,text/plain,text/markdown" hidden onChange={onFile} />
                <button className="btn-ghost btn-sm" disabled={busy || disabled || !token} onClick={() => fileRef.current?.click()}>
                  {busy ? 'Indexing…' : 'Upload standards'}
                </button>
                {info.source === 'custom' && (
                  <button className="btn-ghost btn-sm" disabled={busy || disabled || !token} onClick={() => run(() => resetStandards(token))}>
                    Reset to built-in
                  </button>
                )}
              </div>
            </>
          ) : (
            <p className="dim small">Uploading standards is turned off on this server (set ADMIN_TOKEN to enable it).</p>
          )}
        </div>
      )}
      {message && <p className="error">{message}</p>}
    </div>
  )
}
