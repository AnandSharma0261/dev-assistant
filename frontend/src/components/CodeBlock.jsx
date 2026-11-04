import { useState } from 'react'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { cleanCode, codeStyle, prismLanguage } from '../code'

/**
 * One generated file. `output` is the finished file (may be undefined while it
 * is still being written); `streaming` is text arriving right now, and
 * `streamingLabel` says what is producing it ("writing…" / "fixing…").
 */
export default function CodeBlock({ output, task, streaming, streamingLabel }) {
  const [showOriginal, setShowOriginal] = useState(false)
  const live = streaming !== undefined
  const revision = output?.revision
  const code = live ? streaming : showOriginal && revision ? revision.original_code : output?.code

  return (
    <div className={`code-block ${live ? 'is-streaming' : ''}`}>
      <div className="code-title">
        {output?.filename && <span className="code-file">{output.filename}</span>}
        <span className="dim">{output?.task || task}{output?.language ? ` · ${output.language}` : ''}</span>
        {live && <span className="live-tag">● {streamingLabel}</span>}
        {!live && revision && (
          <>
            <span className="fixed-tag">✓ revised</span>
            <button className="link-btn" onClick={() => setShowOriginal((v) => !v)}>
              {showOriginal ? 'show revised' : 'show original'}
            </button>
          </>
        )}
      </div>
      {!live && revision?.addressed?.length > 0 && (
        <ul className="addressed">
          {revision.addressed.map((a) => <li key={a}>{a}</li>)}
        </ul>
      )}
      <SyntaxHighlighter language={prismLanguage(output?.language)} style={oneDark} customStyle={codeStyle}>
        {(live ? code : cleanCode(code)) + (live ? '▍' : '')}
      </SyntaxHighlighter>
      {!live && output?.notes && <p className="dim code-notes">ℹ {output.notes}</p>}
    </div>
  )
}
