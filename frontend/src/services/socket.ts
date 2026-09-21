import { io, type Socket } from 'socket.io-client';
import type { ActiveTestProblem } from './activeTest';

export type PairingSocket = Socket;

/**
 * A photo pushed from the phone for ad-hoc math recognition.
 *
 * Nothing currently emits this — see "Known dead path" in
 * docs/superpowers/specs/2026-09-21-phone-connect-rehaul-design.md. The type
 * and listener are retained so MathVisionPanel keeps its prop.
 */
export type PairingImagePayload = {
  dataUrl: string;
  sentAt: string;
  deviceId: string;
  deviceName: string;
};

export type ConnectReason =
  | 'UNAUTHORIZED'
  | 'INVALID_PAYLOAD'
  | 'DEVICE_GONE'
  | 'DEVICE_BUSY'
  | 'ALREADY_LINKED'
  | 'NOT_LINKED'
  | 'TOO_LARGE'
  | 'REQUEST_EXPIRED'
  | 'REQUEST_UNKNOWN';

export type ConnectAck<T = unknown> = ({ ok: true } & T) | { ok: false; reason?: ConnectReason };

export type DiscoveredDevice = {
  deviceId: string;
  name: string;
  platform: string;
  announcedAt: number;
  busy: boolean;
};

export type IncomingLinkRequest = {
  requestId: string;
  desktopName: string;
  expiresInMs: number;
};

export type LinkEstablished = {
  linkId: string;
  peer: { deviceId?: string; desktopId?: string; name?: string };
  examProblems: ActiveTestProblem[];
};

export type AnswerSubmitPayload = {
  problemId: number;
  image: string;
  deviceId: string;
  deviceName: string;
  submittedAt: string;
};

export const getStoredPairingUserId = (): string | null => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem('user');
    if (!raw) return null;
    // Guests now hold a real user_id (backed by a real JWT the realtime
    // server verifies), so pairing works identically for them — no
    // isGuest exception needed.
    const user = JSON.parse(raw) as { id?: string | number };
    if (!user?.id) return null;
    return String(user.id);
  } catch {
    return null;
  }
};

const resolveSocketConfig = (): { baseUrl: string | null; isFallbackOrigin: boolean } => {
  const configured = String(
    import.meta.env.VITE_SOCKET_URL ?? import.meta.env.VITE_REALTIME_URL ?? ''
  ).trim();

  if (configured) {
    const lowered = configured.toLowerCase();
    // Reject values that point back to the Vite dev server or same origin.
    const isSameOrigin = lowered === window.location.origin.toLowerCase();
    const isViteDev = lowered.includes(':5173');
    const isPath = lowered === '/socket.io';
    if (!isSameOrigin && !isViteDev && !isPath) {
      return { baseUrl: configured, isFallbackOrigin: false };
    }
  }

  if (import.meta.env.DEV) {
    const protocol = window.location.protocol === 'https:' ? 'https:' : 'http:';
    const host = window.location.hostname || '127.0.0.1';
    return { baseUrl: `${protocol}//${host}:3001`, isFallbackOrigin: false };
  }

  // Production with no explicit realtime URL configured.
  return { baseUrl: null, isFallbackOrigin: false };
};

const socketConfig = resolveSocketConfig();
export const SOCKET_SERVER_URL = socketConfig.baseUrl;
export const REALTIME_AVAILABLE = Boolean(SOCKET_SERVER_URL);

export const createSocketClient = (): PairingSocket => {
  if (!SOCKET_SERVER_URL) {
    return io('http://localhost:0', {
      autoConnect: false,
      reconnection: false,
    });
  }

  return io(SOCKET_SERVER_URL, {
    autoConnect: true,
    path: '/socket.io',
    // The realtime server verifies this JWT on the handshake and derives the
    // connect identity from it, so an unauthenticated socket is refused.
    auth: (cb) => cb({ token: localStorage.getItem('token') ?? '' }),
    transports: ['websocket', 'polling'],
    reconnection: !socketConfig.isFallbackOrigin,
    reconnectionAttempts: socketConfig.isFallbackOrigin ? 0 : 20,
    reconnectionDelay: 1000,
  });
};

const request = <T,>(
  socket: PairingSocket,
  event: string,
  payload: unknown
): Promise<ConnectAck<T>> =>
  new Promise((resolve) => {
    socket.emit(event, payload, (response: ConnectAck<T>) => resolve(response));
  });

// ─── Desktop ─────────────────────────────────────────────────────────────────

export const emitPresenceSubscribe = (socket: PairingSocket, desktopId: string, name: string) =>
  request<{ devices: DiscoveredDevice[] }>(socket, 'presence:subscribe', { desktopId, name });

export const emitPresenceUnsubscribe = (socket: PairingSocket) =>
  request(socket, 'presence:unsubscribe', {});

export const emitLinkRequest = (socket: PairingSocket, deviceId: string) =>
  request<{ requestId: string }>(socket, 'link:request', { deviceId });

export const emitLinkCancel = (socket: PairingSocket, requestId: string) =>
  request(socket, 'link:cancel', { requestId });

export const emitLinkEnd = (socket: PairingSocket) => request(socket, 'link:end', {});

export const emitExamProblems = (socket: PairingSocket, problems: ActiveTestProblem[]) =>
  request(socket, 'exam:problems', { problems });

// ─── Phone ───────────────────────────────────────────────────────────────────

export const emitPresenceAnnounce = (
  socket: PairingSocket,
  deviceId: string,
  name: string,
  platform: string
) => request<{ deviceId: string }>(socket, 'presence:announce', { deviceId, name, platform });

export const emitPresenceWithdraw = (socket: PairingSocket) =>
  request(socket, 'presence:withdraw', {});

export const emitLinkRespond = (socket: PairingSocket, requestId: string, accept: boolean) =>
  request(socket, 'link:respond', { requestId, accept });

export const emitLinkLeave = (socket: PairingSocket) => request(socket, 'link:leave', {});

export const emitAnswerSubmit = (socket: PairingSocket, problemId: number, image: string) =>
  request(socket, 'answer:submit', { problemId, image });
