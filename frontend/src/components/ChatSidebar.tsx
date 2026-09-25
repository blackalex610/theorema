import React, { Suspense, lazy, useEffect, useEffectEvent, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { sendChatMessage, type ChatMessage } from '../services/ai';
import UpgradePrompt from './UpgradePrompt';

// react-markdown and its parser are ~350 KB before minification; loaded only
// once a message is on screen instead of in every page's entry bundle.
const ChatMarkdown = lazy(() => import('./ChatMarkdown'));
import { apiErrorDetail, getLimitErrorDetail } from '../services/api';
import { usePlan } from '../hooks/usePlan';
import { usePlanPrompt } from '../hooks/usePlanPrompt';

const ASK_ASSISTANT_EVENT = 'ask-assistant-from-selection';

interface ChatSidebarProps {
  isOpen: boolean;
  onOpen: () => void;
  onClose: () => void;
}


const ChatSidebar: React.FC<ChatSidebarProps> = ({ isOpen, onOpen, onClose }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: 'Здравей! Аз съм AI помощникът по математика. Питай ме всичко за урока.',
    },
  ]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [limitError, setLimitError] = useState<{ feature: string; message: string } | null>(null);

  const { status: planStatus } = usePlan();
  const { maybeShow: maybeShowUpgrade, dismiss: dismissUpgrade } = usePlanPrompt(setLimitError);
  const location = useLocation();
  const navigate = useNavigate();

  const lessonTitleContext = useMemo(() => {
    const match = location.pathname.match(/\/learn\/lessons\/(\d+)\/theory/);
    if (!match) return undefined;
    return `Lesson ${match[1]}`;
  }, [location.pathname]);

  const sendUserPrompt = async (promptText: string) => {
    const trimmed = promptText.trim();
    if (!trimmed || isSending) return;

    const nextMessages: ChatMessage[] = [...messages, { role: 'user', content: trimmed }];
    setMessages(nextMessages);
    setInput('');
    setIsSending(true);

    try {
      const reply = await sendChatMessage(nextMessages, lessonTitleContext);
      setMessages((prev) => [...prev, { role: 'assistant', content: reply }]);
    } catch (err) {
      const serverDetail = apiErrorDetail(err);
        const limitDetail = getLimitErrorDetail(err);
        if (limitDetail) {
          maybeShowUpgrade({
            feature: limitDetail.feature,
            message: limitDetail.message,
            daysSinceSignup: planStatus.days_since_signup,
            isPremium: planStatus.is_premium,
          });
        } else {
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: typeof serverDetail === 'string' && serverDetail.trim()
                ? `Грешка от AI услугата: ${serverDetail}`
                : 'В момента не успях да отговоря. Опитай пак след малко.',
            },
          ]);
        }
    } finally {
      setIsSending(false);
    }
  };

  const handleSend = async () => {
    await sendUserPrompt(input);
  };

  // The shortcut buttons are memoised per page, so they must not capture this
  // render's sendUserPrompt: it closes over `messages`, and a stale copy sent
  // an old history and then overwrote the conversation with it.
  const sendUserPromptRef = useRef(sendUserPrompt);
  useEffect(() => {
    sendUserPromptRef.current = sendUserPrompt;
  });

  const shortcutItems = useMemo(() => {
    const path = location.pathname;
    
    // Theory page - show theory-related actions
    if (path.includes('/theory')) {
      return [
        {
          label: '🔍 Обясни по-просто',
          tone: 'bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 text-blue-700 dark:text-blue-300',
          run: () => sendUserPromptRef.current('Обясни ми текущата тема по-просто, със стъпка по стъпка пример.'),
        },
        {
          label: '📝 Дай ми примерни задачи',
          tone: 'bg-violet-50 hover:bg-violet-100 dark:bg-violet-900/30 dark:hover:bg-violet-900/50 text-violet-700 dark:text-violet-300',
          run: () => sendUserPromptRef.current('Дай ми 3 примерни задачи с решения по текущата тема.'),
        },
        {
          label: '🎯 Тествай ме',
          tone: 'bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-900/30 dark:hover:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300',
          run: () => sendUserPromptRef.current('Дай ми 1 тестова задача за текущата тема. След отговора ми кажи дали е верен.'),
        },
      ];
    }
    
    // Grades/Topics/Lessons pages - navigation actions
    if (path.includes('/grades') || path.includes('/topics') || path.includes('/lessons')) {
      return [
        {
          label: '📚 Към уроците',
          tone: 'bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 text-blue-700 dark:text-blue-300',
          run: () => {
            navigate('/learn/grades');
            onClose();
          },
        },
        {
          label: '✏️ Към упражненията',
          tone: 'bg-violet-50 hover:bg-violet-100 dark:bg-violet-900/30 dark:hover:bg-violet-900/50 text-violet-700 dark:text-violet-300',
          run: () => {
            navigate('/grades');
            onClose();
          },
        },
        {
          label: '🏠 Начало',
          tone: 'bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-900/30 dark:hover:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300',
          run: () => {
            navigate('/dashboard');
            onClose();
          },
        },
      ];
    }
    
    // NVO/Exam pages - exam-related actions
    if (path.includes('/nvo') || path.includes('/exam')) {
      return [
        {
          label: '📖 Теория за НВО',
          tone: 'bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 text-blue-700 dark:text-blue-300',
          run: () => {
            navigate('/learn/grades');
            onClose();
          },
        },
        {
          label: '📝 Примерни задачи',
          tone: 'bg-violet-50 hover:bg-violet-100 dark:bg-violet-900/30 dark:hover:bg-violet-900/50 text-violet-700 dark:text-violet-300',
          run: () => sendUserPromptRef.current('Дай ми 3 примерни задачи по математика за 7. клас с решения.'),
        },
        {
          label: '🏠 Начало',
          tone: 'bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-900/30 dark:hover:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300',
          run: () => {
            navigate('/dashboard');
            onClose();
          },
        },
      ];
    }
    
    // Default/Dashboard - general actions
    return [
      {
        label: '📚 Уроци за учене',
        tone: 'bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 text-blue-700 dark:text-blue-300',
        run: () => {
          navigate('/learn/grades');
          onClose();
        },
      },
      {
        label: '✏️ Упражнения',
        tone: 'bg-violet-50 hover:bg-violet-100 dark:bg-violet-900/30 dark:hover:bg-violet-900/50 text-violet-700 dark:text-violet-300',
        run: () => {
          navigate('/grades');
          onClose();
        },
      },
      {
        label: '📝 НВО Подготовка',
        tone: 'bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-900/30 dark:hover:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300',
        run: () => {
          navigate('/nvo/practice');
          onClose();
        },
      },
    ];
  }, [location.pathname, navigate, onClose]);

  const onAskAssistant = useEffectEvent((event: Event) => {
    const customEvent = event as CustomEvent<{ text?: string }>;
    const text = customEvent.detail?.text?.trim() || '';
    if (!text) return;
    void sendUserPrompt(text);
  });

  useEffect(() => {
    const handleAskAssistantEvent = (event: Event) => onAskAssistant(event);
    window.addEventListener(ASK_ASSISTANT_EVENT, handleAskAssistantEvent);
    return () => {
      window.removeEventListener(ASK_ASSISTANT_EVENT, handleAskAssistantEvent);
    };
  }, []);

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/25 z-30 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
        {limitError && (
          <UpgradePrompt
            feature={limitError.feature}
            message={limitError.message}
            onClose={dismissUpgrade}
          />
        )}

      <aside
        className={`hidden lg:flex shrink-0 flex-col border-l border-slate-200 bg-white transition-all duration-300 dark:border-slate-800 dark:bg-slate-900 overflow-hidden ${
          isOpen ? 'w-[420px]' : 'w-14'
        } ${isOpen ? '' : 'cursor-pointer hover:bg-blue-50/40 dark:hover:bg-blue-900/10'}`}
        onClick={!isOpen ? onOpen : undefined}
      >
        <div className={`flex items-center border-b border-slate-100 px-2 py-3 dark:border-slate-800 ${isOpen ? 'justify-between' : 'justify-center'}`}>
          {isOpen ? (
            <>
              <div className="px-2">
                <div className="flex items-center gap-2">
                  <span className="relative inline-flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 via-blue-500 to-violet-600 text-white text-sm shadow-sm ring-2 ring-blue-100 dark:ring-blue-400/20">
                    (•ᴗ•)
                    <span className="absolute -right-0.5 -bottom-0.5 h-2.5 w-2.5 rounded-full border border-white bg-emerald-500 dark:border-slate-900" />
                  </span>
                  <h3 className="font-semibold text-gray-900 dark:text-slate-100">Mati AI</h3>
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    Online
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-slate-400">Помощ по математика</p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors dark:hover:bg-slate-800 dark:hover:text-slate-200"
                title="Свий"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={onOpen}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors dark:hover:bg-slate-800 dark:hover:text-slate-200"
              title="Разшири"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          )}
        </div>

        {isOpen ? (
          <>
            <div className="border-b border-slate-100 dark:border-slate-800 px-3 py-2 space-y-1.5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 px-1">Бързи действия</p>
              {shortcutItems.map((item) => (
                <button
                  key={item.label}
                  onClick={item.run}
                  disabled={isSending}
                  className={`w-full rounded-xl px-3 py-2 text-xs font-semibold text-left transition-colors disabled:opacity-50 ${item.tone}`}
                >
                  {item.label}
                </button>
              ))}
            </div>

            <div className="flex-1 overflow-y-auto no-scrollbar p-4 space-y-3">
              {messages.map((msg, idx) => (
                <div key={idx} className="flex flex-col gap-1">
                  <div
                    className={`rounded-lg px-3 py-2 text-sm whitespace-pre-line ${
                      msg.role === 'assistant'
                        ? 'bg-gray-100 dark:bg-slate-800/80 text-gray-800 dark:text-slate-100'
                        : 'bg-blue-600 text-white ml-8'
                    }`}
                  >
                    <Suspense fallback={msg.content}>
                      <ChatMarkdown content={msg.content} />
                    </Suspense>
                  </div>
                </div>
              ))}

              {isSending && (
                <div className="rounded-lg px-3 py-2 text-sm bg-gray-100 dark:bg-slate-800/80 text-gray-600 dark:text-slate-300">
                  AI мисли...
                </div>
              )}
            </div>

            <div className="h-20 border-t border-gray-200 dark:border-slate-700 p-3 flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSend();
                }}
                placeholder="Напиши въпрос..."
                className="flex-1 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200 dark:focus:ring-blue-500/30"
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={isSending}
                className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-60"
              >
                Изпрати
              </button>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-between border-t border-slate-100 px-2 py-3 dark:border-slate-800">
            <button
              type="button"
              onClick={onOpen}
              className="relative inline-flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 via-blue-500 to-violet-600 text-white text-[11px] shadow-sm ring-2 ring-blue-100 dark:ring-blue-400/20"
              title="Отвори AI чата"
            >
              (•ᴗ•)
              <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-emerald-500 border border-white dark:border-slate-900 animate-pulse" />
            </button>

            <button
              type="button"
              onClick={onOpen}
              className="flex flex-col items-center gap-2 rounded-xl px-1 py-2 text-slate-400 hover:bg-slate-100 hover:text-blue-600 dark:hover:bg-slate-800 dark:hover:text-blue-300 transition-colors"
              title="Pull/Open AI"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
              <span className="text-[10px] font-extrabold tracking-[0.16em] [writing-mode:vertical-rl] rotate-180">OPEN</span>
            </button>

            <div className="flex flex-col items-center gap-1 pb-1 text-blue-500 dark:text-blue-300">
              <span className="h-1 w-1 rounded-full bg-current" />
              <span className="h-1 w-1 rounded-full bg-current" />
              <span className="h-1 w-1 rounded-full bg-current" />
            </div>
          </div>
        )}
      </aside>

      {/* Mobile floating chat button */}
      {!isOpen && (
        <button
          type="button"
          onClick={onOpen}
          className="fixed bottom-20 right-4 z-30 lg:hidden inline-flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 via-blue-500 to-violet-600 text-white shadow-lg shadow-blue-500/30 ring-2 ring-white dark:ring-slate-900"
          title="Отвори AI чата"
        >
          <span className="text-lg leading-none">(•ᴗ•)</span>
          <span className="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full bg-emerald-500 border-2 border-white dark:border-slate-900 animate-pulse" />
        </button>
      )}

      <aside
        className={`fixed top-0 right-0 h-full w-full sm:w-[380px] bg-white dark:bg-slate-950/95 border-l border-gray-200 dark:border-slate-700 shadow-2xl z-40 transform transition-transform duration-300 lg:hidden ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div className="h-16 px-4 border-b border-gray-200 dark:border-slate-700 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="relative inline-flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-sky-400 via-blue-500 to-violet-600 text-white text-sm shadow-sm ring-2 ring-blue-100 dark:ring-blue-400/20">
                (•ᴗ•)
                <span className="absolute -right-0.5 -bottom-0.5 h-2.5 w-2.5 rounded-full border border-white bg-emerald-500 dark:border-slate-900" />
              </span>
              <h3 className="font-semibold text-gray-900 dark:text-slate-100">Mati AI</h3>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Online
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-slate-400">Помощ по математика</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-500 dark:text-slate-400 hover:text-gray-700 dark:hover:text-slate-100 text-sm"
          >
            Затвори
          </button>
        </div>

        <div className="border-b border-slate-100 dark:border-slate-800 px-3 py-2 space-y-1.5">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500 px-1">Бързи действия</p>
          {shortcutItems.map((item) => (
            <button
              key={`mobile-${item.label}`}
              onClick={item.run}
              disabled={isSending}
              className={`w-full rounded-xl px-3 py-2 text-xs font-semibold text-left transition-colors disabled:opacity-50 ${item.tone}`}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="h-[calc(100%-13.5rem)] overflow-y-auto no-scrollbar p-4 space-y-3">
          {messages.map((msg, idx) => (
            <div key={idx} className="flex flex-col gap-1">
              <div
                className={`rounded-lg px-3 py-2 text-sm whitespace-pre-line ${
                  msg.role === 'assistant'
                    ? 'bg-gray-100 dark:bg-slate-800/80 text-gray-800 dark:text-slate-100'
                    : 'bg-blue-600 text-white ml-8'
                }`}
              >
                <Suspense fallback={msg.content}>
                  <ChatMarkdown content={msg.content} />
                </Suspense>
              </div>
            </div>
          ))}

          {isSending && (
            <div className="rounded-lg px-3 py-2 text-sm bg-gray-100 dark:bg-slate-800/80 text-gray-600 dark:text-slate-300">
              AI мисли...
            </div>
          )}
        </div>

        <div className="h-20 border-t border-gray-200 dark:border-slate-700 p-3 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSend();
            }}
            placeholder="Напиши въпрос..."
            className="flex-1 border border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200 dark:focus:ring-blue-500/30"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={isSending}
            className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-60"
          >
            Изпрати
          </button>
        </div>
      </aside>
    </>
  );
};

export default ChatSidebar;
