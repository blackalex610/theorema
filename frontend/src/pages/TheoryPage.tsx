import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { useParams } from 'react-router-dom';
import { getGeneratedExamples, getGeneratedTheory, getLesson, getVideoSearchQueries, getContentStatus, type GeneratedExampleItem, type Lesson } from '../services/curriculum';
import { searchYouTubeVideos, type YouTubeVideo } from '../services/youtube';
import AppNavbar from '../components/AppNavbar';
import { TheoryContentSkeleton, VideoGridSkeleton } from '../components/Skeleton';

const ASK_ASSISTANT_EVENT = 'ask-assistant-from-selection';

const TOC_ITEMS = [
  { id: 'teoriya', label: 'Теория' },
  { id: 'videа', label: 'Видеа' },
  { id: 'primeri', label: 'Примерни задачи' },
];

const markdownRenderers = {
  code({ inline, children, ...props }: any) {
    return inline ? (
      <code className="bg-gray-100 dark:bg-slate-900 rounded px-1 py-0.5 text-sm" {...props}>{children}</code>
    ) : (
      <pre className="bg-gray-100 dark:bg-slate-900 rounded-lg p-3 overflow-x-auto text-sm"><code {...props}>{children}</code></pre>
    );
  },
  table({ children }: any) {
    return <table className="border border-gray-200 dark:border-slate-700">{children}</table>;
  },
  th({ children }: any) {
    return <th className="border border-gray-200 dark:border-slate-700 px-2 py-1 bg-gray-50 dark:bg-slate-900 font-semibold">{children}</th>;
  },
  td({ children }: any) {
    return <td className="border border-gray-200 dark:border-slate-700 px-2 py-1">{children}</td>;
  },
  blockquote({ children }: any) {
    return <blockquote className="border-l-4 border-blue-300 dark:border-blue-400 pl-4 italic text-gray-600 dark:text-slate-300 my-2">{children}</blockquote>;
  },
};

const TheoryPage: React.FC = () => {
  const { lessonId } = useParams<{ lessonId: string }>();
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [videos, setVideos] = useState<YouTubeVideo[]>([]);
  const [videosLoading, setVideosLoading] = useState(false);
  const [activeVideo, setActiveVideo] = useState<string | null>(null);
  const [videoSearchInfo, setVideoSearchInfo] = useState<string | null>(null);
  const [theoryContent, setTheoryContent] = useState<string>('');
  const [theoryLoading, setTheoryLoading] = useState(false);
  const [theoryError, setTheoryError] = useState<string | null>(null);
  const [detailLevel, setDetailLevel] = useState<'concise' | 'standard' | 'detailed' | null>(null);
  const [cachedLevels, setCachedLevels] = useState<Set<string>>(new Set());
  const [showUncachedWarning, setShowUncachedWarning] = useState(false);
  const [pendingLevel, setPendingLevel] = useState<'concise' | 'standard' | 'detailed' | null>(null);
  const [examples, setExamples] = useState<GeneratedExampleItem[]>([]);
  const [examplesLoading, setExamplesLoading] = useState(false);
  const [examplesError, setExamplesError] = useState<string | null>(null);
  const [revealedExamples, setRevealedExamples] = useState<Record<number, boolean>>({});
  const [selectedText, setSelectedText] = useState('');
  const [askButtonVisible, setAskButtonVisible] = useState(false);
  const [askButtonPos, setAskButtonPos] = useState({ x: 0, y: 0 });
  const noApiKey = !import.meta.env.VITE_YOUTUBE_KEY;

  // Refs for smooth scroll
  const teoriyaRef = useRef<HTMLDivElement>(null);
  const videaRef = useRef<HTMLDivElement>(null);
  const primeriRef = useRef<HTMLDivElement>(null);
  const theoryTextBoxRef = useRef<HTMLDivElement>(null);
  const selectionTimerRef = useRef<number | null>(null);
  const refs: Record<string, React.RefObject<HTMLDivElement | null>> = {
    teoriya: teoriyaRef,
    videа: videaRef,
    primeri: primeriRef,
  };

  useEffect(() => {
    const fetchLesson = async () => {
      if (!lessonId) return;
      try {
        setLoading(true);
        const lessonData = await getLesson(parseInt(lessonId));
        setLesson(lessonData);

        // Check which levels are cached
        try {
          const status = await getContentStatus(parseInt(lessonId));
          const levels = new Set(status.cached_levels);
          setCachedLevels(levels);
          // Auto-load standard if cached, else show modal
          if (levels.has('standard')) {
            setDetailLevel('standard');
          } else if (levels.has('concise')) {
            setDetailLevel('concise');
          } else if (levels.has('detailed')) {
            setDetailLevel('detailed');
          }
          // else detailLevel stays null → modal will show
        } catch {
          // If status check fails, show modal
        }
      } catch (err) {
        setError('Грешка при зареждане на теорията');
        console.error('Error fetching lesson:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchLesson();
  }, [lessonId]);

  useEffect(() => {
    const clearSelectionTimer = () => {
      if (selectionTimerRef.current !== null) {
        window.clearTimeout(selectionTimerRef.current);
        selectionTimerRef.current = null;
      }
    };

    const hideAskButton = () => {
      clearSelectionTimer();
      setAskButtonVisible(false);
    };

    const isSelectionInsideTheory = (selection: Selection): boolean => {
      const root = theoryTextBoxRef.current;
      if (!root || selection.rangeCount === 0) return false;
      const range = selection.getRangeAt(0);
      const container = range.commonAncestorContainer;
      const element = container.nodeType === Node.TEXT_NODE ? container.parentElement : (container as Element);
      if (!element) return false;
      return root.contains(element);
    };

    const updateSelection = () => {
      clearSelectionTimer();

      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
        setAskButtonVisible(false);
        return;
      }

      const text = selection.toString().trim();
      if (!text || !isSelectionInsideTheory(selection)) {
        setAskButtonVisible(false);
        return;
      }

      selectionTimerRef.current = window.setTimeout(() => {
        const activeSelection = window.getSelection();
        if (!activeSelection || activeSelection.rangeCount === 0 || activeSelection.isCollapsed) {
          setAskButtonVisible(false);
          return;
        }

        const stableText = activeSelection.toString().trim();
        if (!stableText || !isSelectionInsideTheory(activeSelection)) {
          setAskButtonVisible(false);
          return;
        }

        const rect = activeSelection.getRangeAt(0).getBoundingClientRect();
        if (!rect.width && !rect.height) {
          setAskButtonVisible(false);
          return;
        }

        setSelectedText(stableText);
        setAskButtonPos({
          x: Math.min(window.innerWidth - 170, Math.max(10, rect.left)),
          y: Math.min(window.innerHeight - 60, Math.max(10, rect.bottom + 8)),
        });
        setAskButtonVisible(true);
      }, 500);
    };

    document.addEventListener('selectionchange', updateSelection);
    window.addEventListener('scroll', hideAskButton, true);
    window.addEventListener('resize', hideAskButton);

    return () => {
      document.removeEventListener('selectionchange', updateSelection);
      window.removeEventListener('scroll', hideAskButton, true);
      window.removeEventListener('resize', hideAskButton);
      clearSelectionTimer();
    };
  }, []);

  useEffect(() => {
    if (!lesson || !lessonId) return;
    const fetchVideos = async () => {
      setVideosLoading(true);
      try {
        const primaryQuery = `${lesson.title} математика на български`;
        let results = await searchYouTubeVideos(primaryQuery, 9);

        if (results.length > 0) {
          setVideoSearchInfo(null);
          setVideos(results);
          return;
        }

        // AI fallback: rephrase concept and retry with multiple search variants.
        const queryResponse = await getVideoSearchQueries(parseInt(lessonId));
        for (const q of queryResponse.queries) {
          results = await searchYouTubeVideos(`${q} на български`, 9);
          if (results.length > 0) {
            setVideoSearchInfo(`Показани са резултати от алтернативно търсене: "${q}"`);
            setVideos(results);
            return;
          }
        }

        setVideoSearchInfo(null);
        setVideos([]);
      } catch (err) {
        console.error('YouTube fetch error:', err);
      } finally {
        setVideosLoading(false);
      }
    };
    fetchVideos();
  }, [lesson, lessonId]);

  useEffect(() => {
    if (!lessonId || !detailLevel) return;

    const fetchGeneratedTheory = async () => {
      try {
        setTheoryLoading(true);
        setTheoryError(null);
        const data = await getGeneratedTheory(parseInt(lessonId), detailLevel);
        setTheoryContent(data.content);
        // Mark this level as cached now
        setCachedLevels(prev => new Set([...prev, detailLevel]));
      } catch (err: any) {
        console.error('Theory generation error:', err);
        const detail = err?.response?.data?.detail;
        let message = 'Грешка при генериране на теорията';
        if (typeof detail === 'string') message = detail;
        else if (detail?.message) message = detail.message;
        setTheoryError(message);
      } finally {
        setTheoryLoading(false);
      }
    };

    fetchGeneratedTheory();
  }, [lessonId, detailLevel]);

  useEffect(() => {
    if (!lessonId) return;

    const fetchGeneratedExamples = async () => {
      try {
        setExamplesLoading(true);
        setExamplesError(null);
        const data = await getGeneratedExamples(parseInt(lessonId));
        setExamples(data.examples);
        setRevealedExamples({});
      } catch (err: any) {
        console.error('Examples generation error:', err);
        const message = err?.response?.data?.detail || 'Грешка при генериране на примерни задачи';
        setExamplesError(message);
      } finally {
        setExamplesLoading(false);
      }
    };

    fetchGeneratedExamples();
  }, [lessonId]);

  const scrollTo = (id: string) => {
    refs[id]?.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const handleDetailLevelChange = (level: 'concise' | 'standard' | 'detailed') => {
    if (level === detailLevel) return;
    if (cachedLevels.has(level)) {
      setDetailLevel(level);
    } else {
      setPendingLevel(level);
      setShowUncachedWarning(true);
    }
  };

  const confirmUncachedLevel = () => {
    if (pendingLevel) {
      setDetailLevel(pendingLevel);
    }
    setShowUncachedWarning(false);
    setPendingLevel(null);
  };

  const toggleExampleAnswer = (index: number) => {
    setRevealedExamples((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  const difficultyLabel = (difficulty: 'easy' | 'medium' | 'hard') => {
    if (difficulty === 'easy') return 'Лесно';
    if (difficulty === 'medium') return 'Средно';
    return 'Трудно';
  };

  const difficultyClass = (difficulty: 'easy' | 'medium' | 'hard') => {
    if (difficulty === 'easy') return 'bg-green-100 text-green-700';
    if (difficulty === 'medium') return 'bg-yellow-100 text-yellow-700';
    return 'bg-red-100 text-red-700';
  };

  const handleAskAssistantFromSelection = () => {
    const text = selectedText.trim();
    if (!text) return;

    window.dispatchEvent(new CustomEvent(ASK_ASSISTANT_EVENT, {
      detail: {
        text,
        source: 'theory-selection',
      },
    }));

    setAskButtonVisible(false);
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-transparent">
      <AppNavbar maxWidthClassName="max-w-5xl" />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-red-800 text-sm">
            {error}
          </div>
        )}

        {/* Title */}
        <h2 className="text-4xl font-bold text-gray-900 dark:text-slate-100 mb-2">
          {lesson?.title || 'Теория'}
        </h2>
        <p className="text-gray-500 dark:text-slate-300 mb-8 text-sm">
          Урок #{lessonId} {loading && '• Зареждане на данни...'}
        </p>

        {/* Quick-jump table of contents */}
        <div className="bg-white dark:bg-slate-950/60 border border-gray-200 dark:border-indigo-400/25 rounded-xl shadow-sm p-5 mb-10 motion-fade-up">
          <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-slate-400 mb-3">
            Съдържание
          </h3>
          <ol className="space-y-2">
            {TOC_ITEMS.map((item, idx) => (
              <li key={item.id}>
                <button
                  onClick={() => scrollTo(item.id)}
                  className="flex items-center gap-2 text-blue-600 dark:text-blue-300 hover:text-blue-800 dark:hover:text-blue-200 hover:underline text-left"
                >
                  <span className="w-5 h-5 rounded-full bg-blue-100 dark:bg-blue-500/15 text-blue-700 dark:text-blue-200 text-xs flex items-center justify-center font-bold shrink-0">
                    {idx + 1}
                  </span>
                  {item.label}
                </button>
              </li>
            ))}
          </ol>
        </div>

        {/* ── Detail level picker modal (only shown when nothing is cached) ── */}
        {!detailLevel && !loading && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 backdrop-blur-sm">
            <div className="bg-white dark:bg-slate-950/95 border border-gray-200 dark:border-indigo-400/25 rounded-2xl shadow-2xl p-8 max-w-sm w-full mx-4 motion-fade-up">
              <h2 className="text-xl font-bold text-gray-900 dark:text-slate-100 mb-1 text-center">Ниво на обяснение</h2>
              <p className="text-sm text-gray-500 dark:text-slate-300 text-center mb-6">Тази тема не е генерирана. Избери ниво и ще бъде запазена за следващия път.</p>
              <div className="flex flex-col gap-3">
                {([
                  { level: 'concise' as const, label: 'Накратко', desc: 'Само ключовото — формула и един пример (~150 думи)', icon: '⚡' },
                  { level: 'standard' as const, label: 'Стандартно', desc: 'Балансирано обяснение с два примера (~250 думи)', icon: '📖' },
                  { level: 'detailed' as const, label: 'Подробно', desc: 'Изчерпателно с три примера и допълнителни бележки (~500 думи)', icon: '🔬' },
                ]).map(({ level, label, desc, icon }) => (
                  <button
                    key={level}
                    onClick={() => setDetailLevel(level)}
                    className="flex items-start gap-4 text-left px-5 py-4 rounded-xl border-2 border-gray-200 dark:border-slate-700 hover:border-blue-400 dark:hover:border-blue-400/70 bg-white dark:bg-slate-900/80 hover:bg-blue-50 dark:hover:bg-blue-500/10 transition-colors group motion-card"
                  >
                    <span className="text-2xl mt-0.5 motion-icon">{icon}</span>
                    <div>
                      <p className="font-semibold text-gray-900 dark:text-slate-100 group-hover:text-blue-700 dark:group-hover:text-blue-200">{label}</p>
                      <p className="text-xs text-gray-500 dark:text-slate-400 mt-0.5">{desc}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Uncached level warning dialog ── */}
        {showUncachedWarning && pendingLevel && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 backdrop-blur-sm">
            <div className="bg-white dark:bg-slate-950/95 border border-gray-200 dark:border-indigo-400/25 rounded-2xl shadow-2xl p-8 max-w-sm w-full mx-4 motion-fade-up">
              <div className="text-3xl mb-3 text-center">⏳</div>
              <h2 className="text-lg font-bold text-gray-900 dark:text-slate-100 mb-2 text-center">Генерирането може да отнеме момент</h2>
              <p className="text-sm text-gray-500 dark:text-slate-300 text-center mb-6">
                Нивото „{ { concise: 'Накратко', standard: 'Стандартно', detailed: 'Подробно' }[pendingLevel] }" все още не е запазено. То ще бъде генерирано и съхранено автоматично.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => { setShowUncachedWarning(false); setPendingLevel(null); }}
                  className="flex-1 px-4 py-2 rounded-xl border border-gray-200 dark:border-slate-700 text-gray-600 dark:text-slate-400 hover:bg-gray-50 dark:hover:bg-slate-800 text-sm font-medium transition-colors"
                >
                  Отказ
                </button>
                <button
                  onClick={confirmUncachedLevel}
                  className="flex-1 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold transition-colors"
                >
                  Продължи
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── 1. Теория ── */}
        <section ref={teoriyaRef} className="mb-14 scroll-mt-20">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 dark:border-slate-700 pb-2 mb-5">
            <h3 className="text-2xl font-bold text-gray-900 dark:text-slate-100">1. Теория</h3>
            {detailLevel && (
            <div className="flex items-center gap-1 rounded-2xl border border-gray-200 dark:border-slate-700 bg-gray-100 dark:bg-slate-900/85 p-1 shadow-sm motion-fade-up">
              {(['concise', 'standard', 'detailed'] as const).map((level) => {
                const labels = { concise: 'Накратко', standard: 'Стандартно', detailed: 'Подробно' };
                const isCached = cachedLevels.has(level);
                return (
                  <button
                    key={level}
                    onClick={() => handleDetailLevelChange(level)}
                    disabled={theoryLoading}
                    className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all motion-pill ${
                      detailLevel === level
                        ? 'bg-white dark:bg-slate-800 text-blue-700 dark:text-blue-200 shadow-sm ring-1 ring-blue-200 dark:ring-blue-400/20'
                        : 'text-gray-500 dark:text-slate-400 hover:text-gray-800 dark:hover:text-slate-100'
                    } disabled:opacity-50`}
                  >
                    {labels[level]}{!isCached && <span className="ml-1 text-xs opacity-60">✦</span>}
                  </button>
                );
              })}
            </div>
            )}
          </div>
          <div ref={theoryTextBoxRef} className="bg-white dark:bg-slate-950/60 rounded-xl shadow-sm border border-gray-200 dark:border-indigo-400/25 p-6 prose prose-blue dark:prose-invert max-w-none text-gray-700 dark:text-slate-200">
            {theoryLoading ? (
              <TheoryContentSkeleton />
            ) : theoryError ? (
              <div className="bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-500/30 rounded-lg p-4">
                <p className="text-red-800 text-sm font-medium">{theoryError}</p>
                <p className="text-red-700 text-sm mt-2">
                  Добавете OpenAI ключ в backend `.env` като `OPENAI_API_KEY=...` и рестартирайте сървъра.
                </p>
              </div>
            ) : (
              <div className="prose prose-blue dark:prose-invert max-w-none text-gray-800 dark:text-slate-200">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={markdownRenderers}
                >
                  {theoryContent || 'Няма генерирано съдържание.'}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </section>

        {/* ── 2. Видеа ── */}
        <section ref={videaRef} className="mb-14 scroll-mt-20">
          <h3 className="text-2xl font-bold text-gray-900 border-b border-gray-200 pb-2 mb-5">
            2. Видеа
          </h3>

          {noApiKey ? (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-amber-800">
              <p className="font-semibold mb-1">YouTube API ключът не е конфигуриран</p>
              <p className="text-sm">
                Добавете <code className="bg-amber-100 px-1 rounded">VITE_YOUTUBE_KEY</code> в{' '}
                <code className="bg-amber-100 px-1 rounded">.env</code> файла на frontend директорията,
                за да се зареждат видеа автоматично.
              </p>
            </div>
          ) : videosLoading ? (
            <VideoGridSkeleton count={9} />
          ) : videos.length === 0 ? (
            <div className="bg-white border border-gray-200 rounded-xl p-6 text-gray-500 text-center">
              Не са намерени видеа за този урок.
            </div>
          ) : (
            <div>
              {videoSearchInfo && (
                <div className="mb-4 p-3 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 text-sm">
                  {videoSearchInfo}
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {videos.map((video) =>
                activeVideo === video.videoId ? (
                  <div key={video.videoId} className="rounded-xl overflow-hidden shadow-md col-span-1">
                    <div className="relative" style={{ paddingTop: '56.25%' }}>
                      <iframe
                        className="absolute inset-0 w-full h-full"
                        src={`https://www.youtube.com/embed/${video.videoId}?autoplay=1`}
                        title={video.title}
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowFullScreen
                      />
                    </div>
                    <div className="bg-white p-3">
                      <p className="text-sm font-medium text-gray-800 line-clamp-2">{video.title}</p>
                      <p className="text-xs text-gray-400 mt-1">{video.channelTitle}</p>
                    </div>
                  </div>
                ) : (
                  <button
                    key={video.videoId}
                    onClick={() => setActiveVideo(video.videoId)}
                    className="rounded-xl overflow-hidden shadow-sm border border-gray-200 bg-white hover:shadow-md transition-shadow text-left group"
                  >
                    <div className="relative">
                      <img
                        src={video.thumbnail}
                        alt={video.title}
                        className="w-full object-cover"
                      />
                      {/* Play overlay */}
                      <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/40 transition-colors">
                        <div className="w-12 h-12 rounded-full bg-red-600 flex items-center justify-center shadow-lg">
                          <svg className="w-5 h-5 text-white ml-1" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M6.3 2.841A1.5 1.5 0 004 4.11v11.78a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z" />
                          </svg>
                        </div>
                      </div>
                    </div>
                    <div className="p-3">
                      <p className="text-sm font-medium text-gray-800 line-clamp-2">{video.title}</p>
                      <p className="text-xs text-gray-400 mt-1">{video.channelTitle}</p>
                    </div>
                  </button>
                )
              )}
              </div>
            </div>
          )}
        </section>

        {/* ── 3. Примерни задачи ── */}
        <section ref={primeriRef} className="mb-14 scroll-mt-20">
          <h3 className="text-2xl font-bold text-gray-900 border-b border-gray-200 pb-2 mb-5">
            3. Примерни задачи
          </h3>
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 text-gray-700">
            {examplesLoading ? (
              <TheoryContentSkeleton />
            ) : examplesError ? (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <p className="text-red-800 text-sm font-medium">{examplesError}</p>
              </div>
            ) : examples.length === 0 ? (
              <p className="text-gray-500">Няма генерирани примерни задачи.</p>
            ) : (
              <div className="space-y-4">
                {examples.map((item, idx) => (
                  <div key={idx} className="rounded-lg border border-gray-200 p-4 bg-gray-50">
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-semibold text-gray-900">Задача {idx + 1}</p>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${difficultyClass(item.difficulty)}`}>
                        {difficultyLabel(item.difficulty)}
                      </span>
                    </div>
                    <div className="text-gray-800 dark:text-slate-200 mb-3 prose prose-sm prose-blue dark:prose-invert max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={markdownRenderers}>
                        {item.problem}
                      </ReactMarkdown>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleExampleAnswer(idx)}
                      className="mb-3 px-3 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700"
                    >
                      {revealedExamples[idx] ? 'Скрий решението' : 'Покажи решението'}
                    </button>

                    {revealedExamples[idx] && (
                      <div className="rounded-md bg-green-50 border border-green-200 p-3">
                        <p className="text-green-900 font-medium mb-1">Решение</p>
                        <div className="text-green-800 prose prose-sm prose-green max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={markdownRenderers}>
                            {item.solution}
                          </ReactMarkdown>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

      </main>

      {askButtonVisible && (
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={handleAskAssistantFromSelection}
          className="fixed z-40 rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-lg hover:bg-blue-700"
          style={{ left: askButtonPos.x, top: askButtonPos.y }}
        >
          Ask Assistant
        </button>
      )}
    </div>
  );
};

export default TheoryPage;