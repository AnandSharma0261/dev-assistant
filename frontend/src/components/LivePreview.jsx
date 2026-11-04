import { useRef, useState } from 'react'
import { SyntaxHighlighter, oneDark } from '../highlight'
import { codeStyle, codeTagProps } from '../code'

// Generated prototypes are untrusted code. On top of the iframe sandbox
// (no allow-same-origin => opaque origin: no access to our cookies, storage
// or DOM), this CSP blocks every network request, so the code can't load
// or send anything. Inline styles/scripts and data: images still work.
const PREVIEW_CSP =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; form-action 'none'"

function withCsp(html) {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}">`
  // The CSP meta must come before any script, so put it at the start of <head>
  return /<head[^>]*>/i.test(html)
    ? html.replace(/<head[^>]*>/i, (m) => `${m}${meta}`)
    : `${meta}${html}`
}

// The model sometimes wraps the document in a ```html fence; the server strips
// it from the final HTML, so hide it from the live stream too
const stripFence = (text) => text.replace(/^\s*```[a-z]*\s*\n?/i, '').replace(/\n?```\s*$/, '')

const DEVICES = [
  { key: 'desktop', label: 'Desktop', width: '100%' },
  { key: 'tablet', label: 'Tablet', width: '768px' },
  { key: 'mobile', label: 'Mobile', width: '390px' },
]

/** Runs the Preview agent's HTML in a locked-down iframe; shows the HTML while it streams. */
export default function LivePreview({ html, streaming }) {
  const [showCode, setShowCode] = useState(false)
  const [device, setDevice] = useState('desktop')
  const [reloadKey, setReloadKey] = useState(0)
  const frameRef = useRef(null)
  const live = streaming != null
  const width = DEVICES.find((d) => d.key === device).width

  return (
    <div className="preview">
      <div className="toolbar">
        {live ? (
          <span className="live-tag">● {html ? 'updating prototype…' : 'writing prototype…'}</span>
        ) : (
          <>
            <div className="segmented" role="radiogroup" aria-label="Preview size">
              {DEVICES.map((d) => (
                <button key={d.key} role="radio" aria-checked={device === d.key}
                  className={device === d.key ? 'active' : ''} onClick={() => setDevice(d.key)}>
                  {d.label}
                </button>
              ))}
            </div>
            <div className="toolbar-actions">
              <button className="btn-ghost btn-sm" onClick={() => setReloadKey((k) => k + 1)}>Reload</button>
              <button className="btn-ghost btn-sm" onClick={() => setShowCode((v) => !v)}>{showCode ? 'Preview' : 'HTML'}</button>
              <button className="btn-ghost btn-sm" onClick={() => frameRef.current?.requestFullscreen?.()}>Full screen</button>
            </div>
          </>
        )}
      </div>
      {live || showCode ? (
        <SyntaxHighlighter language="markup" style={oneDark} customStyle={codeStyle} codeTagProps={codeTagProps}>
          {live ? stripFence(streaming) + '▍' : html}
        </SyntaxHighlighter>
      ) : (
        <div className="preview-stage">
          <iframe
            key={reloadKey}
            ref={frameRef}
            className="preview-frame"
            style={{ width }}
            title="Generated app preview"
            sandbox="allow-scripts allow-modals"
            srcDoc={withCsp(html)}
          />
        </div>
      )}
      <p className="dim small">Runs in a sandbox: no network, no backend; data lives in memory.</p>
    </div>
  )
}
