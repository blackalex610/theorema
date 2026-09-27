import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google'

// Self-hosted variable fonts. Each package ships Cyrillic subsets, which the
// Bulgarian UI needs and most "default" web fonts do not carry.
import '@fontsource-variable/onest'
import '@fontsource-variable/manrope'
import '@fontsource-variable/jetbrains-mono'

import './index.css'
// Loaded after index.css so its rules win the cascade. Every rule inside is
// scoped to `html.plain-ui`, so without the class below the file does nothing.
import './styles/plain.css'
import App from './App.tsx'
import { GOOGLE_CLIENT_ID } from './config/google'
import { PLAIN_UI } from './config/plainMode'
import ErrorBoundary from './components/ErrorBoundary'
import { installGlobalErrorHandlers } from './utils/errorLogger'
import { installBugReportErrorCapture } from './components/BugReportButton'

installGlobalErrorHandlers()
installBugReportErrorCapture()

if (PLAIN_UI) {
  document.documentElement.classList.add('plain-ui')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <App />
      </GoogleOAuthProvider>
    </ErrorBoundary>
  </StrictMode>,
)
