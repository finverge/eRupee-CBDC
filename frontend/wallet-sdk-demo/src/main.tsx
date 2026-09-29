import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// SDK theme defaults MUST load before this app's own brand override
// (./index.css) — see wallet-sdk/README.md's embedding order note.
import '@sdk/theme.css'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
