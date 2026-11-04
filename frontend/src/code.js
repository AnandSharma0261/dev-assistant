// Shared helpers for showing generated code
import { KNOWN_LANGUAGES } from './highlight'

// Map the Developer's language id to a registered Prism grammar
const PRISM_ALIASES = {
  html: 'markup', xml: 'markup', svg: 'markup', js: 'javascript', node: 'javascript', nodejs: 'javascript',
  ts: 'typescript', py: 'python', sh: 'bash', shell: 'bash', zsh: 'bash', yml: 'yaml',
}
export function prismLanguage(lang) {
  const key = (lang || 'javascript').toLowerCase()
  const name = PRISM_ALIASES[key] || key
  return KNOWN_LANGUAGES.has(name) ? name : 'text'
}

// Older reports stored code with markdown fences (```); strip them for display
export function cleanCode(raw) {
  if (!raw) return ''
  return raw.trim().replace(/^```[a-zA-Z]*\n?/, '').replace(/\n?```$/, '').trim()
}

export const codeStyle = {
  borderRadius: 12, fontSize: 13, margin: 0, background: 'var(--code-bg)', maxHeight: 560, padding: '14px 16px',
}
// The theme also paints the inner <code>; that showed up as a box behind every line
export const codeTagProps = { style: { background: 'transparent', fontFamily: 'var(--mono)' } }
