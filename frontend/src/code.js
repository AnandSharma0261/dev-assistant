// Shared helpers for showing generated code

// Map the Developer's language id to a Prism grammar name
const PRISM_ALIASES = { html: 'markup', xml: 'markup', svg: 'markup', js: 'javascript', ts: 'typescript', py: 'python', sh: 'bash', shell: 'bash' }
export function prismLanguage(lang) {
  const key = (lang || 'javascript').toLowerCase()
  return PRISM_ALIASES[key] || key
}

// Older reports stored code with markdown fences (```); strip them for display
export function cleanCode(raw) {
  if (!raw) return ''
  return raw.trim().replace(/^```[a-zA-Z]*\n?/, '').replace(/\n?```$/, '').trim()
}

export const codeStyle = { borderRadius: 12, fontSize: 13, margin: 0, background: '#0d1117', maxHeight: 560 }
