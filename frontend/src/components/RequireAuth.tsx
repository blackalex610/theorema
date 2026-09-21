import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

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
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/" replace state={{ from: location.pathname + location.search }} />;
  }

  return <Outlet />;
}
