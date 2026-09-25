import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const CONSENT_PATH = '/consent';

/**
 * Route guard for everything behind login.
 *
 * Previously every page (/dashboard, /progress, /grades, /nvo/practice, ...)
 * rendered for anonymous visitors, who then saw a broken shell firing 401s.
 * Anonymous visitors are now sent to /, remembering where they wanted to go
 * so the auth page can bounce them back (see utils/redirect.ts).
 */
export default function RequireAuth() {
  const location = useLocation();
  const { isAuthenticated, user } = useAuth();
  const here = location.pathname + location.search;

  if (!isAuthenticated) {
    return <Navigate to="/" replace state={{ from: here }} />;
  }

  // Signed in but the age / consent step is still owed: nothing else until
  // it is answered, then back to where they were going.
  if (user?.consentRequired && location.pathname !== CONSENT_PATH) {
    return <Navigate to={CONSENT_PATH} replace state={{ from: here }} />;
  }

  return <Outlet />;
}
