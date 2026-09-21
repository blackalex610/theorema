import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import MyDataSection from './MyDataSection';

const deleteMyAccount = vi.fn();
const downloadMyData = vi.fn();
const signOut = vi.fn();

vi.mock('../services/userData', () => ({
  deleteMyAccount: (...args: unknown[]) => deleteMyAccount(...args),
  downloadMyData: (...args: unknown[]) => downloadMyData(...args),
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ signOut }),
}));

beforeEach(() => {
  deleteMyAccount.mockReset().mockResolvedValue({ deleted: true, removed_rows: {} });
  downloadMyData.mockReset().mockResolvedValue(undefined);
  signOut.mockReset();
});

describe('MyDataSection', () => {
  it('exports the data when asked', async () => {
    render(<MyDataSection />);

    await userEvent.click(screen.getByRole('button', { name: 'Изтегли данните ми' }));

    expect(downloadMyData).toHaveBeenCalledOnce();
  });

  it('does not delete the account on the first click', async () => {
    render(<MyDataSection />);

    await userEvent.click(screen.getByRole('button', { name: 'Изтрий профила' }));

    expect(deleteMyAccount).not.toHaveBeenCalled();
  });

  it('keeps deletion disabled until the confirmation word is typed exactly', async () => {
    render(<MyDataSection />);
    await userEvent.click(screen.getByRole('button', { name: 'Изтрий профила' }));

    const confirmButton = screen.getByRole('button', { name: 'Изтрий окончателно' });
    expect(confirmButton).toBeDisabled();

    await userEvent.type(screen.getByRole('textbox'), 'изтрий');
    expect(confirmButton).toBeDisabled();
  });

  it('deletes and signs out once confirmed', async () => {
    render(<MyDataSection />);
    await userEvent.click(screen.getByRole('button', { name: 'Изтрий профила' }));
    await userEvent.type(screen.getByRole('textbox'), 'ИЗТРИЙ');

    await userEvent.click(screen.getByRole('button', { name: 'Изтрий окончателно' }));

    expect(deleteMyAccount).toHaveBeenCalledOnce();
    expect(signOut).toHaveBeenCalledOnce();
  });

  it('does not sign the student out if deletion failed', async () => {
    deleteMyAccount.mockRejectedValue(new Error('network'));
    render(<MyDataSection />);
    await userEvent.click(screen.getByRole('button', { name: 'Изтрий профила' }));
    await userEvent.type(screen.getByRole('textbox'), 'ИЗТРИЙ');

    await userEvent.click(screen.getByRole('button', { name: 'Изтрий окончателно' }));

    expect(signOut).not.toHaveBeenCalled();
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });
});
