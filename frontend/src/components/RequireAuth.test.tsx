import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';

import RequireAuth from './RequireAuth';

const auth = vi.hoisted(() => ({
  value: { isAuthenticated: false, user: null as null | { consentRequired: boolean } },
}));
vi.mock('../context/AuthContext', () => ({ useAuth: () => auth.value }));

function Where({ label }: { label: string }) {
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? '';
  return <p>{label} from={from}</p>;
}

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<Where label="sign-in" />} />
        <Route element={<RequireAuth />}>
          <Route path="/consent" element={<Where label="consent" />} />
          <Route path="/dashboard" element={<Where label="dashboard" />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe('RequireAuth', () => {
  it('sends a signed-out visitor to sign in, remembering where they were going', () => {
    auth.value = { isAuthenticated: false, user: null };
    renderAt('/dashboard?tab=1');
    expect(screen.getByText('sign-in from=/dashboard?tab=1')).toBeInTheDocument();
  });

  it('sends an account that owes the consent step to /consent first', () => {
    auth.value = { isAuthenticated: true, user: { consentRequired: true } };
    renderAt('/dashboard');
    expect(screen.getByText('consent from=/dashboard')).toBeInTheDocument();
  });

  it('lets the consent page itself render instead of redirecting forever', () => {
    auth.value = { isAuthenticated: true, user: { consentRequired: true } };
    renderAt('/consent');
    expect(screen.getByText(/^consent/)).toBeInTheDocument();
  });

  it('lets an account that has answered through', () => {
    auth.value = { isAuthenticated: true, user: { consentRequired: false } };
    renderAt('/dashboard');
    expect(screen.getByText(/^dashboard/)).toBeInTheDocument();
  });
});
