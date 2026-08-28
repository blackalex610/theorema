import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import type { ActiveTestProblem } from '../services/activeTest';
import {
  createSocketClient,
  getStoredPairingUserId,
  emitJoinRoom,
  emitSubmitAnswerImage,
  REALTIME_AVAILABLE,
  SOCKET_SERVER_URL,
  type PairedDevice,
  type PairingSocket,
} from '../services/socket';
import heic2any from 'heic2any';

type ProblemUploadState = {
  image: string;
  status: 'empty' | 'uploaded';
};

const ControllerPage: React.FC = () => {
  const navigate = useNavigate();
  const [controllerState, setControllerState] = React.useState<'pairing' | 'waiting' | 'test'>('pairing');
  const [pairingCode, setPairingCode] = React.useState('');
  const [status, setStatus] = React.useState<
    'idle' | 'connecting' | 'connected' | 'invalid-code' | 'server-unavailable' | 'disconnected' | 'room-closed'
  >('idle');
  const [activeTestProblems, setActiveTestProblems] = React.useState<ActiveTestProblem[]>([]);
  const [problemUploads, setProblemUploads] = React.useState<Record<number, ProblemUploadState>>({});
  const [device, setDevice] = React.useState<PairedDevice | null>(null);
  const [statusDetail, setStatusDetail] = React.useState('');
  const [uploadError, setUploadError] = React.useState<string | null>(null);
  const socketRef = React.useRef<PairingSocket | null>(null);
  const fileInputRefs = React.useRef<Record<number, HTMLInputElement | null>>({});
  // A guest now holds a real user_id, so pairing works identically to a
  // signed-in user — no separate guest branch needed.
  const { user } = useAuth();
  const access = React.useMemo(() => {
    if (!user) return { allowed: false as const, reason: 'login' as const, userId: undefined };
    return { allowed: true as const, reason: null, userId: String(user.id) };
  }, [user]);

  React.useEffect(() => {
    return () => {
      socketRef.current?.disconnect();
      socketRef.current = null;
    };
  }, []);

  React.useEffect(() => {
    setProblemUploads((current) => {
      const next: Record<number, ProblemUploadState> = {};
      activeTestProblems.forEach((problem) => {
        next[problem.id] = current[problem.id] ?? { image: '', status: 'empty' };
      });
      return next;
    });
  }, [activeTestProblems]);

  const ensureSocket = React.useCallback(() => {
    if (socketRef.current) return socketRef.current;

    const socket = createSocketClient();
    socket.on('disconnect', (reason: string) => {
      setControllerState('pairing');
      setStatus('disconnected');
      setStatusDetail(`Socket disconnected. Reason: ${reason}. URL: ${String(SOCKET_SERVER_URL ?? 'not configured')}`);
      setDevice(null);
      setActiveTestProblems([]);
      setProblemUploads({});
    });
    socket.on('connect_error', (error: unknown) => {
      const err = error as { message?: string; description?: unknown; type?: string };
      setStatus('server-unavailable');
      setStatusDetail(
        `connect_error: ${err?.message ?? 'unknown'}${err?.type ? ` (type: ${err.type})` : ''}${err?.description ? `, details: ${JSON.stringify(err.description)}` : ''}`
      );
    });

    socket.on('roomClosed', () => {
      setControllerState('pairing');
      setStatus('room-closed');
      setDevice(null);
      setActiveTestProblems([]);
      setProblemUploads({});
    });
    socket.on('activeTestData', (payload: { problems?: ActiveTestProblem[] }) => {
      const nextProblems = Array.isArray(payload?.problems) ? payload.problems : [];
      setActiveTestProblems(nextProblems);
      setControllerState(nextProblems.length > 0 ? 'test' : 'waiting');
    });
    socket.on('answerReceived', (payload: { problemId?: number }) => {
      if (!Number.isFinite(payload?.problemId)) return;
      const problemId = Number(payload.problemId);
      setProblemUploads((current) => {
        const currentItem = current[problemId] ?? { image: '', status: 'empty' as const };
        return {
          ...current,
          [problemId]: {
            ...currentItem,
            status: 'uploaded',
          },
        };
      });
    });
    socketRef.current = socket;
    return socket;
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!REALTIME_AVAILABLE) {
      setStatus('server-unavailable');
      setStatusDetail(`No realtime URL configured. Set VITE_REALTIME_URL or VITE_SOCKET_URL. Current SOCKET_SERVER_URL: ${String(SOCKET_SERVER_URL ?? 'null')}`);
      return;
    }

    const normalizedCode = pairingCode.trim();
    const pairingUserId = access.allowed ? access.userId ?? getStoredPairingUserId() : null;
    if (!pairingUserId) {
      setStatus('invalid-code');
      setStatusDetail('Missing authenticated user id for pairing. Please re-login on the phone.');
      return;
    }

    if (!/^\d{6}$/.test(normalizedCode)) {
      setStatus('invalid-code');
      setStatusDetail(`"${normalizedCode}" is not a valid 6-digit code (${normalizedCode.length} char${normalizedCode.length !== 1 ? 's' : ''}, digits only).`);
      return;
    }

    setStatus('connecting');
    setStatusDetail('');

    const socket = ensureSocket();
    if (!socket.connected) {
      // Allow up to 15 s for Render free-tier cold start (can take 30-60 s on first wake-up;
      // 15 s covers the typical 10-12 s case and keeps UX tolerable).
      const connected = await new Promise<boolean>((resolve) => {
        const timeout = window.setTimeout(() => resolve(false), 15000);
        socket.once('connect', () => {
          window.clearTimeout(timeout);
          resolve(true);
        });
        socket.once('connect_error', () => {
          window.clearTimeout(timeout);
          resolve(false);
        });
        socket.connect();
      });

      if (!connected) {
        setStatus('server-unavailable');
        setStatusDetail(`Socket could not connect within 15 s. Realtime URL: ${String(SOCKET_SERVER_URL ?? 'not configured')}. Check network and server.`);
        return;
      }
    }

    // Add a 10 s timeout for the join acknowledgement in case the server
    // accepts the socket but drops the event mid-flight (e.g. cold restart).
    console.log(`🔐 Attempting to join room - code: "${normalizedCode}", userId: ${pairingUserId}, socketConnected: ${socket.connected}, socketUrl: ${SOCKET_SERVER_URL}`);
    
    const response = await Promise.race([
      emitJoinRoom(socket, normalizedCode, pairingUserId),
      new Promise<{ ok: false; reason: 'TIMEOUT' }>((resolve) =>
        window.setTimeout(() => resolve({ ok: false, reason: 'TIMEOUT' }), 10000)
      ),
    ]);
    
    console.log(`📋 Join response:`, response);
    
    if (!response.ok || !('device' in response) || !response.device) {
      setStatus('invalid-code');
      const reason = (response as { reason?: string }).reason ?? 'UNKNOWN';
      console.error(`❌ Join failed - reason: ${reason}`, response);
      if (reason === 'TIMEOUT') {
        setStatusDetail(`Join request timed out (10 s). Server may be cold-starting. URL: ${String(SOCKET_SERVER_URL ?? 'not configured')}`);
      } else if (reason === 'ROOM_NOT_FOUND') {
        setStatusDetail(`No open room found for code "${normalizedCode}". Make sure the desktop has an active pairing session.`);
      } else if (reason === 'INVALID_CODE') {
        setStatusDetail(`Server rejected code format. Code sent: "${normalizedCode}" (${normalizedCode.length} chars).`);
      } else if (reason === 'ACCOUNT_MISMATCH') {
        const expectedUserId = (response as { expectedUserId?: string }).expectedUserId;
        setStatusDetail(`Account mismatch. This phone is logged in as user ${pairingUserId}, but the desktop room belongs to user ${expectedUserId ?? 'unknown'}. Log into the same account on both devices.`);
      } else if (reason === 'ROOM_FULL') {
        setStatusDetail('Вече има свързан телефон. Изключи другото устройство или генерирай нов код от desktop.');
      } else if (reason === 'UNAUTHORIZED') {
        setStatusDetail('Pairing requires a logged-in account on both phone and desktop.');
      } else {
        setStatusDetail(`Join failed — reason: ${reason}. Response: ${JSON.stringify(response)}`);
      }
      setDevice(null);
      return;
    }

    setDevice(response.device);
    setStatus('connected');
    setControllerState('waiting');
  };

  // Helper: Detect if file is an image using BOTH MIME type AND extension
  const isImageFile = (file: File): boolean => {
    const name = file.name.toLowerCase();
    const type = file.type || '';
    
    // Check MIME type first
    if (type.startsWith('image/')) return true;
    
    // Check extension for unreliable MIME type cases (JPEG, HEIC, etc)
    const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.heic', '.heif'];
    return imageExtensions.some(ext => name.endsWith(ext));
  };

  // Helper: Detect HEIC files using BOTH MIME type AND extension
  const isHeicFile = (file: File): boolean => {
    const name = file.name.toLowerCase();
    const type = file.type || '';
    
    // Check MIME type
    if (type === 'image/heic' || type === 'image/heif') return true;
    
    // Check extension
    return name.endsWith('.heic') || name.endsWith('.heif');
  };

  const readFileAsDataUrl = (file: File): Promise<string> => {
    return new Promise(async (resolve, reject) => {
      console.log(`📸 Image selected: ${file.name} (type: ${file.type}, size: ${(file.size / 1024).toFixed(2)} KB)`);
      
      // Convert all images to JPG for consistency (fixes format issues)
      if (isImageFile(file)) {
        console.log('🔄 Converting image to JPG...');
        try {
          // Add timeout to prevent hanging on large images (longer for HEIC)
          const timeoutMs = isHeicFile(file) ? 30000 : 10000; // 30s for HEIC, 10s for others
          const timeoutPromise = new Promise<never>((_, reject) => 
            setTimeout(() => reject(new Error(`Image conversion timeout (${timeoutMs}ms)`)), timeoutMs)
          );
          const conversionPromise = imageToJpegCanvas(file);
          const canvas = await Promise.race([conversionPromise, timeoutPromise]);
          const dataUrl = canvas.toDataURL('image/jpeg', 0.95);
          console.log('✅ Image conversion successful');
          resolve(dataUrl);
          return;
        } catch (error) {
          console.error('❌ Image conversion failed:', error);
          // Don't fall back to raw upload - show error instead
          reject(new Error(`Image conversion failed: ${error instanceof Error ? error.message : 'Unknown error'}`));
          return;
        }
      } else {
        console.log('⚠️ Not an image file, skipping conversion');
      }

      // Fallback for non-image files (shouldn't happen for our use case)
      const reader = new FileReader();
      reader.onload = () => {
        if (typeof reader.result === 'string') {
          console.log(`✅ File read as data URL (${(reader.result.length / 1024).toFixed(2)} KB)`);
          resolve(reader.result);
          return;
        }
        reject(new Error('Invalid file result'));
      };
      reader.onerror = () => {
        const errorMsg = `Failed to read image: ${file.name}`;
        console.error(`❌ ${errorMsg}`);
        reject(new Error(errorMsg));
      };
      reader.readAsDataURL(file);
    });
  };

  const imageToJpegCanvas = async (file: File): Promise<HTMLCanvasElement> => {
    // Handle HEIC files specially
    if (isHeicFile(file)) {
      if (!heic2any) {
        throw new Error('heic2any library not available');
      }
      
      try {
        console.log('🔄 Converting HEIC using heic2any...');
        const conversionResult = await heic2any({ blob: file, toType: 'image/jpeg', quality: 0.95 });
        const blob = Array.isArray(conversionResult) ? conversionResult[0] : conversionResult;
        console.log(`✅ heic2any conversion successful, output size: ${(blob.size / 1024).toFixed(2)} KB`);
        
        return new Promise((resolve, reject) => {
          const img = new Image();
          const blobUrl = URL.createObjectURL(blob);
          img.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = img.width;
            canvas.height = img.height;
            const ctx = canvas.getContext('2d');
            if (!ctx) {
              URL.revokeObjectURL(blobUrl);
              reject(new Error('Could not get canvas context'));
              return;
            }
            ctx.drawImage(img, 0, 0);
            URL.revokeObjectURL(blobUrl);
            console.log(`✅ HEIC canvas created: ${canvas.width}x${canvas.height}`);
            resolve(canvas);
          };
          img.onerror = () => {
            URL.revokeObjectURL(blobUrl);
            reject(new Error('Failed to load converted HEIC image'));
          };
          img.src = blobUrl;
        });
      } catch (error) {
        console.error('❌ heic2any conversion failed:', error);
        throw new Error(`HEIC conversion failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
      }
    }
    
    // For other image formats, use standard canvas conversion
    return new Promise((resolve, reject) => {
      const img = new Image();
      const effectiveMime = file.type && file.type.startsWith('image/') ? file.type : 'image/jpeg';
      const blobUrl = URL.createObjectURL(new Blob([file], { type: effectiveMime }));
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = img.width;
        canvas.height = img.height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          URL.revokeObjectURL(blobUrl);
          reject(new Error('Could not get canvas context'));
          return;
        }
        ctx.drawImage(img, 0, 0);
        URL.revokeObjectURL(blobUrl);
        resolve(canvas);
      };
      img.onerror = () => {
        URL.revokeObjectURL(blobUrl);
        reject(new Error('Failed to load image'));
      };
      img.src = blobUrl;
    });
  };

  const openPhotoCapture = (problemId: number) => {
    fileInputRefs.current[problemId]?.click();
  };

  const handleFileSelected = async (problemId: number, file: File | null) => {
    if (!file) return;

    // Clear any previous error
    setUploadError(null);

    try {
      const dataUrl = await readFileAsDataUrl(file);
      setProblemUploads((current) => ({
        ...current,
        [problemId]: {
          image: dataUrl,
          status: 'uploaded',
        },
      }));

      const socket = socketRef.current;
      if (socket?.connected) {
        console.log(`📤 Submitting answer for problem ${problemId} (${(dataUrl.length / 1024).toFixed(2)} KB)`);
        const response = await emitSubmitAnswerImage(socket, { problemId, image: dataUrl });
        if (response.ok) {
          console.log(`✅ Answer for problem ${problemId} submitted successfully`);
          setProblemUploads((current) => ({
            ...current,
            [problemId]: {
              image: dataUrl,
              status: 'uploaded',
            },
          }));
          return;
        } else {
          console.error(`❌ Answer submission failed for problem ${problemId}: ${response.reason}`);
          // Don't disconnect socket on application errors - just show failed state
          setProblemUploads((current) => ({
            ...current,
            [problemId]: {
              image: '',
              status: 'empty',
            },
          }));
        }
      } else {
        console.error('❌ Socket not connected when submitting answer');
        setProblemUploads((current) => ({
          ...current,
          [problemId]: {
            image: '',
            status: 'empty',
          },
        }));
      }
    } catch (error) {
      console.error(`❌ Error handling file for problem ${problemId}:`, error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      setUploadError(`Failed to process image: ${errorMessage}`);
      setProblemUploads((current) => ({
        ...current,
        [problemId]: {
          image: '',
          status: 'empty',
        },
      }));
    }
  };

  const statusText =
    status === 'connecting'
      ? 'Connecting...'
      : status === 'connected'
        ? 'Connected'
        : status === 'invalid-code'
          ? 'Invalid code'
          : status === 'server-unavailable'
            ? 'Realtime server unavailable'
            : status === 'disconnected'
              ? 'Connection lost'
              : status === 'room-closed'
                ? 'Desktop session ended'
          : 'Enter your 6-digit code to join';

  const renderPairingScreen = () => (
    <>
      <h1 className="text-center text-2xl font-bold text-gray-900 dark:text-slate-100">Enter Pairing Code</h1>
      <p className="mt-2 text-center text-sm text-gray-500 dark:text-slate-400">Use the 6-digit code shown on desktop.</p>

      <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
        <input
          inputMode="numeric"
          pattern="[0-9]*"
          value={pairingCode}
          onChange={(event) => setPairingCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
          placeholder="123456"
          className="h-16 w-full rounded-2xl border border-gray-200 bg-white px-4 text-center text-3xl font-black tracking-[0.35em] text-slate-900 outline-none transition-all duration-200 focus:border-blue-400 focus:ring-4 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100 dark:focus:border-blue-400 dark:focus:ring-blue-500/20"
        />

        <button
          type="submit"
          disabled={status === 'connecting'}
          className="h-14 w-full rounded-2xl bg-blue-600 px-4 text-base font-semibold text-white shadow-sm transition-all duration-200 hover:bg-blue-700 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {status === 'connecting' ? 'Connecting...' : 'Join'}
        </button>
      </form>

      <div
        className={`mt-5 rounded-2xl border px-4 py-3 text-center text-sm font-semibold transition-all duration-200 ${
          status === 'connected'
            ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-300'
            : status === 'invalid-code' || status === 'server-unavailable' || status === 'disconnected' || status === 'room-closed'
              ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300'
              : 'border-gray-200 bg-gray-50 text-gray-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300'
        }`}
      >
          {statusText}
        {statusDetail && (
          <div className="mt-1 text-xs font-normal opacity-80 break-all">{statusDetail}</div>
        )}
      </div>
    </>
  );

  const renderWaitingScreen = () => (
    <>
      <h1 className="text-center text-2xl font-bold text-gray-900 dark:text-slate-100">Connected</h1>
      <p className="mt-2 text-center text-sm text-gray-500 dark:text-slate-400">Waiting for test to start...</p>
      <div className="mt-5 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-4 text-center dark:border-blue-900/40 dark:bg-blue-950/30">
        <p className="text-sm font-semibold text-blue-800 dark:text-blue-300">Waiting for test to start...</p>
        {device ? <p className="mt-1 text-xs text-blue-700 dark:text-blue-400">{device.name}</p> : null}
      </div>

    </>
  );

  const renderTestScreen = () => (
    <>
      <h1 className="text-center text-2xl font-bold text-gray-900 dark:text-slate-100">Test Mode</h1>
      {uploadError && (
        <div className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-center text-sm font-medium text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
          {uploadError}
          <button
            type="button"
            onClick={() => setUploadError(null)}
            className="ml-2 text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
          >
            ✕
          </button>
        </div>
      )}
      <div className="mt-5 space-y-4">
        {activeTestProblems.map((problem) => {
          const upload = problemUploads[problem.id] ?? { image: '', status: 'empty' as const };
          return (
            <div key={problem.id} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
              <p className="text-lg font-bold text-slate-900 dark:text-slate-100">Problem {problem.id}</p>
              {upload.status === 'uploaded' ? (
                <div className="mt-3 space-y-3">
                  <img src={upload.image} alt={`Problem ${problem.id}`} className="w-full rounded-xl border border-slate-200 object-cover dark:border-slate-700" />
                  <button
                    type="button"
                    onClick={() => openPhotoCapture(problem.id)}
                    className="h-14 w-full rounded-2xl bg-emerald-600 px-4 text-base font-semibold text-white shadow-sm transition-all duration-200 hover:bg-emerald-700 active:scale-[0.99]"
                  >
                    Retake
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => openPhotoCapture(problem.id)}
                  className="mt-3 h-14 w-full rounded-2xl bg-blue-600 px-4 text-base font-semibold text-white shadow-sm transition-all duration-200 hover:bg-blue-700 active:scale-[0.99]"
                >
                  Take Photo
                </button>
              )}
              <input
                ref={(element) => {
                  fileInputRefs.current[problem.id] = element;
                }}
                type="file"
                accept="image/*"
                capture="environment"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  void handleFileSelected(problem.id, file);
                  event.currentTarget.value = '';
                }}
              />
            </div>
          );
        })}
        {activeTestProblems.length === 0 ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-center text-sm font-medium text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
            Waiting for test to start...
          </div>
        ) : null}
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 px-4 py-6 dark:from-slate-950 dark:to-slate-900">
      <div className="mx-auto flex min-h-[calc(100vh-3rem)] w-full max-w-sm items-center justify-center">
        <div className="w-full rounded-3xl border border-gray-200 bg-white p-6 shadow-xl shadow-slate-900/10 transition-all duration-300 dark:border-slate-700 dark:bg-slate-900 dark:shadow-black/30">
          {!access.allowed && (
            <div className="space-y-4 text-center">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Свързване не е разрешено</h1>
              <p className="text-sm text-gray-600 dark:text-slate-300">
                Трябва да влезеш в профил, за да свържеш телефона.
              </p>
              <button
                type="button"
                onClick={() => navigate('/')}
                className="h-12 w-full rounded-2xl bg-emerald-600 px-4 text-base font-semibold text-white hover:bg-emerald-700"
              >
                Към вход
              </button>
            </div>
          )}
          {access.allowed && (
            <>
          {controllerState === 'pairing' && renderPairingScreen()}
          {controllerState === 'waiting' && renderWaitingScreen()}
          {controllerState === 'test' && renderTestScreen()}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ControllerPage;