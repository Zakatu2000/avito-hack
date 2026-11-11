import '@fontsource/manrope/400.css'
import '@fontsource/manrope/500.css'
import '@fontsource/manrope/600.css'
import '@fontsource/manrope/700.css'
import '@fontsource/manrope/800.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from './App'
import { enableApiMock } from './mocks/browser'
import './design/tokens.css'
import './styles/global.css'
import './styles/ui.css'

void enableApiMock()
  .catch(() => undefined)
  .finally(() => {
    const container = document.getElementById('root')
    if (!container) throw new Error('root container not found')
    createRoot(container).render(
      <StrictMode>
        <App />
      </StrictMode>,
    )
  })
