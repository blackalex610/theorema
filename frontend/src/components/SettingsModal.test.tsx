import { describe, it, expect, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import SettingsModal from './SettingsModal';
import { SettingsProvider, OPEN_SETTINGS_MODAL_EVENT } from '../context/SettingsContext';
import { DeveloperModeProvider } from '../context/DeveloperModeContext';

// The modal now hosts the "Моите данни" (export / delete account) section,
// which reads the auth session. Stubbed rather than wrapped in a real
// AuthProvider so this file stays about the modal's own contents.
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ signOut: vi.fn() }),
}));

// The "Език" section used to render a select with English/Bulgarian options
// that only ever set `document.documentElement.lang` — no string anywhere in
// the app was actually translated, so switching it did nothing a student
// could see. Offering a choice that has no effect is worse than offering
// none, so the control was removed rather than left to imply support that
// doesn't exist. (Real i18n is tracked separately as product work.)
function renderOpenSettingsModal() {
  render(
    <DeveloperModeProvider>
      <SettingsProvider>
        <SettingsModal />
      </SettingsProvider>
    </DeveloperModeProvider>
  );
  act(() => {
    window.dispatchEvent(new Event(OPEN_SETTINGS_MODAL_EVENT));
  });
}

describe('SettingsModal', () => {
  it('does not offer a language switch', () => {
    renderOpenSettingsModal();

    expect(screen.queryByText('Език')).not.toBeInTheDocument();
    expect(screen.queryByText('App language')).not.toBeInTheDocument();
  });

  it('still offers the working theme switch', () => {
    renderOpenSettingsModal();

    expect(screen.getByText('Външен вид')).toBeInTheDocument();
  });
});
