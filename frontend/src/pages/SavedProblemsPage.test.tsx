import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

const listSavedProblems = vi.fn();
const deleteSavedProblem = vi.fn();
const refresh = vi.fn();

vi.mock('../services/savedProblems', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/savedProblems')>();
  return {
    ...actual,
    listSavedProblems: (...args: unknown[]) => listSavedProblems(...args),
    deleteSavedProblem: (...args: unknown[]) => deleteSavedProblem(...args),
  };
});

vi.mock('../context/SavedProblemsContext', () => ({
  useSavedProblems: () => ({
    isSaved: () => true,
    toggle: vi.fn(),
    savedCount: 1,
    error: null,
    clearError: vi.fn(),
    refresh,
  }),
}));

vi.mock('../components/AppNavbar', () => ({ default: () => null }));

import SavedProblemsPage from './SavedProblemsPage';

const nvoItem = {
  id: 1,
  source: 'nvo' as const,
  source_ref: 'exam-abc:7',
  created_at: '2026-09-20T14:05:00',
  snapshot: {
    kind: 'nvo' as const,
    question: 'Колко е 2 + 2?',
    answer_type: 'multiple_choice' as const,
    options: [
      { key: 'А', text: '3' },
      { key: 'Б', text: '4' },
    ],
    correct_answer: 'Б',
    user_answer: 'А',
    origin: { exam_id: 'exam-abc', question_number: 7 },
  },
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <SavedProblemsPage />
    </MemoryRouter>
  );

describe('SavedProblemsPage', () => {
  beforeEach(() => {
    listSavedProblems.mockReset().mockResolvedValue([]);
    deleteSavedProblem.mockReset().mockResolvedValue(undefined);
    refresh.mockReset().mockResolvedValue(undefined);
  });

  it('tells the student when nothing is saved yet', async () => {
    renderPage();
    expect(await screen.findByText('Няма запазени задачи.')).toBeInTheDocument();
  });

  it('shows a saved problem with its origin and the date it was saved', async () => {
    listSavedProblems.mockResolvedValue([nvoItem]);
    renderPage();
    expect(await screen.findByText('Колко е 2 + 2?')).toBeInTheDocument();
    expect(screen.getByText(/От НВО тест/)).toBeInTheDocument();
    expect(screen.getByText(/Задача 7/)).toBeInTheDocument();
  });

  it('reveals the answer only after the student opens the problem', async () => {
    listSavedProblems.mockResolvedValue([nvoItem]);
    renderPage();
    await screen.findByText('Колко е 2 + 2?');
    expect(screen.queryByText('Верен отговор')).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Отвори задачата' }));
    expect(screen.getByText('Верен отговор')).toBeInTheDocument();
    expect(screen.getByText('Твоят отговор')).toBeInTheDocument();
  });

  it('removes a saved problem and refreshes the shared bookmark state', async () => {
    listSavedProblems.mockResolvedValue([nvoItem]);
    renderPage();
    await screen.findByText('Колко е 2 + 2?');

    await userEvent.click(screen.getByRole('button', { name: 'Премахни' }));
    expect(deleteSavedProblem).toHaveBeenCalledWith(1);
    expect(refresh).toHaveBeenCalled();
    expect(await screen.findByText('Няма запазени задачи.')).toBeInTheDocument();
  });

  it('refetches with a source filter when a chip is chosen', async () => {
    listSavedProblems.mockResolvedValue([nvoItem]);
    renderPage();
    await screen.findByText('Колко е 2 + 2?');

    await userEvent.click(screen.getByRole('button', { name: 'От НВО' }));
    expect(listSavedProblems).toHaveBeenLastCalledWith({ limit: 100, source: 'nvo' });
  });
});
