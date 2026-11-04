import { useState } from 'react'
import { SyntaxHighlighter, oneDark } from '../highlight'
import { cleanCode, codeStyle, codeTagProps, prismLanguage } from '../code'

/**
 * One generated file. `output` is the finished file (may be undefined while it
 * is still being written); `streaming` is text arriving right now, and
 * `streamingLabel` says what is producing it ("writing…" / "fixing…").
 */
export default function CodeBlock({ output, task, streaming, streamingLabel }) {
  const [showOriginal, setShowOriginal] = useState(false)
  const [copied, setCopied] = useState(false)
  const live = streaming !== undefined
  const revision = output?.revision
  const code = live ? streaming : cleanCode(showOriginal && revision ? revision.original_code : output?.code)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard blocked: nothing to do */ }
  }

  return (
    <div className={`code-block ${live ? 'is-streaming' : ''}`}>
      <div className="code-title">
        <span className="code-file">{output?.filename || 'untitled'}</span>
        <span className="dim small">{output?.task || task}{output?.language ? ` · ${output.language}` : ''}</span>
        <span className="code-actions">
          {live && <span className="live-tag">● {streamingLabel}</span>}
          {!live && revision && (
            <>
              <span className="tag tag-success">✓ revised</span>
              <button className="link-btn" onClick={() => setShowOriginal((v) => !v)}>
                {showOriginal ? 'show revised' : 'show original'}
              </button>
            </>
          )}
          {!live && <button className="link-btn" onClick={copy}>{copied ? 'copied' : 'copy'}</button>}
        </span>
      </div>
      {!live && revision?.addressed?.length > 0 && (
        <ul className="addressed">
          {revision.addressed.map((a) => <li key={a}>{a}</li>)}
        </ul>
      )}
      <SyntaxHighlighter
        language={prismLanguage(output?.language)}
        style={oneDark}
        customStyle={codeStyle}
        codeTagProps={codeTagProps}
      >
        {code + (live ? '▍' : '')}
      </SyntaxHighlighter>
      {!live && output?.notes && <p className="dim small code-notes">ℹ {output.notes}</p>}
    </div>
  )
}
