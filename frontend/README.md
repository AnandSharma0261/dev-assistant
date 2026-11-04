# dev.assistant: frontend

React + Vite UI for the multi-agent dev assistant. Setup, architecture and
design decisions are in the [main README](../readme.md).

```bash
npm ci
npm run dev      # talks to the backend at http://localhost:8000 (override with VITE_API_URL)
npm run lint
npm run build
```

Layout: `src/App.jsx` (run lifecycle), `src/runEvents.js` (SSE events -> UI
state), `src/components/` (pipeline graph, tabs, preview, history, ...),
`src/index.css` (design tokens for the light and dark themes).
