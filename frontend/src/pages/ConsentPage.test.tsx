import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import ConsentPage from './ConsentPage';

const recordConsent = vi.fn();
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: { ageGroup: null }, recordConsent, signOut: vi.fn() }),
}));

function renderPage() {
  render(
    <MemoryRouter initialEntries={[{ pathname: '/consent', state: { from: '/nvo/practice' } }]}>
      <Routes>
        <Route path="/consent" element={<ConsentPage />} />
        <Route path="/nvo/practice" element={<p>exam page</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const submit = () => screen.getByRole('button', { name: 'Продължи' });

describe('ConsentPage', () => {
  beforeEach(() => {
    recordConsent.mockReset().mockResolvedValue(undefined);
  });

  it('cannot be submitted until an age is chosen and the box is ticked', async () => {
    renderPage();
    expect(submit()).toBeDisabled();
    await userEvent.click(screen.getByLabelText('На 14 или повече години съм'));
    expect(submit()).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox'));
    expect(submit()).toBeEnabled();
  });

  it('asks a parent to confirm for an under-14 account, then continues', async () => {
    renderPage();
    await userEvent.click(screen.getByLabelText('Под 14 години съм'));
    expect(screen.getByText('За родител или настойник')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(submit());

    expect(recordConsent).toHaveBeenCalledWith('under_14', true);
    expect(await screen.findByText('exam page')).toBeInTheDocument();
  });

  it('clears the tick when the age answer changes, since it now means something else', async () => {
    renderPage();
    await userEvent.click(screen.getByLabelText('На 14 или повече години съм'));
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByLabelText('Под 14 години съм'));
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(submit()).toBeDisabled();
  });

  it('shows the server message when saving fails', async () => {
    recordConsent.mockImplementation(async () => {
      throw { response: { status: 503, data: { detail: 'Database unavailable' } } };
    });
    renderPage();
    await userEvent.click(screen.getByLabelText('На 14 или повече години съм'));
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(submit());
    expect(await screen.findByRole('alert')).toHaveTextContent('Database unavailable');
  });
});
