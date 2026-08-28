import { io, type Socket } from 'socket.io-client';
import type { ActiveTestProblem } from './activeTest';

export type PairedDevice = {
  id: string;
  name: string;
  joinedAt: string;
  userAgent: string;
};

export type RoomState = {
  roomCode: string;
  devices: PairedDevice[];
};

export type PairingImagePayload = {
  dataUrl: string;
  sentAt: string;
  deviceId: string;
  deviceName: string;
};

export type ActiveTestDataPayload = {
  problems: ActiveTestProblem[];
};

export type SubmitAnswerImagePayload = {
  problemId: number;
  image: string;
};

type PairingAck = {
  ok: boolean;
  reason?: 'INVALID_CODE' | 'ROOM_EXISTS' | 'ROOM_NOT_FOUND' | 'ACCOUNT_MISMATCH' | 'UNAUTHORIZED';
  roomCode?: string;
  devices?: PairedDevice[];
  device?: PairedDevice;
  expectedUserId?: string;
};

type SendImageAck = {
  ok: boolean;
  reason?: 'NOT_PAIRED' | 'TOO_LARGE' | 'INVALID_PAYLOAD';
};

type ActiveTestDataAck = {
  ok: boolean;
  reason?: 'NOT_PAIRED' | 'INVALID_PAYLOAD';
};

type SubmitAnswerImageAck = {
  ok: boolean;
  reason?: 'NOT_PAIRED' | 'TOO_LARGE' | 'INVALID_PAYLOAD';
};

export type PairingSocket = Socket;

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
    // pairing identity from it, so an unauthenticated socket is refused.
    auth: (cb) => cb({ token: localStorage.getItem('token') ?? '' }),
    transports: ['websocket', 'polling'],
    reconnection: !socketConfig.isFallbackOrigin,
    reconnectionAttempts: socketConfig.isFallbackOrigin ? 0 : 20,
    reconnectionDelay: 1000,
  });
};

export const emitCreateRoom = (socket: PairingSocket, roomCode: string, ownerUserId: string): Promise<PairingAck> => {
  return new Promise((resolve) => {
    socket.emit('createRoom', { roomCode, ownerUserId }, (response: PairingAck) => resolve(response));
  });
};

export const emitJoinRoom = (socket: PairingSocket, roomCode: string, requesterUserId: string): Promise<PairingAck> => {
  return new Promise((resolve) => {
    socket.emit('joinRoom', { roomCode, requesterUserId }, (response: PairingAck) => resolve(response));
  });
};

export const emitSendImage = (socket: PairingSocket, dataUrl: string): Promise<SendImageAck> => {
  return new Promise((resolve) => {
    socket.emit('sendImage', { dataUrl }, (response: SendImageAck) => resolve(response));
  });
};

export const emitActiveTestData = (socket: PairingSocket, problems: ActiveTestProblem[]): Promise<ActiveTestDataAck> => {
  return new Promise((resolve) => {
    socket.emit('activeTestData', { problems }, (response: ActiveTestDataAck) => resolve(response));
  });
};

export const emitSubmitAnswerImage = (
  socket: PairingSocket,
  payload: SubmitAnswerImagePayload
): Promise<SubmitAnswerImageAck> => {
  return new Promise((resolve) => {
    socket.emit('submitAnswerImage', payload, (response: SubmitAnswerImageAck) => resolve(response));
  });
};

export const generatePairingCode = (): string => {
  return Math.floor(100000 + Math.random() * 900000).toString();
};