import { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { codeStyle } from '../code'
import { item } from '../motion'

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

/** Runs the Preview agent's HTML in a locked-down iframe; shows the HTML while it streams. */
export default function LivePreview({ html, streaming, children }) {
  const [showCode, setShowCode] = useState(false)
  const frameRef = useRef(null)
  const live = streaming != null

  return (
    <motion.section className="card" variants={item}>
      <div className="preview-head">
        <h2>
          <span className="h-mark">▸</span> Live Preview
          {live && <span className="live-tag">● {html ? 'updating…' : 'writing…'}</span>}
        </h2>
        {!live && html && (
          <div className="preview-actions">
            <button className="btn-ghost" onClick={() => setShowCode((v) => !v)}>
              {showCode ? 'Preview' : 'Code'}
            </button>
            <button className="btn-ghost" onClick={() => frameRef.current?.requestFullscreen?.()}>
              Full screen
            </button>
          </div>
        )}
      </div>
      {live || showCode ? (
        <div className="preview-code">
          <SyntaxHighlighter language="markup" style={oneDark} customStyle={codeStyle}>
            {(live ? streaming : html) + (live ? '▍' : '')}
          </SyntaxHighlighter>
        </div>
      ) : (
        <iframe
          ref={frameRef}
          className="preview-frame"
          title="Generated app preview"
          sandbox="allow-scripts allow-modals"
          srcDoc={withCsp(html)}
        />
      )}
      <p className="dim preview-note">
        Prototype runs in a sandbox: no network, no backend, data lives in memory.
      </p>
      {children}
    </motion.section>
  )
}
