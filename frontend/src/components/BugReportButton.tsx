import React, { useState, useRef, useCallback } from 'react';
import axios from 'axios';
import { useLocation } from 'react-router-dom';
import { API_BASE_URL } from '../services/api';

// ─── Types ────────────────────────────────────────────────────────────────────

type Category = 'bug' | 'suggestion' | 'wrong_answer' | 'other';

const CATEGORIES: { value: Category; label: string; emoji: string }[] = [
  { value: 'bug',          label: 'Нещо не работи',    emoji: '🐛' },
  { value: 'wrong_answer', label: 'Грешен отговор',    emoji: '❌' },
  { value: 'suggestion',   label: 'Идея/предложение',  emoji: '💡' },
  { value: 'other',        label: 'Друго',              emoji: '📝' },
];

// ─── Context collector ────────────────────────────────────────────────────────

function collectContext(route: string) {
  return {
    route,
    timestamp: new Date().toISOString(),
    user_agent: navigator.userAgent,
    screen_size: `${window.screen.width}x${window.screen.height}`,
    language: navigator.language,
    user_id: localStorage.getItem('userId') ?? undefined,
    console_errors: window.__bugReportErrors ?? [],
  };
}

// ─── Modal ────────────────────────────────────────────────────────────────────

interface BugReportModalProps {
  onClose: () => void;
  currentRoute: string;
}

const BugReportModal: React.FC<BugReportModalProps> = ({ onClose, currentRoute }) => {
  const [category, setCategory] = useState<Category>('bug');
  const [message, setMessage] = useState('');
  const [screenshotPreview, setScreenshotPreview] = useState<string | null>(null);
  const [screenshotBase64, setScreenshotBase64] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle');
  const fileRef = useRef<HTMLInputElement>(null);

  const handleScreenshot = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 400_000) {
      alert('Снимката е прекалено голяма (макс. 400KB). Моля, изберете по-малка.');
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      const result = ev.target?.result as string;
      setScreenshotPreview(result);
      setScreenshotBase64(result.split(',')[1]);
    };
    reader.readAsDataURL(file);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim().length < 5) return;

    setStatus('sending');
    const ctx = collectContext(currentRoute);

    try {
      await axios.post(`${API_BASE_URL}/bug-report`, {
        message: message.trim(),
        category,
        screenshot_base64: screenshotBase64,
        ...ctx,
      });
      setStatus('success');
      setTimeout(onClose, 2000);
    } catch {
      setStatus('error');
    }
  };

  const isSuccess = status === 'success';
  const isSending = status === 'sending';

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 shadow-2xl p-6 flex flex-col gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">🐛</span>
            <h2 className="font-bold text-slate-800 dark:text-slate-100 text-base">
              Докладвай проблем
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xl leading-none"
          >
            ×
          </button>
        </div>

        {isSuccess ? (
          /* Success state */
          <div className="flex flex-col items-center gap-3 py-6">
            <span className="text-4xl">✅</span>
            <p className="font-bold text-slate-800 dark:text-slate-100">Изпратено!</p>
            <p className="text-sm text-slate-500 dark:text-slate-400 text-center">
              Благодарим! Ще разгледаме проблема скоро.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {/* Category chips */}
            <div>
              <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2 block">
                Вид проблем
              </label>
              <div className="flex flex-wrap gap-2">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat.value}
                    type="button"
                    onClick={() => setCategory(cat.value)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-all ${
                      category === cat.value
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-transparent text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-blue-400'
                    }`}
                  >
                    {cat.emoji} {cat.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Message */}
            <div>
              <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2 block">
                Опиши проблема *
              </label>
              <textarea
                required
                minLength={5}
                maxLength={2000}
                rows={4}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Какво се случи? Какво очаквахте да се случи?"
                className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 px-4 py-3 text-sm text-slate-800 dark:text-slate-100 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-slate-400"
              />
              <span className="text-[11px] text-slate-400 float-right">{message.length}/2000</span>
            </div>

            {/* Screenshot upload */}
            <div>
              <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-2 block">
                Снимка (по желание)
              </label>
              {screenshotPreview ? (
                <div className="relative">
                  <img
                    src={screenshotPreview}
                    alt="Screenshot preview"
                    className="rounded-xl border border-slate-200 dark:border-slate-700 max-h-32 object-cover w-full"
                  />
                  <button
                    type="button"
                    onClick={() => { setScreenshotPreview(null); setScreenshotBase64(null); }}
                    className="absolute top-1.5 right-1.5 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs"
                  >
                    ×
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="w-full rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-700 py-3 text-sm text-slate-400 hover:border-blue-400 hover:text-blue-500 transition-colors"
                >
                  📷 Добави снимка
                </button>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleScreenshot}
              />
            </div>

            {/* Context badge */}
            <div className="rounded-lg bg-slate-50 dark:bg-slate-800/60 px-3 py-2 text-[11px] text-slate-400 dark:text-slate-500">
              📍 Страница: <span className="font-mono">{currentRoute}</span>
            </div>

            {/* Error state */}
            {status === 'error' && (
              <p className="text-xs text-red-500 text-center">
                Нещо се обърка. Провери интернет и опитай пак.
              </p>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isSending || message.trim().length < 5}
              className="rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-3 text-sm transition-all"
            >
              {isSending ? '📡 Изпращане...' : '📤 Изпрати доклад'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

// ─── Floating button ──────────────────────────────────────────────────────────

const BugReportButton: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const BUTTON_SIZE = 44;
  const POSITION_KEY = 'bug_report_button_position';
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const dragRef = useRef<{ startX: number; startY: number; originX: number; originY: number; moved: boolean } | null>(null);

  React.useEffect(() => {
    const saved = localStorage.getItem(POSITION_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as { x?: number; y?: number };
        if (typeof parsed.x === 'number' && typeof parsed.y === 'number') {
          setPosition({ x: parsed.x, y: parsed.y });
          return;
        }
      } catch {
        // ignore invalid storage
      }
    }

    const margin = 16;
    const x = window.innerWidth - BUTTON_SIZE - margin;
    const y = window.innerWidth >= 1024 ? window.innerHeight - BUTTON_SIZE - 24 : window.innerHeight - BUTTON_SIZE - 84;
    setPosition({ x, y });
  }, []);

  const clampPosition = (x: number, y: number) => {
    const margin = 8;
    const maxX = window.innerWidth - BUTTON_SIZE - margin;
    const maxY = window.innerHeight - BUTTON_SIZE - margin;
    return {
      x: Math.min(maxX, Math.max(margin, x)),
      y: Math.min(maxY, Math.max(margin, y)),
    };
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (!position) return;
    dragRef.current = {
      startX: event.clientX,
      startY: event.clientY,
      originX: position.x,
      originY: position.y,
      moved: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (!dragRef.current) return;
    const deltaX = event.clientX - dragRef.current.startX;
    const deltaY = event.clientY - dragRef.current.startY;
    if (Math.abs(deltaX) > 4 || Math.abs(deltaY) > 4) {
      dragRef.current.moved = true;
    }
    const next = clampPosition(dragRef.current.originX + deltaX, dragRef.current.originY + deltaY);
    setPosition(next);
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (!dragRef.current) return;
    event.currentTarget.releasePointerCapture(event.pointerId);

    if (dragRef.current.moved && position) {
      localStorage.setItem(POSITION_KEY, JSON.stringify(position));
    } else {
      setIsOpen(true);
    }

    dragRef.current = null;
  };

  return (
    <>
      {/* Floating trigger */}
      <button
        title="Докладвай проблем"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        style={position ? { left: position.x, top: position.y } : undefined}
        className="fixed z-50 w-11 h-11 rounded-full bg-slate-700/55 hover:bg-slate-700/75 dark:bg-slate-800/60 dark:hover:bg-slate-700/80 text-white shadow-lg backdrop-blur-sm flex items-center justify-center transition-all hover:scale-110 active:scale-95 touch-none"
      >
        <span className="text-base">🐛</span>
      </button>

      {isOpen && (
        <BugReportModal
          onClose={() => setIsOpen(false)}
          currentRoute={location.pathname}
        />
      )}
    </>
  );
};

// ─── Error capture (call once in app root) ───────────────────────────────────

declare global {
  interface Window {
    __bugReportErrors?: string[];
  }
}

export function installBugReportErrorCapture() {
  if (typeof window === 'undefined') return;
  const store: string[] = [];
  window.__bugReportErrors = store;
  const originalError = console.error.bind(console);
  console.error = (...args: unknown[]) => {
    const msg = args.map(String).join(' ').slice(0, 500);
    store.push(`[${new Date().toISOString()}] ${msg}`);
    if (store.length > 20) store.shift();
    originalError(...args);
  };
}

export default BugReportButton;
