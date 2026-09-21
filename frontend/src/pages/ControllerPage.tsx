import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import type { ActiveTestProblem } from '../services/activeTest';
import {
  createSocketClient,
  emitAnswerSubmit,
  emitLinkLeave,
  emitLinkRespond,
  emitPresenceAnnounce,
  emitPresenceWithdraw,
  REALTIME_AVAILABLE,
  type IncomingLinkRequest,
  type LinkEstablished,
  type PairingSocket,
} from '../services/socket';
import { describeDevice, detectPlatform, getDeviceId, getDisplayName } from '../utils/deviceIdentity';
import { fileToJpegDataUrl } from '../utils/imageCapture';
import PhoneVisibleScreen from '../components/connect/PhoneVisibleScreen';
import PhoneConfirmSheet from '../components/connect/PhoneConfirmSheet';
import PhoneIdleScreen from '../components/connect/PhoneIdleScreen';
import PhoneExamScreen, { type ProblemUpload } from '../components/connect/PhoneExamScreen';

type PhoneState = 'connecting' | 'visible' | 'confirming' | 'linked' | 'offline';

const ControllerPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [phoneState, setPhoneState] = React.useState<PhoneState>('connecting');
  const [deviceName, setDeviceName] = React.useState(() => getDisplayName());
  const [incoming, setIncoming] = React.useState<(IncomingLinkRequest & { expiresAt: number }) | null>(null);
  const [problems, setProblems] = React.useState<ActiveTestProblem[]>([]);
  const [uploads, setUploads] = React.useState<Record<number, ProblemUpload>>({});
  const [error, setError] = React.useState<string | null>(null);
  const socketRef = React.useRef<PairingSocket | null>(null);

  const announce = React.useCallback(async (socket: PairingSocket, name: string) => {
    const ack = await emitPresenceAnnounce(socket, getDeviceId(), name, detectPlatform());
    if (ack.ok) setPhoneState((current) => (current === 'linked' ? current : 'visible'));
  }, []);

  React.useEffect(() => {
    if (!user) return;
    if (!REALTIME_AVAILABLE) {
      setPhoneState('offline');
      setError('Свързването не е конфигурирано на този сървър.');
      return;
    }

    const socket = createSocketClient();
    socketRef.current = socket;

    socket.on('connect', () => void announce(socket, getDisplayName()));
    socket.on('connect_error', () => {
      setPhoneState('offline');
      setError('Няма връзка със сървъра.');
    });
    socket.on('disconnect', () => setPhoneState('connecting'));

    socket.on('link:incoming', (payload: IncomingLinkRequest) => {
      setIncoming({ ...payload, expiresAt: Date.now() + payload.expiresInMs });
      setPhoneState('confirming');
    });

    socket.on('link:expired', () => {
      setIncoming(null);
      setPhoneState((current) => (current === 'linked' ? current : 'visible'));
    });

    socket.on('link:established', (payload: LinkEstablished) => {
      setIncoming(null);
      setProblems(payload.examProblems ?? []);
      setPhoneState('linked');
      setError(null);
    });

    socket.on('link:ended', () => {
      setPhoneState('visible');
      setProblems([]);
      setUploads({});
    });

    socket.on('exam:problems', (payload: { problems?: ActiveTestProblem[] }) => {
      setProblems(Array.isArray(payload?.problems) ? payload.problems : []);
    });

    socket.on('answer:received', (payload: { problemId?: number }) => {
      const problemId = Number(payload?.problemId);
      if (!Number.isFinite(problemId)) return;
      setUploads((current) => ({
        ...current,
        [problemId]: { ...(current[problemId] ?? { image: '' }), status: 'sent' },
      }));
    });

    if (socket.connected) void announce(socket, getDisplayName());
    else socket.connect();

    // A backgrounded tab should not keep advertising this phone as available.
    const onVisibilityChange = () => {
      if (!socket.connected) return;
      if (document.visibilityState === 'hidden') void emitPresenceWithdraw(socket);
      else void announce(socket, getDisplayName());
    };
    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      // Leaving the connect screen must remove this phone from the desktop list.
      if (socket.connected) void emitPresenceWithdraw(socket);
      socket.removeAllListeners();
      socket.disconnect();
      socketRef.current = null;
    };
  }, [announce, user]);

  const handleNicknameChange = (name: string) => {
    const next = name || describeDevice();
    setDeviceName(next);
    const socket = socketRef.current;
    if (socket?.connected) void announce(socket, next);
  };

  const respond = async (accept: boolean) => {
    const socket = socketRef.current;
    const request = incoming;
    setIncoming(null);
    if (!accept) setPhoneState('visible');
    if (socket?.connected && request) await emitLinkRespond(socket, request.requestId, accept);
  };

  const disconnect = async () => {
    const socket = socketRef.current;
    setPhoneState('visible');
    setProblems([]);
    setUploads({});
    if (socket?.connected) await emitLinkLeave(socket);
  };

  const capture = async (problemId: number, file: File) => {
    setError(null);
    setUploads((current) => ({ ...current, [problemId]: { image: '', status: 'sending' } }));

    try {
      const dataUrl = await fileToJpegDataUrl(file);
      setUploads((current) => ({ ...current, [problemId]: { image: dataUrl, status: 'sending' } }));

      const socket = socketRef.current;
      if (!socket?.connected) throw new Error('Няма връзка с компютъра.');

      const ack = await emitAnswerSubmit(socket, problemId, dataUrl);
      if (!ack.ok) {
        throw new Error(
          ack.reason === 'TOO_LARGE'
            ? 'Снимката е твърде голяма. Опитай отново.'
            : 'Изпращането не успя. Опитай отново.'
        );
      }
      // 'sent' is confirmed by the answer:received event, not assumed here.
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Възникна грешка.');
      setUploads((current) => ({ ...current, [problemId]: { image: '', status: 'failed' } }));
    }
  };

  const shell = (children: React.ReactNode) => (
    <div className="min-h-screen bg-paper px-4 py-6">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-sm items-center justify-center">
        <div className="w-full rounded-3xl border border-line bg-surface p-6 shadow-lg">{children}</div>
      </div>
    </div>
  );

  if (!user) {
    return shell(
      <div className="space-y-4 text-center">
        <h1 className="text-2xl font-bold text-ink">Нужен е профил</h1>
        <p className="text-caption text-ink-muted">
          Влез в същия профил като на компютъра, за да свържеш телефона.
        </p>
        <button
          type="button"
          onClick={() => navigate('/')}
          className="h-12 w-full rounded-2xl bg-brand text-base font-semibold text-white hover:bg-brand-strong"
        >
          Към вход
        </button>
      </div>
    );
  }

  return shell(
    <>
      {phoneState === 'connecting' ? (
        <p className="text-center text-caption text-ink-muted">Свързване…</p>
      ) : null}

      {phoneState === 'offline' ? (
        <p role="alert" className="text-center text-caption font-medium text-danger">
          {error}
        </p>
      ) : null}

      {phoneState === 'visible' ? (
        <PhoneVisibleScreen deviceName={deviceName} onNicknameChange={handleNicknameChange} />
      ) : null}

      {phoneState === 'confirming' && incoming ? (
        <PhoneConfirmSheet
          desktopName={incoming.desktopName}
          expiresAt={incoming.expiresAt}
          onAccept={() => void respond(true)}
          onDecline={() => void respond(false)}
        />
      ) : null}

      {phoneState === 'linked' && problems.length === 0 ? (
        <PhoneIdleScreen deviceName={deviceName} onDisconnect={() => void disconnect()} />
      ) : null}

      {phoneState === 'linked' && problems.length > 0 ? (
        <PhoneExamScreen
          problems={problems}
          uploads={uploads}
          error={error}
          onDismissError={() => setError(null)}
          onCapture={(problemId, file) => void capture(problemId, file)}
        />
      ) : null}
    </>
  );
};

export default ControllerPage;
