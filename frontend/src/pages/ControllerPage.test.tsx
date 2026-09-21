import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const handlers = new Map<string, (payload: unknown) => void>();
const emitted: Array<{ event: string; payload: unknown }> = [];

const fakeSocket = {
  connected: true,
  on: (event: string, handler: (payload: unknown) => void) => handlers.set(event, handler),
  once: (event: string, handler: (payload: unknown) => void) => handlers.set(event, handler),
  removeAllListeners: () => handlers.clear(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  emit: (event: string, payload: unknown, ack?: (r: unknown) => void) => {
    emitted.push({ event, payload });
    if (event === 'presence:announce') ack?.({ ok: true, deviceId: 'dev-a' });
    else ack?.({ ok: true });
  },
};

vi.mock('../services/socket', async () => {
  const actual = await vi.importActual<typeof import('../services/socket')>('../services/socket');
  return {
    ...actual,
    REALTIME_AVAILABLE: true,
    SOCKET_SERVER_URL: 'http://localhost:3001',
    createSocketClient: () => fakeSocket,
  };
});

const mockUser: { id: string; name: string } | null = { id: '42', name: 'Иван' };
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}));

vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }));

import ControllerPage from './ControllerPage';

const fire = (event: string, payload: unknown) =>
  act(() => {
    handlers.get(event)?.(payload);
  });

describe('ControllerPage', () => {
  beforeEach(() => {
    handlers.clear();
    emitted.length = 0;
    localStorage.clear();
  });

  it('announces presence on mount and shows the visible screen', async () => {
    render(<ControllerPage />);
    await waitFor(() => expect(emitted.some((e) => e.event === 'presence:announce')).toBe(true));
    await waitFor(() => expect(screen.getByText('Видим си')).toBeInTheDocument());
  });

  it('shows the confirm sheet on an incoming request, naming the desktop', async () => {
    render(<ControllerPage />);
    await waitFor(() => expect(handlers.has('link:incoming')).toBe(true));

    fire('link:incoming', {
      requestId: 'req-1',
      desktopName: 'Windows · Chrome',
      expiresInMs: 30000,
    });

    expect(screen.getByText('Заявка за свързване')).toBeInTheDocument();
    expect(screen.getByText('Windows · Chrome')).toBeInTheDocument();
  });

  it('sends the accept response and then shows the idle Kahoot screen', async () => {
    render(<ControllerPage />);
    await waitFor(() => expect(handlers.has('link:incoming')).toBe(true));

    fire('link:incoming', { requestId: 'req-1', desktopName: 'Mac · Safari', expiresInMs: 30000 });
    await userEvent.click(screen.getByText('Приеми'));

    const respond = emitted.find((e) => e.event === 'link:respond');
    expect(respond?.payload).toEqual({ requestId: 'req-1', accept: true });

    fire('link:established', { linkId: 'l1', peer: { desktopId: 'desk-1' }, examProblems: [] });
    expect(screen.getByText('Свързан')).toBeInTheDocument();
    expect(screen.getByText('Погледни екрана на компютъра.')).toBeInTheDocument();
  });

  it('declining sends accept:false and returns to the visible screen', async () => {
    render(<ControllerPage />);
    await waitFor(() => expect(handlers.has('link:incoming')).toBe(true));

    fire('link:incoming', { requestId: 'req-9', desktopName: 'Mac', expiresInMs: 30000 });
    await userEvent.click(screen.getByText('Откажи'));

    const respond = emitted.find((e) => e.event === 'link:respond');
    expect(respond?.payload).toEqual({ requestId: 'req-9', accept: false });
    await waitFor(() => expect(screen.getByText('Видим си')).toBeInTheDocument());
  });

  it('shows the problem list once an exam starts, using Bulgarian labels', async () => {
    render(<ControllerPage />);
    await waitFor(() => expect(handlers.has('link:established')).toBe(true));

    fire('link:established', {
      linkId: 'l1',
      peer: { desktopId: 'desk-1' },
      examProblems: [
        { id: 17, label: 'Задача 17', type: 'open' },
        { id: 18, label: 'Задача 18', type: 'open' },
      ],
    });

    expect(screen.getByText('Задачи')).toBeInTheDocument();
    expect(screen.getByText('Задача 17')).toBeInTheDocument();
    expect(screen.getByText('Задача 18')).toBeInTheDocument();
    // Progress pill starts at zero sent.
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('marks a problem sent only when the server confirms receipt', async () => {
    render(<ControllerPage />);
    await waitFor(() => expect(handlers.has('answer:received')).toBe(true));

    fire('link:established', {
      linkId: 'l1',
      peer: { desktopId: 'desk-1' },
      examProblems: [{ id: 17, label: 'Задача 17', type: 'open' }],
    });
    expect(screen.queryByText('✓ Изпратена')).not.toBeInTheDocument();

    fire('answer:received', { problemId: 17 });
    expect(screen.getByText('✓ Изпратена')).toBeInTheDocument();
  });

  it('withdraws presence when the connect screen unmounts', async () => {
    const { unmount } = render(<ControllerPage />);
    await waitFor(() => expect(emitted.some((e) => e.event === 'presence:announce')).toBe(true));

    unmount();
    expect(emitted.some((e) => e.event === 'presence:withdraw')).toBe(true);
  });
});
