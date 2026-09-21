import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { GoogleOAuthProvider } from '@react-oauth/google'

// Self-hosted variable fonts. Each package ships Cyrillic subsets, which the
// Bulgarian UI needs and most "default" web fonts do not carry.
import '@fontsource-variable/onest'
import '@fontsource-variable/manrope'
import '@fontsource-variable/jetbrains-mono'

import './index.css'
import App from './App.tsx'
import { GOOGLE_CLIENT_ID } from './config/google'
import ErrorBoundary from './components/ErrorBoundary'
import { installGlobalErrorHandlers } from './utils/errorLogger'
import { installBugReportErrorCapture } from './components/BugReportButton'

installGlobalErrorHandlers()
installBugReportErrorCapture()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        <App />
      </GoogleOAuthProvider>
    </ErrorBoundary>
  </StrictMode>,
)
