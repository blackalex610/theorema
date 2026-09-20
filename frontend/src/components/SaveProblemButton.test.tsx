import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const toggle = vi.fn();
const isSaved = vi.fn();

vi.mock('../context/SavedProblemsContext', () => ({
  useSavedProblems: () => ({
    isSaved,
    toggle,
    savedCount: 0,
    error: null,
    clearError: vi.fn(),
    refresh: vi.fn(),
  }),
}));

import SaveProblemButton from './SaveProblemButton';
import type { SavedProblemSnapshot } from '../services/savedProblems';

const snapshot: SavedProblemSnapshot = {
  kind: 'exercise',
  question: 'Колко е 2 + 2?',
  answer_type: 'numeric',
  origin: { lesson_id: 3 },
};

describe('SaveProblemButton', () => {
  beforeEach(() => {
    toggle.mockReset().mockResolvedValue(undefined);
    isSaved.mockReset().mockReturnValue(false);
  });

  it('offers to save when the problem is not saved yet', () => {
    render(
      <SaveProblemButton source="exercise" sourceRef="4271" buildSnapshot={() => snapshot} />
    );
    expect(screen.getByRole('button', { name: 'Запази задачата' })).toBeInTheDocument();
  });

  it('offers to remove when the problem is already saved', () => {
    isSaved.mockReturnValue(true);
    render(
      <SaveProblemButton source="exercise" sourceRef="4271" buildSnapshot={() => snapshot} />
    );
    expect(screen.getByRole('button', { name: 'Премахни от запазените' })).toBeInTheDocument();
  });

  it('toggles with the source and ref when clicked', async () => {
    render(
      <SaveProblemButton source="nvo" sourceRef="exam-abc:7" buildSnapshot={() => snapshot} />
    );
    await userEvent.click(screen.getByRole('button', { name: 'Запази задачата' }));
    expect(toggle).toHaveBeenCalledTimes(1);
    expect(toggle.mock.calls[0][0]).toMatchObject({ source: 'nvo', sourceRef: 'exam-abc:7' });
  });

  it('does not build the snapshot until the button is clicked', async () => {
    const buildSnapshot = vi.fn(() => snapshot);
    render(<SaveProblemButton source="exercise" sourceRef="1" buildSnapshot={buildSnapshot} />);
    expect(buildSnapshot).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Запази задачата' }));
    expect(toggle.mock.calls[0][0].buildSnapshot).toBe(buildSnapshot);
  });
});
