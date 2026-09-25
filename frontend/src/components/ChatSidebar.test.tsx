import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import ChatSidebar from './ChatSidebar';

const ai = vi.hoisted(() => ({ sendChatMessage: vi.fn() }));
vi.mock('../services/ai', () => ai);
// Rendering markdown is not what these tests are about, and loading the real
// renderer lazily is slow enough under a full parallel run to time them out.
vi.mock('./ChatMarkdown', () => ({ default: ({ content }: { content: string }) => <>{content}</> }));
vi.mock('../hooks/usePlan', () => ({
  usePlan: () => ({ status: { days_since_signup: 30, is_premium: false } }),
}));

function renderSidebar() {
  render(
    <MemoryRouter initialEntries={['/learn/lessons/3/theory']}>
      <ChatSidebar isOpen onOpen={() => {}} onClose={() => {}} />
    </MemoryRouter>
  );
}

describe('ChatSidebar', () => {
  it('a shortcut continues the conversation instead of replacing it', async () => {
    ai.sendChatMessage.mockReset();
    ai.sendChatMessage.mockResolvedValueOnce('Първи отговор').mockResolvedValueOnce('Втори отговор');
    renderSidebar();

    // The panel renders twice (desktop column and mobile drawer); either works.
    fireEvent.change(screen.getAllByPlaceholderText('Напиши въпрос...')[0], {
      target: { value: 'Какво е дроб?' },
    });
    fireEvent.click(screen.getAllByText('Изпрати')[0]);
    await screen.findAllByText('Първи отговор');

    fireEvent.click(screen.getAllByText('🔍 Обясни по-просто')[0]);
    await screen.findAllByText('Втори отговор');

    const history = ai.sendChatMessage.mock.calls[1][0].map((m: { content: string }) => m.content);
    expect(history).toContain('Какво е дроб?');
    expect(history).toContain('Първи отговор');
    await waitFor(() => expect(screen.getAllByText('Какво е дроб?').length).toBeGreaterThan(0));
  });

  it('answers text sent from a text selection elsewhere on the page', async () => {
    ai.sendChatMessage.mockReset();
    ai.sendChatMessage.mockResolvedValue('Отговор');
    renderSidebar();

    window.dispatchEvent(new CustomEvent('ask-assistant-from-selection', { detail: { text: '  Обясни 2/3  ' } }));

    await screen.findAllByText('Отговор');
    const history = ai.sendChatMessage.mock.calls[0][0];
    expect(history[history.length - 1]).toEqual({ role: 'user', content: 'Обясни 2/3' });
  });
});
