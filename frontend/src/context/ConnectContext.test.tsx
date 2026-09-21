import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const handlers = new Map<string, (payload: unknown) => void>();
const emitted: Array<{ event: string; payload: unknown }> = [];

const fakeSocket = {
  connected: true,
  on: (event: string, handler: (payload: unknown) => void) => handlers.set(event, handler),
  once: (event: string, handler: (payload: unknown) => void) => handlers.set(event, handler),
  off: (event: string) => handlers.delete(event),
  removeAllListeners: (event?: string) => {
    if (event) handlers.delete(event);
    else handlers.clear();
  },
  connect: vi.fn(),
  disconnect: vi.fn(),
  emit: (event: string, payload: unknown, ack?: (r: unknown) => void) => {
    emitted.push({ event, payload });
    if (event === 'presence:subscribe') ack?.({ ok: true, devices: [] });
    else if (event === 'link:request') ack?.({ ok: true, requestId: 'req-1' });
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
    getStoredPairingUserId: () => '42',
  };
});

import { ConnectProvider, useConnect } from './ConnectContext';
import { TEST_ANSWER_IMAGE_EVENT } from '../services/testAnswerSync';

const Probe = () => {
  const { status, devices, linkedDevice, pendingRequest, requestLink } = useConnect();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="device-count">{devices.length}</span>
      <span data-testid="linked">{linkedDevice?.name ?? 'none'}</span>
      <span data-testid="pending">{pendingRequest?.deviceId ?? 'none'}</span>
      <button onClick={() => void requestLink('dev-a')}>connect</button>
    </div>
  );
};

const fire = (event: string, payload: unknown) =>
  act(() => {
    handlers.get(event)?.(payload);
  });

describe('ConnectContext', () => {
  beforeEach(() => {
    handlers.clear();
    emitted.length = 0;
    localStorage.clear();
  });

  it('subscribes to presence on mount', async () => {
    render(<ConnectProvider><Probe /></ConnectProvider>);
    await waitFor(() => expect(emitted.some((e) => e.event === 'presence:subscribe')).toBe(true));
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('discovering'));
  });

  it('renders devices pushed by presence:list', async () => {
    render(<ConnectProvider><Probe /></ConnectProvider>);
    await waitFor(() => expect(handlers.has('presence:list')).toBe(true));

    fire('presence:list', {
      devices: [
        { deviceId: 'dev-a', name: 'iPhone · Safari', platform: 'iPhone', announcedAt: 1, busy: false },
      ],
    });
    expect(screen.getByTestId('device-count').textContent).toBe('1');
  });

  it('moves to requesting, then linked, then back on link:ended', async () => {
    render(<ConnectProvider><Probe /></ConnectProvider>);
    await waitFor(() => expect(handlers.has('link:established')).toBe(true));

    await userEvent.click(screen.getByText('connect'));
    await waitFor(() => expect(screen.getByTestId('pending').textContent).toBe('dev-a'));
    expect(screen.getByTestId('status').textContent).toBe('requesting');

    fire('link:established', {
      linkId: 'l1',
      peer: { deviceId: 'dev-a', name: 'iPhone · Safari' },
      examProblems: [],
    });
    expect(screen.getByTestId('status').textContent).toBe('linked');
    expect(screen.getByTestId('linked').textContent).toBe('iPhone · Safari');

    fire('link:ended', { reason: 'peer-left' });
    expect(screen.getByTestId('status').textContent).toBe('discovering');
    expect(screen.getByTestId('linked').textContent).toBe('none');
  });

  it('clears the pending request when the phone declines', async () => {
    render(<ConnectProvider><Probe /></ConnectProvider>);
    await waitFor(() => expect(handlers.has('link:rejected')).toBe(true));

    await userEvent.click(screen.getByText('connect'));
    await waitFor(() => expect(screen.getByTestId('pending').textContent).toBe('dev-a'));

    fire('link:rejected', { deviceId: 'dev-a' });
    expect(screen.getByTestId('pending').textContent).toBe('none');
    expect(screen.getByTestId('status').textContent).toBe('discovering');
  });

  it('re-dispatches an inbound photo as the NVO answer-image event', async () => {
    render(<ConnectProvider><Probe /></ConnectProvider>);
    await waitFor(() => expect(handlers.has('answer:submit')).toBe(true));

    const received = vi.fn();
    window.addEventListener(TEST_ANSWER_IMAGE_EVENT, received);
    fire('answer:submit', {
      problemId: 17,
      image: 'data:image/jpeg;base64,AA==',
      deviceId: 'dev-a',
      deviceName: 'iPhone',
      submittedAt: '2026-09-21T00:00:00.000Z',
    });

    expect(received).toHaveBeenCalledTimes(1);
    const detail = (received.mock.calls[0][0] as CustomEvent).detail;
    expect(detail.problemId).toBe(17);
    expect(detail.image).toBe('data:image/jpeg;base64,AA==');
    window.removeEventListener(TEST_ANSWER_IMAGE_EVENT, received);
  });
});
