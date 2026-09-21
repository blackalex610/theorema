import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import {
  createSocketClient,
  emitExamProblems,
  emitLinkCancel,
  emitLinkEnd,
  emitLinkRequest,
  emitPresenceSubscribe,
  getStoredPairingUserId,
  REALTIME_AVAILABLE,
  type AnswerSubmitPayload,
  type DiscoveredDevice,
  type LinkEstablished,
  type PairingImagePayload,
  type PairingSocket,
} from '../services/socket';
import { ACTIVE_TEST_DATA_EVENT, readActiveTestData, type ActiveTestProblem } from '../services/activeTest';
import { TEST_ANSWER_IMAGE_EVENT, type SubmitAnswerImageEventPayload } from '../services/testAnswerSync';
import { describeDevice, getDesktopId } from '../utils/deviceIdentity';

export type ConnectStatus = 'idle' | 'connecting' | 'discovering' | 'requesting' | 'linked' | 'error';

export type LinkedDevice = { deviceId: string; name: string };

export type PendingRequest = { deviceId: string; requestId: string; expiresAt: number };

type ConnectContextValue = {
  status: ConnectStatus;
  error: string;
  devices: DiscoveredDevice[];
  linkedDevice: LinkedDevice | null;
  pendingRequest: PendingRequest | null;
  latestImage: PairingImagePayload | null;
  refreshDevices: () => Promise<void>;
  requestLink: (deviceId: string) => Promise<void>;
  cancelRequest: () => Promise<void>;
  endLink: () => Promise<void>;
};

const ConnectContext = createContext<ConnectContextValue | null>(null);

const REQUEST_TTL_MS = 30_000;

const reasonMessage: Record<string, string> = {
  DEVICE_GONE: 'Устройството вече не е налично.',
  DEVICE_BUSY: 'Устройството вече е свързано другаде.',
  ALREADY_LINKED: 'Вече имаш свързан телефон. Прекъсни връзката първо.',
  UNAUTHORIZED: 'Свързването беше отказано — влез отново в профила си.',
};

/**
 * Why the feature cannot start, or null if it can.
 *
 * Resolved once up front rather than inside an effect: both conditions are
 * known at first render, and setting state synchronously in an effect body
 * costs a second render pass for no benefit.
 */
const startupBlocker = (): string | null => {
  if (!REALTIME_AVAILABLE) return 'Свързването с телефон не е конфигурирано (VITE_REALTIME_URL).';
  if (!getStoredPairingUserId()) return 'Свързването с телефон изисква вписан профил.';
  return null;
};

export const ConnectProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [status, setStatus] = useState<ConnectStatus>(() =>
    startupBlocker() ? 'error' : 'connecting'
  );
  const [error, setError] = useState(() => startupBlocker() ?? '');
  const [devices, setDevices] = useState<DiscoveredDevice[]>([]);
  const [linkedDevice, setLinkedDevice] = useState<LinkedDevice | null>(null);
  const [pendingRequest, setPendingRequest] = useState<PendingRequest | null>(null);
  const [latestImage, setLatestImage] = useState<PairingImagePayload | null>(null);
  const socketRef = useRef<PairingSocket | null>(null);

  const pushExamProblems = useCallback(async (problems?: ActiveTestProblem[]) => {
    const socket = socketRef.current;
    if (!socket?.connected) return;
    await emitExamProblems(socket, problems ?? readActiveTestData());
  }, []);

  const subscribe = useCallback(async (socket: PairingSocket) => {
    const ack = await emitPresenceSubscribe(socket, getDesktopId(), describeDevice());
    if (!ack.ok) {
      setStatus('error');
      setError(reasonMessage[ack.reason ?? ''] ?? 'Неуспешно свързване със сървъра.');
      return;
    }
    setDevices(ack.devices);
    setStatus((current) => (current === 'linked' ? current : 'discovering'));
    setError('');
    await pushExamProblems();
  }, [pushExamProblems]);

  const attachListeners = useCallback((socket: PairingSocket) => {
    socket.on('presence:list', (payload: { devices: DiscoveredDevice[] }) => {
      setDevices(payload?.devices ?? []);
    });

    socket.on('link:established', (payload: LinkEstablished) => {
      setLinkedDevice({
        deviceId: payload.peer?.deviceId ?? '',
        name: payload.peer?.name ?? 'Телефон',
      });
      setPendingRequest(null);
      setStatus('linked');
      setError('');
      // Re-push in case the exam started while this link was forming.
      void pushExamProblems();
    });

    socket.on('link:rejected', () => {
      setPendingRequest(null);
      setStatus('discovering');
      setError('Заявката беше отказана от устройството.');
    });

    socket.on('link:expired', () => {
      setPendingRequest(null);
      setStatus((current) => (current === 'linked' ? current : 'discovering'));
      setError('Заявката изтече без отговор.');
    });

    socket.on('link:ended', () => {
      setLinkedDevice(null);
      setPendingRequest(null);
      setStatus('discovering');
    });

    socket.on('link:peer-reconnected', () => setError(''));

    socket.on('answer:submit', (payload: AnswerSubmitPayload) => {
      const detail: SubmitAnswerImageEventPayload = {
        problemId: payload.problemId,
        image: payload.image,
        deviceId: payload.deviceId,
        deviceName: payload.deviceName,
        submittedAt: payload.submittedAt,
      };
      window.dispatchEvent(
        new CustomEvent<SubmitAnswerImageEventPayload>(TEST_ANSWER_IMAGE_EVENT, { detail })
      );
    });

    // Retained so MathVisionPanel keeps working. No phone entry point emits
    // this today — see "Known dead path" in the design spec.
    socket.on('sendImage', (payload: PairingImagePayload) => setLatestImage(payload));

    socket.on('disconnect', () => {
      setDevices([]);
      setStatus('connecting');
    });

    socket.on('connect', () => {
      void subscribe(socket);
    });

    socket.on('connect_error', () => {
      setStatus('error');
      setError('Няма връзка със сървъра за свързване на телефон.');
    });
  }, [pushExamProblems, subscribe]);

  useEffect(() => {
    if (startupBlocker()) return;

    const socket = createSocketClient();
    socketRef.current = socket;
    attachListeners(socket);
    // subscribe() only setStates after awaiting the server ack, so this is a
    // later microtask, not the synchronous cascade the rule guards against.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (socket.connected) void subscribe(socket);
    else socket.connect();

    return () => {
      socket.removeAllListeners();
      socket.disconnect();
      socketRef.current = null;
    };
  }, [attachListeners, subscribe]);

  useEffect(() => {
    const onExamDataUpdated = (event: Event) => {
      const detail = (event as CustomEvent<ActiveTestProblem[]>).detail;
      void pushExamProblems(Array.isArray(detail) ? detail : undefined);
    };
    window.addEventListener(ACTIVE_TEST_DATA_EVENT, onExamDataUpdated);
    return () => window.removeEventListener(ACTIVE_TEST_DATA_EVENT, onExamDataUpdated);
  }, [pushExamProblems]);

  const refreshDevices = useCallback(async () => {
    const socket = socketRef.current;
    if (socket?.connected) await subscribe(socket);
  }, [subscribe]);

  const requestLink = useCallback(async (deviceId: string) => {
    const socket = socketRef.current;
    if (!socket?.connected) return;

    setError('');
    const ack = await emitLinkRequest(socket, deviceId);
    if (!ack.ok) {
      setError(reasonMessage[ack.reason ?? ''] ?? 'Заявката не беше приета.');
      return;
    }
    setPendingRequest({ deviceId, requestId: ack.requestId, expiresAt: Date.now() + REQUEST_TTL_MS });
    setStatus('requesting');
  }, []);

  const cancelRequest = useCallback(async () => {
    const socket = socketRef.current;
    const current = pendingRequest;
    setPendingRequest(null);
    setStatus('discovering');
    if (socket?.connected && current) await emitLinkCancel(socket, current.requestId);
  }, [pendingRequest]);

  const endLink = useCallback(async () => {
    const socket = socketRef.current;
    setLinkedDevice(null);
    setStatus('discovering');
    if (socket?.connected) await emitLinkEnd(socket);
  }, []);

  const value = useMemo<ConnectContextValue>(
    () => ({
      status,
      error,
      devices,
      linkedDevice,
      pendingRequest,
      latestImage,
      refreshDevices,
      requestLink,
      cancelRequest,
      endLink,
    }),
    [
      cancelRequest,
      devices,
      endLink,
      error,
      latestImage,
      linkedDevice,
      pendingRequest,
      refreshDevices,
      requestLink,
      status,
    ]
  );

  return <ConnectContext.Provider value={value}>{children}</ConnectContext.Provider>;
};

export const useConnect = (): ConnectContextValue => {
  const context = useContext(ConnectContext);
  if (!context) throw new Error('useConnect must be used within a ConnectProvider');
  return context;
};
