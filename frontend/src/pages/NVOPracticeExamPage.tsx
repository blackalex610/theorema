import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createNVOGenerationJob, getGeneratedNVOExam, getNVOGenerationJob, submitNVOExam, awardNvoXpDetailed, type NVOExamSubmitResponse, type NVOAwardXpResponse } from '../services/nvo';
import { useXp } from '../context/XpContext';
import UpgradePrompt from '../components/UpgradePrompt';
import { getLimitErrorDetail } from '../services/api';
import { usePlan } from '../hooks/usePlan';
import { usePlanPrompt } from '../hooks/usePlanPrompt';
import { clearActiveTestData, publishActiveTestData } from '../services/activeTest';
import { TEST_ANSWER_IMAGE_EVENT, type SubmitAnswerImageEventPayload } from '../services/testAnswerSync';
import { trackEvent } from '../services/analytics';
import { renderMathText } from '../components/MathRenderer';
import DiagramRenderer from '../components/DiagramRenderer';
import { renderNvoDiagram } from '../components/NvoDiagrams';
import type { NVOQuestion } from '../services/nvo';
import AppNavbar from '../components/AppNavbar';
import NVODifficultySelector, { type NVODifficulty } from '../components/NVODifficultySelector';
import { type NVOFormat } from '../components/NVOFormatSelector';

type QuestionOption = {
  key: string;
  text: string;
};

type BaseQuestion = {
  id: number;
  module: 1 | 2;
  text: string;
  hasDiagram?: boolean;
  diagramType?: string;
  diagramConfig?: Record<string, unknown>;
  topic?: string;
  correctAnswer?: string | string[] | null;
};

type MCQQuestion = BaseQuestion & {
  type: 'mcq';
  options: QuestionOption[];
};

type OpenQuestion = BaseQuestion & {
  type: 'open';
  parts?: string[];
};

type ExamQuestion = MCQQuestion | OpenQuestion;
type OpenPartsAnswer = Record<string, string>;
type AnswerValue = string | OpenPartsAnswer;

type ExamState = {
  examId: string;
  examStarted: boolean;
  questions: ExamQuestion[];
  currentQuestion: number;
  answers: Record<number, AnswerValue>;
  answerImages: Record<number, string>;
  markedForReview: number[];
  timeLeft: number;
};

type ExamHistoryEntry = {
  id: number;
  examId: string;
  status: 'ready' | 'in_progress' | 'unfinished' | 'completed';
  createdAt: string;
  completedAt?: string;
  durationSec: number;
  score: number;
  maxScore: number;
  scorePercent: number;
  module1Percent: number;
  module2Percent: number;
  difficulty?: 'easy' | 'standard' | 'hard';
  format?: 'full' | 'short';
  openResults?: NVOExamSubmitResponse['open_results'];
  questions: ExamQuestion[];
  answers: Record<number, AnswerValue>;
  answerImages: Record<number, string>;
  markedForReview: number[];
  timeLeft?: number;
  currentQuestion?: number;
};

type PreviousResult = {
  id: number;
  date: string;
  status: 'completed' | 'unfinished';
  score: number;
  maxScore: number;
  durationMin: number;
  module1Percent: number;
  module2Percent: number;
  answeredCount: number;
  questionCount: number;
};

const STORAGE_KEY = 'nvo-practice-state-v1';
const HISTORY_KEY = 'nvo-practice-history-v1';
const FULL_EXAM_DURATION_SECONDS = 90 * 60;
const EXAM_DURATION_SECONDS = FULL_EXAM_DURATION_SECONDS;

const DIFFICULTY_LABELS: Record<string, string> = {
  easy: '0.5x XP',
  standard: '1.0x XP',
  hard: '2.0x XP',
};

const DIFFICULTY_COLORS: Record<string, string> = {
  easy: 'text-green-600 bg-green-100',
  standard: 'text-blue-600 bg-blue-100',
  hard: 'text-rose-600 bg-rose-100',
};

const normalizeOptionKey = (value: string) => {
  const key = value.trim().charAt(0).toUpperCase();
  if (key === 'A' || key === 'А') return 'А';
  if (key === 'Б') return 'Б';
  if (key === 'В') return 'В';
  if (key === 'Г') return 'Г';
  return key;
};

const formatBgDateTime = (iso: string) => {
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return dt.toLocaleString('bg-BG', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const createQuestionPlaceholders = (): ExamQuestion[] =>
  Array.from({ length: 23 }, (_, index) => {
    const id = index + 1;
    if (id <= 20) {
      return {
        id,
        module: 1,
        type: 'mcq',
        text: 'Зареждане на задача...',
        options: [
          { key: 'A', text: 'Зареждане...' },
          { key: 'Б', text: 'Зареждане...' },
          { key: 'В', text: 'Зареждане...' },
          { key: 'Г', text: 'Зареждане...' },
        ],
      } as MCQQuestion;
    }

    return {
      id,
      module: 2,
      type: 'open',
      text: 'Зареждане на задача...',
      parts: id === 21 ? undefined : id === 22 ? ['A', 'Б'] : ['A', 'Б', 'В'],
    } as OpenQuestion;
  });

const convertExamQuestions = (questions: NVOQuestion[]): ExamQuestion[] =>
  questions.map((q: NVOQuestion) => {
    if (q.options) {
      const KEY_ORDER = ['А', 'Б', 'В', 'Г'];
      const parsedOptions = q.options.map((opt) => {
        const raw = opt.trim();
        const rawKey = raw.charAt(0);
        const normalizedKey = normalizeOptionKey(rawKey);
        const cleanedText = raw.replace(/^[АБВГAБВГaбвг]\)\s*/u, '').trim();
        return { key: normalizedKey, text: cleanedText };
      }).sort((a, b) => KEY_ORDER.indexOf(a.key) - KEY_ORDER.indexOf(b.key));

      return {
        id: q.number,
        module: q.number <= 20 ? 1 : 2,
        type: 'mcq',
        text: q.question,
        hasDiagram: q.diagram,
        diagramType: q.diagram_type,
        diagramConfig: q.diagram_config,
        topic: q.topic,
        correctAnswer: q.correct_answer,
        options: parsedOptions,
      } as MCQQuestion;
    }

    return {
      id: q.number,
      module: q.number <= 20 ? 1 : 2,
      type: 'open',
      text: q.question,
      hasDiagram: q.diagram,
      diagramType: q.diagram_type,
      diagramConfig: q.diagram_config,
      topic: q.topic,
      correctAnswer: q.correct_answer,
      parts: q.open_parts ?? (q.number === 21 ? undefined : q.number === 22 ? ['A', 'Б'] : ['A', 'Б', 'В']),
    } as OpenQuestion;
  });

const isQuestionAnswered = (question: ExamQuestion, value: AnswerValue | undefined) => {
  if (!value) return false;
  if (question.type === 'mcq') {
    return typeof value === 'string' && value.trim().length > 0;
  }
  if (!question.parts || question.parts.length === 0) {
    return typeof value === 'string' && value.trim().length > 0;
  }
  if (typeof value !== 'object') return false;
  return question.parts.every((part) => (value[part] || '').trim().length > 0);
};

const formatTime = (secondsLeft: number) => {
  const minutes = Math.floor(secondsLeft / 60);
  const seconds = secondsLeft % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
};

const ITEMS_PER_PAGE = 5;
const MAX_HISTORY_ATTEMPTS = 10;

const normalizeHistoryEntry = (entry: Partial<ExamHistoryEntry>): ExamHistoryEntry => ({
  id: entry.id ?? Date.now(),
  examId: entry.examId ?? '',
  status: entry.status ?? 'completed',
  createdAt: entry.createdAt ?? entry.completedAt ?? new Date().toISOString(),
  completedAt: entry.completedAt,
  durationSec: entry.durationSec ?? 0,
  score: entry.score ?? 0,
  maxScore: entry.maxScore ?? 0,
  scorePercent: entry.scorePercent ?? 0,
  module1Percent: entry.module1Percent ?? 0,
  module2Percent: entry.module2Percent ?? 0,
  difficulty: entry.difficulty,
  format: entry.format,
  openResults: entry.openResults ?? [],
  questions: entry.questions ?? [],
  answers: entry.answers ?? {},
  answerImages: entry.answerImages ?? {},
  markedForReview: entry.markedForReview ?? [],
  timeLeft: entry.timeLeft,
  currentQuestion: entry.currentQuestion,
});

const trimHistory = (entries: ExamHistoryEntry[]): ExamHistoryEntry[] => {
  const ready = entries.filter((e) => e.status === 'ready');
  const inProgress = entries.filter((e) => e.status === 'in_progress');
  const attempts = entries
    .filter((e) => e.status === 'completed' || e.status === 'unfinished')
    .sort((a, b) => b.id - a.id)
    .slice(0, MAX_HISTORY_ATTEMPTS);
  return [...ready, ...inProgress.slice(0, 1), ...attempts];
};

const upsertHistoryEntry = (prev: ExamHistoryEntry[], entry: ExamHistoryEntry): ExamHistoryEntry[] => {
  const filtered = prev.filter((item) => item.examId !== entry.examId);
  return trimHistory([entry, ...filtered]);
};

const countAnsweredQuestions = (
  questions: ExamQuestion[],
  answers: Record<number, AnswerValue>,
  answerImages: Record<number, string> = {},
) =>
  questions.filter(
    (q) => isQuestionAnswered(q, answers[q.id]) || (q.type === 'open' && Boolean(answerImages[q.id])),
  ).length;

const computeExamMetrics = (
  questions: ExamQuestion[],
  answers: Record<number, AnswerValue>,
  examStartTimestamp: string | null,
) => {
  let score = 0;
  let maxScore = 0;
  questions.forEach((q) => {
    if (q.type !== 'mcq' || typeof q.correctAnswer !== 'string') return;
    maxScore += 1;
    const selected = answers[q.id];
    if (typeof selected === 'string' && normalizeOptionKey(selected) === normalizeOptionKey(q.correctAnswer)) {
      score += 1;
    }
  });

  const module1 = questions.filter((q) => q.module === 1);
  const module2 = questions.filter((q) => q.module === 2);
  const module1Answered = module1.filter((q) => isQuestionAnswered(q, answers[q.id])).length;
  const module2Answered = module2.filter((q) => isQuestionAnswered(q, answers[q.id])).length;
  const startedAt = examStartTimestamp ? new Date(examStartTimestamp).getTime() : Date.now();
  const durationSec = Math.max(1, Math.floor((Date.now() - startedAt) / 1000));

  return {
    score,
    maxScore,
    scorePercent: maxScore > 0 ? Math.round((score / maxScore) * 100) : 0,
    module1Percent: module1.length > 0 ? Math.round((module1Answered / module1.length) * 100) : 0,
    module2Percent: module2.length > 0 ? Math.round((module2Answered / module2.length) * 100) : 0,
    durationSec,
  };
};

type ExamSnapshot = {
  examId: string;
  examQuestions: ExamQuestion[];
  answers: Record<number, AnswerValue>;
  answerImages: Record<number, string>;
  markedForReview: number[];
  timeLeft: number;
  currentQuestion: number;
  examStartTimestamp: string | null;
  examDifficulty: NVODifficulty;
  existingId?: number;
  createdAt?: string;
};

const buildHistoryEntryFromSnapshot = (
  snapshot: ExamSnapshot,
  status: 'in_progress' | 'unfinished' | 'completed',
): ExamHistoryEntry => {
  const metrics = computeExamMetrics(
    snapshot.examQuestions,
    snapshot.answers,
    snapshot.examStartTimestamp,
  );

  return {
    id: snapshot.existingId ?? Date.now(),
    examId: snapshot.examId,
    status,
    createdAt: snapshot.createdAt ?? new Date().toISOString(),
    completedAt: status === 'completed' ? new Date().toISOString() : undefined,
    durationSec: metrics.durationSec,
    score: metrics.score,
    maxScore: metrics.maxScore,
    scorePercent: metrics.scorePercent,
    module1Percent: metrics.module1Percent,
    module2Percent: metrics.module2Percent,
    difficulty: snapshot.examDifficulty,
    questions: snapshot.examQuestions,
    answers: snapshot.answers,
    answerImages: snapshot.answerImages,
    markedForReview: snapshot.markedForReview,
    timeLeft: snapshot.timeLeft,
    currentQuestion: snapshot.currentQuestion,
  };
};

const persistUnfinishedEntry = (snapshot: ExamSnapshot) => {
  if (!snapshot.examId || snapshot.examQuestions.length === 0) return;
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    const prev = Array.isArray(raw ? JSON.parse(raw) : null)
      ? (JSON.parse(raw!) as Partial<ExamHistoryEntry>[]).map(normalizeHistoryEntry)
      : [];
    const existing = prev.find((item) => item.examId === snapshot.examId);
    const entry = buildHistoryEntryFromSnapshot(
      {
        ...snapshot,
        existingId: existing?.id,
        createdAt: existing?.createdAt ?? existing?.completedAt,
      },
      'unfinished',
    );
    localStorage.setItem(HISTORY_KEY, JSON.stringify(upsertHistoryEntry(prev, entry)));
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore storage errors.
  }
};

const NVOPracticeExamPage: React.FC = () => {
  const navigate = useNavigate();
  // Use non-scoped keys so exam persists across logout/login for same browser
  const storageKey = STORAGE_KEY;
  const historyKey = HISTORY_KEY;
  const isDeveloperMode = import.meta.env.DEV || localStorage.getItem('devMode') === 'true';
  const [examId, setExamId] = useState('');
  const [examStarted, setExamStarted] = useState(false);
  const [examReady, setExamReady] = useState(false);
  const [isReviewMode, setIsReviewMode] = useState(false);
  const [examStartTimestamp, setExamStartTimestamp] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState(1);
  const [answers, setAnswers] = useState<Record<number, AnswerValue>>({});
  const [answerImages, setAnswerImages] = useState<Record<number, string>>({});
  const [partImages, setPartImages] = useState<Record<string, string>>({});
  const [markedForReview, setMarkedForReview] = useState<number[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [showUnansweredWarning, setShowUnansweredWarning] = useState(false);
  const [timeLeft, setTimeLeft] = useState(EXAM_DURATION_SECONDS);
  const [loadingExam, setLoadingExam] = useState(false);
  const [generationJobId, setGenerationJobId] = useState<string | null>(null);
  const [limitError, setLimitError] = useState<{ feature: string; message: string } | null>(null);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [smoothProgress, setSmoothProgress] = useState(0);
  const [generationMessage, setGenerationMessage] = useState('');
  const [examQuestions, setExamQuestions] = useState<ExamQuestion[]>([]);
  const [history, setHistory] = useState<ExamHistoryEntry[]>([]);
  const [isSubmittingExam, setIsSubmittingExam] = useState(false);
  const [selectedDifficulty, setSelectedDifficulty] = useState<NVODifficulty>('standard');
  const [showDifficultySelector, setShowDifficultySelector] = useState(false);
  const [_selectedFormat, _setSelectedFormat] = useState<NVOFormat>('full');
  const [examDifficulty, setExamDifficulty] = useState<NVODifficulty>('standard');
  const [_examFormat, _setExamFormat] = useState<NVOFormat>('full');
  const [_examDuration, _setExamDuration] = useState(FULL_EXAM_DURATION_SECONDS);
  const [xpAwardResult, setXpAwardResult] = useState<NVOAwardXpResponse | null>(null);
  const [historyPage, setHistoryPage] = useState(0);
  const examSnapshotRef = useRef<ExamSnapshot & {
    examStarted: boolean;
    examReady: boolean;
    submitted: boolean;
    isReviewMode: boolean;
  }>({
    examId: '',
    examQuestions: [],
    answers: {},
    answerImages: {},
    markedForReview: [],
    timeLeft: EXAM_DURATION_SECONDS,
    currentQuestion: 1,
    examStartTimestamp: null,
    examDifficulty: 'standard',
    examStarted: false,
    examReady: false,
    submitted: false,
    isReviewMode: false,
  });

  const { status: planStatus } = usePlan();
  const { refreshXp } = useXp();
  const { maybeShow: maybeShowUpgrade, dismiss: dismissUpgrade } = usePlanPrompt(setLimitError);

  useEffect(() => {
    try {
      const rawHistory = localStorage.getItem(historyKey);
      if (rawHistory) {
        const parsed = JSON.parse(rawHistory) as Partial<ExamHistoryEntry>[];
        if (Array.isArray(parsed)) {
          setHistory(
            trimHistory(
              parsed.map((entry) => {
                const normalized = normalizeHistoryEntry(entry);
                if (normalized.status === 'in_progress') {
                  return { ...normalized, status: 'unfinished' as const };
                }
                return normalized;
              }),
            ),
          );
        }
      }
    } catch {
      // Ignore invalid history storage payload.
    }

    // Restore an in-progress exam if one was interrupted (e.g. by page refresh).
    // Conditions: exam was started, has real questions loaded, and time hasn't run out.
    try {
      const rawState = localStorage.getItem(storageKey);
      if (rawState) {
        const saved = JSON.parse(rawState) as Partial<ExamState>;
        const hasQuestions =
          Array.isArray(saved.questions) &&
          saved.questions.length > 0 &&
          saved.questions[0]?.text !== 'Зареждане на задача...';

        if (saved.examStarted && hasQuestions && typeof saved.timeLeft === 'number' && saved.timeLeft <= 0) {
          persistUnfinishedEntry({
            examId: saved.examId ?? '',
            examQuestions: saved.questions as ExamQuestion[],
            answers: (saved.answers ?? {}) as Record<number, AnswerValue>,
            answerImages: (saved.answerImages ?? {}) as Record<number, string>,
            markedForReview: Array.isArray(saved.markedForReview) ? saved.markedForReview : [],
            timeLeft: 0,
            currentQuestion: typeof saved.currentQuestion === 'number' ? saved.currentQuestion : 1,
            examStartTimestamp: null,
            examDifficulty: 'standard',
          });
          localStorage.removeItem(storageKey);
          const refreshedHistory = localStorage.getItem(historyKey);
          if (refreshedHistory) {
            const parsed = JSON.parse(refreshedHistory) as Partial<ExamHistoryEntry>[];
            if (Array.isArray(parsed)) {
              setHistory(trimHistory(parsed.map(normalizeHistoryEntry)));
            }
          }
        } else if (
          saved.examStarted &&
          hasQuestions &&
          typeof saved.timeLeft === 'number' &&
          saved.timeLeft > 0
        ) {
          setExamId(saved.examId ?? '');
          setExamQuestions(saved.questions as ExamQuestion[]);
          setAnswers((saved.answers ?? {}) as Record<number, AnswerValue>);
          setAnswerImages((saved.answerImages ?? {}) as Record<number, string>);
          setMarkedForReview(Array.isArray(saved.markedForReview) ? saved.markedForReview : []);
          setCurrentQuestion(typeof saved.currentQuestion === 'number' ? saved.currentQuestion : 1);
          setTimeLeft(saved.timeLeft);
          setExamStartTimestamp(new Date(Date.now() - (EXAM_DURATION_SECONDS - saved.timeLeft) * 1000).toISOString());
          setSubmitted(false);
          setExamStarted(true);
          setExamReady(true);
          setIsReviewMode(false);
          return; // skip the forced-dashboard reset below
        }
      }
    } catch {
      // Ignore corrupt saved state.
    }

    // No active exam to restore — open the NVO dashboard.
    setExamStarted(false);
    setExamReady(false);
    setSubmitted(false);
  }, [historyKey, storageKey]);

  useEffect(() => {
    const payload: ExamState = {
      examId,
      examStarted,
      questions: examQuestions,
      currentQuestion,
      answers,
      answerImages: {},
      markedForReview,
      timeLeft,
    };
    try {
      localStorage.setItem(storageKey, JSON.stringify(payload));
    } catch {
      // Ignore quota errors — images are not persisted anyway
    }
  }, [examId, examStarted, examQuestions, currentQuestion, answers, markedForReview, timeLeft, storageKey]);

  useEffect(() => {
    try {
      localStorage.setItem(historyKey, JSON.stringify(history));
    } catch {
      // Ignore quota errors
    }
  }, [history, historyKey]);

  useEffect(() => {
    examSnapshotRef.current = {
      examId,
      examQuestions,
      answers,
      answerImages,
      markedForReview,
      timeLeft,
      currentQuestion,
      examStartTimestamp,
      examDifficulty,
      examStarted,
      examReady,
      submitted,
      isReviewMode,
    };
  }, [
    examId,
    examQuestions,
    answers,
    answerImages,
    markedForReview,
    timeLeft,
    currentQuestion,
    examStartTimestamp,
    examDifficulty,
    examStarted,
    examReady,
    submitted,
    isReviewMode,
  ]);

  useEffect(() => {
    return () => {
      const snapshot = examSnapshotRef.current;
      if (!snapshot.examStarted || !snapshot.examReady || snapshot.submitted || snapshot.isReviewMode || !snapshot.examId) {
        return;
      }
      persistUnfinishedEntry(snapshot);
    };
  }, []);

  useEffect(() => {
    if (!examStarted || !examReady || submitted || isReviewMode || !examId || examQuestions.length === 0) return;

    setHistory((prev) => {
      const existing = prev.find((item) => item.examId === examId);
      const entry = buildHistoryEntryFromSnapshot(
        {
          examId,
          examQuestions,
          answers,
          answerImages,
          markedForReview,
          timeLeft,
          currentQuestion,
          examStartTimestamp,
          examDifficulty,
          existingId: existing?.id,
          createdAt: existing?.createdAt,
        },
        'in_progress',
      );
      return upsertHistoryEntry(prev, entry);
    });
  }, [
    examStarted,
    examReady,
    submitted,
    isReviewMode,
    examId,
    examQuestions,
    answers,
    answerImages,
    markedForReview,
    timeLeft,
    currentQuestion,
    examStartTimestamp,
    examDifficulty,
  ]);

  useEffect(() => {
    if (!generationJobId) return;

    let cancelled = false;
    const tick = async () => {
      try {
        const job = await getNVOGenerationJob(generationJobId);
        if (cancelled) return;

        setGenerationProgress(job.progress);
        setGenerationMessage(job.message);

        if (job.status === 'completed' && job.exam_id) {
          const exam = await getGeneratedNVOExam(job.exam_id);
          if (cancelled) return;

          const questions = convertExamQuestions(exam.questions);
          const readyEntry: ExamHistoryEntry = {
            id: Date.now(),
            examId: exam.exam_id,
            status: 'ready',
            createdAt: new Date().toISOString(),
            durationSec: 0,
            score: 0,
            maxScore: 0,
            scorePercent: 0,
            module1Percent: 0,
            module2Percent: 0,
            questions,
            answers: {},
            answerImages: {},
            markedForReview: [],
          };

          setHistory((prev) => upsertHistoryEntry(prev, readyEntry));
          setGenerationJobId(null);
          setGenerationProgress(100);
          setGenerationMessage('Тестът е готов за старт');
          setLoadingExam(false);
          return;
        }

        if (job.status === 'failed') {
          setGenerationMessage(job.message || 'Неуспешно генериране на НВО тест');
          setGenerationJobId(null);
          setLoadingExam(false);
          return;
        }
      } catch {
        if (!cancelled) {
          setGenerationMessage('Грешка при проследяване на генерирането');
          setGenerationJobId(null);
          setLoadingExam(false);
        }
      }
    };

    tick();
    const interval = window.setInterval(tick, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [generationJobId]);

  // Smoothly animate the progress bar toward the real reported value
  useEffect(() => {
    if (generationProgress <= 0) { setSmoothProgress(0); return; }
    const id = window.setInterval(() => {
      setSmoothProgress((prev) => {
        const diff = generationProgress - prev;
        if (diff <= 0.5) { window.clearInterval(id); return generationProgress; }
        return prev + Math.max(0.5, diff * 0.12);
      });
    }, 60);
    return () => window.clearInterval(id);
  }, [generationProgress]);

  const isExamLocked = examStarted && examReady && !submitted && !isReviewMode;

  useEffect(() => {
    if (!isExamLocked) return;

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isExamLocked]);

  const [showTabWarning, setShowTabWarning] = useState(false);

  useEffect(() => {
    if (!isExamLocked) return;

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        setShowTabWarning(true);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [isExamLocked]);

  useEffect(() => {
    if (!isExamLocked || !submitted) return;
    setShowTabWarning(false);
  }, [isExamLocked, submitted]);

  useEffect(() => {
    if (!examStarted || !examReady || submitted || isReviewMode) return;

    const timer = setInterval(() => {
      setTimeLeft((prev) => Math.max(prev - 1, 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [examStarted, examReady, submitted, isReviewMode]);

  useEffect(() => {
    const onAnswerImageReceived = (event: Event) => {
      if (!examStarted || !examReady || submitted || isReviewMode) return;

      const customEvent = event as CustomEvent<SubmitAnswerImageEventPayload>;
      const detail = customEvent.detail;
      if (!detail || !Number.isFinite(detail.problemId) || typeof detail.image !== 'string') return;

      const exists = examQuestions.some((question) => question.id === detail.problemId);
      if (!exists) return;

      setAnswerImages((current) => ({
        ...current,
        [detail.problemId]: detail.image,
      }));
    };

    window.addEventListener(TEST_ANSWER_IMAGE_EVENT, onAnswerImageReceived);
    return () => {
      window.removeEventListener(TEST_ANSWER_IMAGE_EVENT, onAnswerImageReceived);
    };
  }, [examQuestions, examReady, examStarted, isReviewMode, submitted]);

  const current = examQuestions.find((q) => q.id === currentQuestion) || examQuestions[0];
  const currentAnswer = current ? answers[current.id] : undefined;
  const waitingForQuestions = examStarted && (!examReady || !current);

  const answeredCount = useMemo(
    () => examQuestions.filter((q) => isQuestionAnswered(q, answers[q.id]) || (q.type === 'open' && Boolean(answerImages[q.id]))).length,
    [answers, answerImages, examQuestions]
  );

  const unansweredCount = examQuestions.length - answeredCount;

  const completedHistory = history.filter((entry) => entry.status === 'completed');
  const readyHistory = history.filter((entry) => entry.status === 'ready');
  const attemptHistory: PreviousResult[] = history
    .filter((entry) => entry.status === 'completed' || entry.status === 'unfinished')
    .sort((a, b) => b.id - a.id)
    .slice(0, MAX_HISTORY_ATTEMPTS)
    .map((h) => ({
      id: h.id,
      date: formatBgDateTime(h.completedAt ?? h.createdAt),
      status: h.status as 'completed' | 'unfinished',
      score: h.scorePercent,
      maxScore: 100,
      durationMin: Math.round(h.durationSec / 60),
      module1Percent: h.module1Percent,
      module2Percent: h.module2Percent,
      answeredCount: countAnsweredQuestions(h.questions, h.answers, h.answerImages),
      questionCount: h.questions.length,
    }));

  const previousResults = attemptHistory;

  const latestReadyExam = readyHistory.length > 0 ? readyHistory[0] : null;

  const weakPoints = useMemo(() => {
    const byTopic = new Map<string, { answered: number; total: number }>();

    completedHistory.forEach((entry) => {
      entry.questions.forEach((q) => {
        const topic = q.topic || 'общо';
        const currentTopic = byTopic.get(topic) ?? { answered: 0, total: 0 };
        currentTopic.total += 1;
        if (isQuestionAnswered(q, entry.answers[q.id])) currentTopic.answered += 1;
        byTopic.set(topic, currentTopic);
      });
    });

    return Array.from(byTopic.entries())
      .map(([topic, stats]) => {
        const completion = stats.total > 0 ? Math.round((stats.answered / stats.total) * 100) : 0;
        return {
          topic,
          accuracy: completion,
          note: completion < 60
            ? 'Ниска успеваемост по темата. Нужна е допълнителна практика.'
            : 'Има напредък, но още има място за подобрение.',
        };
      })
      .sort((a, b) => a.accuracy - b.accuracy)
      .slice(0, 3);
  }, [completedHistory]);

  const openTestProblems = useMemo(
    () => examQuestions
      .filter((q) => q.type === 'open')
      .map((q) => ({ id: q.id, label: `Problem ${q.id}`, type: 'open' as const })),
    [examQuestions]
  );

  useEffect(() => {
    if (examStarted && examReady && !submitted && !isReviewMode && openTestProblems.length > 0) {
      publishActiveTestData(openTestProblems);
      return;
    }
    clearActiveTestData();
  }, [examReady, examStarted, isReviewMode, openTestProblems, submitted]);

  const scoreCurrentExam = () => {
    let score = 0;
    let maxScore = 0;

    examQuestions.forEach((q) => {
      if (q.type !== 'mcq') return;
      if (typeof q.correctAnswer !== 'string') return;
      maxScore += 1;
      const selected = answers[q.id];
      if (typeof selected === 'string' && normalizeOptionKey(selected) === normalizeOptionKey(q.correctAnswer)) {
        score += 1;
      }
    });

    return { score, maxScore };
  };

  const saveHistoryEntry = () => {
    if (!examId) return;
    setHistory((prev) => {
      const existing = prev.find((item) => item.examId === examId);
      const entry = buildHistoryEntryFromSnapshot(
        {
          examId,
          examQuestions,
          answers,
          answerImages,
          markedForReview,
          timeLeft,
          currentQuestion,
          examStartTimestamp,
          examDifficulty,
          existingId: existing?.id,
          createdAt: existing?.createdAt,
        },
        'completed',
      );
      return upsertHistoryEntry(prev, entry);
    });
    localStorage.removeItem(storageKey);
  };

  const saveUnfinishedEntry = () => {
    if (!examId || examQuestions.length === 0) return;
    setHistory((prev) => {
      const existing = prev.find((item) => item.examId === examId);
      const entry = buildHistoryEntryFromSnapshot(
        {
          examId,
          examQuestions,
          answers,
          answerImages,
          markedForReview,
          timeLeft,
          currentQuestion,
          examStartTimestamp,
          examDifficulty,
          existingId: existing?.id,
          createdAt: existing?.createdAt,
        },
        'unfinished',
      );
      return upsertHistoryEntry(prev, entry);
    });
    localStorage.removeItem(storageKey);
  };

  const startNewExam = async (difficulty?: NVODifficulty) => {
    const selectedDiff = difficulty || 'standard';
    setExamDifficulty(selectedDiff);
    setLoadingExam(true);
    setGenerationProgress(0);
    setGenerationMessage('Подготовка за генериране на НВО тест');
    try {
      const job = await createNVOGenerationJob(selectedDiff);
      setGenerationProgress(job.progress);
      setGenerationMessage(job.message);

      if (job.status === 'completed' && job.exam_id) {
        const exam = await getGeneratedNVOExam(job.exam_id);
        const questions = convertExamQuestions(exam.questions);
        const readyEntry: ExamHistoryEntry = {
          id: Date.now(),
          examId: exam.exam_id,
          status: 'ready',
          createdAt: new Date().toISOString(),
          durationSec: 0,
          score: 0,
          maxScore: 0,
          scorePercent: 0,
          module1Percent: 0,
          module2Percent: 0,
          difficulty: selectedDiff,
          questions,
          answers: {},
          answerImages: {},
          markedForReview: [],
        };
        setHistory((prev) => upsertHistoryEntry(prev, readyEntry));
        setGenerationProgress(100);
        setGenerationMessage('Тестът е готов за старт');
        setLoadingExam(false);
      } else {
        setGenerationJobId(job.job_id);
      }
    } catch (error) {
      console.error('Failed to generate NVO exam:', error);
      const detail = getLimitErrorDetail(error);
      if (detail) {
        maybeShowUpgrade({
          feature: detail.feature,
          message: detail.message,
          daysSinceSignup: planStatus.days_since_signup,
          isPremium: planStatus.is_premium,
        });
      } else {
        alert('Не успяхме да генерирахме ново НВО. Моля, опитайте отново.');
      }
      setLoadingExam(false);
    }
  };

  const startStoredExam = (entry: ExamHistoryEntry) => {
    trackEvent('nvo_started', {
      exam_id: entry.examId,
      source: entry.status,
      question_count: entry.questions.length,
    });
    setExamId(entry.examId);
    setExamQuestions(entry.questions.length > 0 ? entry.questions : createQuestionPlaceholders());
    setAnswers(entry.answers);
    setAnswerImages(entry.answerImages ?? {});
    setMarkedForReview(entry.markedForReview);
    setCurrentQuestion(entry.currentQuestion ?? 1);
    setTimeLeft(entry.timeLeft ?? EXAM_DURATION_SECONDS);
    setExamStartTimestamp(
      entry.timeLeft != null && entry.timeLeft < EXAM_DURATION_SECONDS
        ? new Date(Date.now() - (EXAM_DURATION_SECONDS - entry.timeLeft) * 1000).toISOString()
        : new Date().toISOString(),
    );
    setSubmitted(false);
    setExamStarted(true);
    setExamReady(entry.questions.length > 0);
    setExamDifficulty(entry.difficulty || 'standard');
    setIsReviewMode(false);
    setShowUnansweredWarning(false);
  };

  const revisitExam = (entry: ExamHistoryEntry) => {
    setExamId(entry.examId);
    setExamQuestions(entry.questions);
    setAnswers(entry.answers);
    setAnswerImages(entry.answerImages ?? {});
    setMarkedForReview(entry.markedForReview);
    setCurrentQuestion(entry.currentQuestion ?? 1);
    setTimeLeft(entry.timeLeft ?? EXAM_DURATION_SECONDS);
    setExamStartTimestamp(null);
    setSubmitted(false);
    setExamStarted(true);
    setExamReady(true);
    setExamDifficulty(entry.difficulty || 'standard');
    setIsReviewMode(true);
    setShowUnansweredWarning(false);
  };

  const saveMCQ = (questionId: number, optionKey: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: optionKey }));
  };

  const saveOpenAnswer = (questionId: number, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const saveOpenPart = (questionId: number, partKey: string, value: string) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: {
        ...(typeof prev[questionId] === 'object' ? (prev[questionId] as OpenPartsAnswer) : {}),
        [partKey]: value,
      },
    }));
  };

  const toggleReview = (questionId: number) => {
    setMarkedForReview((prev) =>
      prev.includes(questionId) ? prev.filter((id) => id !== questionId) : [...prev, questionId]
    );
  };

  const submitExamToBackend = async () => {
    if (!examId) return;

    const openAnswerImages = examQuestions
      .filter((question) => question.type === 'open')
      .map((question) => ({
        problemId: question.id,
        image: answerImages[question.id] || '',
      }));

    await submitNVOExam({
      exam_id: examId,
      answers,
      open_answer_images: openAnswerImages,
      questions: examQuestions.map((question) => ({
        number: question.id,
        question: question.text,
        topic: question.topic ?? 'NVO',
        difficulty: 'medium',
        diagram: Boolean(question.hasDiagram),
        diagram_type: question.diagramType,
        diagram_config: question.diagramConfig,
        open_parts: question.type === 'open' ? question.parts : undefined,
        options: question.type === 'mcq' ? question.options.map((option) => `${option.key}) ${option.text}`) : null,
        correct_answer: question.correctAnswer ?? null,
      })),
    });
  };

  const completeExamSubmission = async () => {
    if (isReviewMode) {
      setSubmitted(true);
      return;
    }

    setIsSubmittingExam(true);
    try {
      await submitExamToBackend();
      trackEvent('nvo_completed', {
        exam_id: examId,
        question_count: examQuestions.length,
      });
      saveHistoryEntry();
      // Calculate exam results for XP award
      const { score, maxScore } = scoreCurrentExam();
      const percentageCorrect = maxScore > 0 ? Math.round((score / maxScore) * 100) : 0;
      const minutesTaken = Math.round((EXAM_DURATION_SECONDS - timeLeft) / 60);
      
      // Award NVO exam XP with performance-based calculation
      awardNvoXpDetailed({
        percentage_correct: percentageCorrect,
        difficulty: examDifficulty,
        minutes_taken: minutesTaken,
        exam_id: examId,
      }).then((result) => {
        setXpAwardResult(result);
        refreshXp();
      }).catch(() => {});
      
      setSubmitted(true);
    } catch {
      alert('Неуспешно предаване на теста. Опитайте отново.');
    } finally {
      setIsSubmittingExam(false);
    }
  };

  const trySubmit = async () => {
    if (isReviewMode) {
      return;
    }
    if (unansweredCount > 0) {
      setShowUnansweredWarning(true);
      return;
    }
    await completeExamSubmission();
  };

  const forceSubmit = async () => {
    setShowUnansweredWarning(false);
    await completeExamSubmission();
  };

  const restartExam = () => {
    if (examStarted && examReady && !submitted && !isReviewMode && examId) {
      saveUnfinishedEntry();
    }
    setExamId('');
    setAnswers({});
    setAnswerImages({});
    setPartImages({});
    setMarkedForReview([]);
    setCurrentQuestion(1);
    setTimeLeft(EXAM_DURATION_SECONDS);
    setExamReady(false);
    setExamQuestions([]);
    setExamStartTimestamp(null);
    setIsReviewMode(false);
    setSubmitted(false);
    setShowUnansweredWarning(false);
    localStorage.removeItem(storageKey);
  };

  const exitToDashboard = () => {
    if (isReviewMode) {
      setExamStarted(false);
      setIsReviewMode(false);
      return;
    }
    if (examStarted && examReady && !submitted && examId) {
      saveUnfinishedEntry();
    }
    setExamId('');
    setAnswers({});
    setAnswerImages({});
    setMarkedForReview([]);
    setCurrentQuestion(1);
    setTimeLeft(EXAM_DURATION_SECONDS);
    setExamReady(false);
    setExamQuestions([]);
    setExamStartTimestamp(null);
    setIsReviewMode(false);
    setSubmitted(false);
    setShowUnansweredWarning(false);
    localStorage.removeItem(storageKey);
    setExamStarted(false);
  };

  const avgScore = previousResults.filter((item) => item.status === 'completed').length > 0
    ? Math.round(
        previousResults
          .filter((item) => item.status === 'completed')
          .reduce((sum, item) => sum + item.score, 0) /
          previousResults.filter((item) => item.status === 'completed').length,
      )
    : 0;
  const bestScore = previousResults.filter((item) => item.status === 'completed').length > 0
    ? Math.max(...previousResults.filter((item) => item.status === 'completed').map((item) => item.score))
    : 0;
  const lastCompleted = previousResults.find((item) => item.status === 'completed');
  const lastScore = lastCompleted?.score ?? 0;

  const [showDemoMetrics, setShowDemoMetrics] = useState(false);

  const DEMO_METRICS = {
    totalSessions: 14,
    bestScore: 87,
    avgScore: 71,
    lastScore: 82,
    history: [
      { date: '18.04.2026', score: 82, maxScore: 100, mod1: 85, mod2: 75, duration: 23 },
      { date: '15.04.2026', score: 74, maxScore: 100, mod1: 80, mod2: 60, duration: 27 },
      { date: '12.04.2026', score: 65, maxScore: 100, mod1: 70, mod2: 55, duration: 31 },
      { date: '09.04.2026', score: 78, maxScore: 100, mod1: 85, mod2: 62, duration: 25 },
      { date: '05.04.2026', score: 87, maxScore: 100, mod1: 90, mod2: 80, duration: 22 },
    ],
    weakSpots: [
      { topic: 'Тригонометрия', accuracy: 42, note: 'Греши при синус и косинус на специални ъгли.' },
      { topic: 'Квадратни уравнения', accuracy: 55, note: 'Дискриминантата се пресмята погрешно при отрицателни коефициенти.' },
      { topic: 'Функции и графики', accuracy: 61, note: 'Трудности с намиране на максимум/минимум.' },
    ],
  };

  if (!examStarted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-orange-50 dark:from-transparent dark:to-transparent">
        <AppNavbar backTo="/dashboard" />

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <section className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-lg sm:text-2xl font-black text-gray-900 dark:text-slate-100">НВО Математика – Тренировка</h1>
            <div className="flex items-center gap-3">
              {isDeveloperMode && (
                <button
                  onClick={() => setShowDemoMetrics((v) => !v)}
                  className={`px-5 py-2.5 rounded-xl font-semibold shadow-sm ${showDemoMetrics ? 'bg-indigo-700 text-white' : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'}`}
                >
                  📊 Демо метрики
                </button>
              )}
              {isDeveloperMode && (
                <button
                  onClick={() => navigate('/playground')}
                  className="px-5 py-2.5 rounded-xl bg-violet-600 text-white font-semibold hover:bg-violet-700 shadow-sm"
                >
                  🧪 Playground
                </button>
              )}
              <button
                onClick={() => setShowDifficultySelector(true)}
                disabled={loadingExam}
                className="px-5 py-2.5 rounded-xl bg-orange-600 text-white font-semibold hover:bg-orange-700 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loadingExam ? 'Зарежда...' : 'Генерирай ново НВО'}
              </button>
            </div>
          </section>

          {(loadingExam || generationJobId || generationMessage) && (
            <section className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm mb-8 dark:border-slate-700/60 dark:bg-slate-800/60">
              <div className="flex items-center justify-between gap-4 mb-3">
                <div>
                  <h2 className="text-lg font-bold text-gray-900 dark:text-slate-100">Генериране на ново НВО</h2>
                  <p className="text-sm text-gray-600 dark:text-slate-400">{generationMessage || 'Подготовка...'}</p>
                </div>
                <span className="text-sm font-semibold text-blue-700 dark:text-blue-300">{Math.round(smoothProgress)}%</span>
              </div>
              <div className="w-full h-3 rounded-full bg-slate-100 dark:bg-slate-700/60 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-orange-500"
                  style={{ width: `${smoothProgress}%`, transition: 'width 60ms linear' }}
                />
              </div>
              {!generationJobId && generationProgress === 100 && latestReadyExam && (
                <div className="mt-3 flex items-center justify-between gap-3">
                  <p className="text-sm text-emerald-700 dark:text-emerald-300">Тестът е готов. Може да го стартирате веднага.</p>
                  <button
                    onClick={() => startStoredExam(latestReadyExam)}
                    className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-semibold hover:bg-emerald-700"
                  >
                    Старт на теста
                  </button>
                </div>
              )}
            </section>
          )}

          <div className="mb-6 rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4 flex flex-wrap items-center justify-between gap-3 dark:border-blue-800/40 dark:bg-blue-950/30">
            <div>
              <p className="text-sm font-bold text-blue-900 dark:text-blue-200">📱 Свържи телефона си</p>
              <p className="text-xs text-blue-700 dark:text-blue-300/80 mt-0.5">За задачи с отворен отговор (21–23) можеш да качиш снимка от телефона си в реално време.</p>
            </div>
            <a
              href="/controller"
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
            >
              Свържи телефон →
            </a>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-2xl p-5 border border-gray-200 shadow-sm dark:border-slate-700/60 dark:bg-slate-800/60">
              <p className="text-sm text-gray-500 dark:text-slate-400">Общо тренировки</p>
              <p className="text-3xl font-black text-gray-900 dark:text-slate-100">{showDemoMetrics ? DEMO_METRICS.totalSessions : previousResults.length}</p>
            </div>
            <div className="bg-white rounded-2xl p-5 border border-gray-200 shadow-sm dark:border-slate-700/60 dark:bg-slate-800/60">
              <p className="text-sm text-gray-500 dark:text-slate-400">Най-добър резултат</p>
              <p className="text-3xl font-black text-emerald-600 dark:text-emerald-400">{showDemoMetrics ? DEMO_METRICS.bestScore : bestScore}%</p>
            </div>
            <div className="bg-white rounded-2xl p-5 border border-gray-200 shadow-sm dark:border-slate-700/60 dark:bg-slate-800/60">
              <p className="text-sm text-gray-500 dark:text-slate-400">Среден резултат</p>
              <p className="text-3xl font-black text-blue-600 dark:text-blue-400">{showDemoMetrics ? DEMO_METRICS.avgScore : avgScore}%</p>
            </div>
            <div className="bg-white rounded-2xl p-5 border border-gray-200 shadow-sm dark:border-slate-700/60 dark:bg-slate-800/60">
              <p className="text-sm text-gray-500 dark:text-slate-400">Последен резултат</p>
              <p className="text-3xl font-black text-orange-600 dark:text-orange-400">{showDemoMetrics ? DEMO_METRICS.lastScore : lastScore}%</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <section className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm dark:border-slate-700/60 dark:bg-slate-800/60">
              <h2 className="text-xl font-bold text-gray-900 dark:text-slate-100 mb-4">Готови за старт тестове</h2>
              {readyHistory.length > 0 ? (
                <div className="space-y-3 mb-6">
                  {readyHistory.map((entry) => (
                    <div key={entry.id} className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-700/40 dark:bg-emerald-900/20">
                      <div className="flex items-center justify-between gap-3 mb-2">
                        <p className="font-semibold text-gray-900 dark:text-slate-100">Готов тест • {formatBgDateTime(entry.createdAt)}</p>
                        <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300">Готов за старт</span>
                      </div>
                      <button
                        onClick={() => startStoredExam(entry)}
                        className="text-sm px-3 py-1.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700"
                      >
                        Старт на теста
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 dark:text-slate-400 mb-6">Няма готови, но нестартирани тестове.</p>
              )}

              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold text-gray-900 dark:text-slate-100">Последни резултати</h2>
                {!showDemoMetrics && previousResults.length > ITEMS_PER_PAGE && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setHistoryPage((p) => Math.max(0, p - 1))}
                      disabled={historyPage === 0}
                      className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700/50 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                      </svg>
                    </button>
                    <span className="text-sm text-gray-600 dark:text-slate-400">
                      {historyPage + 1} / {Math.ceil(previousResults.length / ITEMS_PER_PAGE)}
                    </span>
                    <button
                      onClick={() => setHistoryPage((p) => Math.min(Math.ceil(previousResults.length / ITEMS_PER_PAGE) - 1, p + 1))}
                      disabled={historyPage >= Math.ceil(previousResults.length / ITEMS_PER_PAGE) - 1}
                      className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-700/50 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                  </div>
                )}
              </div>
              {(showDemoMetrics ? true : previousResults.length > 0) ? (
                <div className="space-y-3">
                  {(showDemoMetrics ? DEMO_METRICS.history : previousResults.slice(historyPage * ITEMS_PER_PAGE, (historyPage + 1) * ITEMS_PER_PAGE)).map((result: any, i: number) => {
                    if (showDemoMetrics) {
                      return (
                        <div key={i} className="rounded-xl border border-gray-200 p-4 dark:border-slate-700/60 dark:bg-slate-900/40">
                          <div className="flex items-center justify-between mb-2 gap-2">
                            <p className="font-semibold text-gray-900 dark:text-slate-100">{result.date}</p>
                            <span className="text-sm font-bold text-blue-600 dark:text-blue-400">{result.score}/{result.maxScore}</span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-xs text-gray-600 dark:text-slate-400">
                            <span>Модул 1: {result.mod1}%</span>
                            <span>Модул 2: {result.mod2}%</span>
                            <span>Време: {result.duration} мин</span>
                          </div>
                        </div>
                      );
                    }
                    const source = history.find((h) => h.id === result.id);
                    const isUnfinished = result.status === 'unfinished';
                    return (
                      <div
                        key={result.id}
                        className={`rounded-xl border p-4 dark:bg-slate-900/40 ${
                          isUnfinished
                            ? 'border-amber-200 bg-amber-50/50 dark:border-amber-700/50 dark:bg-amber-950/20'
                            : 'border-gray-200 dark:border-slate-700/60'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2 gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <p className="font-semibold text-gray-900 dark:text-slate-100 truncate">{result.date}</p>
                            {isUnfinished && (
                              <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800 dark:bg-amber-900/50 dark:text-amber-300">
                                Недовършен
                              </span>
                            )}
                          </div>
                          {isUnfinished ? (
                            <span className="text-sm font-bold text-amber-700 dark:text-amber-300 shrink-0">
                              {result.answeredCount}/{result.questionCount}
                            </span>
                          ) : (
                            <span className="text-sm font-bold text-blue-600 dark:text-blue-400 shrink-0">
                              {result.score}/{result.maxScore}
                            </span>
                          )}
                        </div>
                        <div className="grid grid-cols-3 gap-2 text-xs text-gray-600 dark:text-slate-400 mb-3">
                          <span>Модул 1: {result.module1Percent}%</span>
                          <span>Модул 2: {result.module2Percent}%</span>
                          <span>Време: {result.durationMin} мин</span>
                        </div>
                        {source && (
                          <div className="flex flex-wrap gap-2">
                            {isUnfinished && (
                              <button
                                onClick={() => startStoredExam(source)}
                                className="text-sm px-3 py-1.5 rounded-lg bg-amber-600 text-white hover:bg-amber-700"
                              >
                                Продължи
                              </button>
                            )}
                            <button
                              onClick={() => revisitExam(source)}
                              className="text-sm px-3 py-1.5 rounded-lg border border-blue-200 text-blue-700 hover:bg-blue-50 dark:border-blue-700/50 dark:text-blue-300 dark:hover:bg-blue-900/30"
                            >
                              Преглед на теста
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-gray-500 dark:text-slate-400">Все още няма завършени или недовършени тренировки.</p>
              )}
            </section>

            <section className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm dark:border-slate-700/60 dark:bg-slate-800/60">
              <h2 className="text-xl font-bold text-gray-900 dark:text-slate-100 mb-4">Слаби места</h2>
              {(showDemoMetrics ? DEMO_METRICS.weakSpots : weakPoints).length > 0 ? (
                <div className="space-y-3">
                  {(showDemoMetrics ? DEMO_METRICS.weakSpots : weakPoints).map((point) => (
                    <div key={point.topic} className="rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-700/40 dark:bg-amber-900/20">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-semibold text-gray-900 dark:text-slate-100 capitalize">{point.topic}</p>
                        <span className="shrink-0 text-amber-700 dark:text-amber-300 font-bold text-sm">{point.accuracy}%</span>
                      </div>
                      <p className="text-sm text-gray-600 dark:text-slate-400 mt-1">{point.note}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500 dark:text-slate-400">Няма достатъчно данни за анализ на слаби места.</p>
              )}
              <button
                onClick={() => setShowDifficultySelector(true)}
                disabled={loadingExam || !!generationJobId}
                className="mt-5 w-full px-4 py-3 rounded-xl bg-orange-600 text-white font-semibold hover:bg-orange-700"
              >
                {loadingExam || generationJobId ? 'Генериране...' : 'Генерирай ново НВО'}
              </button>
            </section>
          </div>
        </main>

        {/* Difficulty Selector Modal */}
        {showDifficultySelector && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm">
            <div className="w-full max-w-2xl rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-slate-700 dark:bg-slate-900">
              <NVODifficultySelector
                selected={selectedDifficulty}
                onSelect={setSelectedDifficulty}
                disabled={loadingExam}
              />
              <div className="mt-6 flex justify-end gap-3">
                <button
                  onClick={() => setShowDifficultySelector(false)}
                  disabled={loadingExam}
                  className="px-4 py-2 rounded-xl border border-gray-200 text-gray-700 font-semibold hover:bg-gray-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  Отказ
                </button>
                <button
                  onClick={() => {
                    setShowDifficultySelector(false);
                    startNewExam(selectedDifficulty);
                  }}
                  disabled={loadingExam}
                  className="px-4 py-2 rounded-xl bg-orange-600 text-white font-semibold hover:bg-orange-700 disabled:opacity-50"
                >
                  {loadingExam ? 'Генериране...' : 'Продължи'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-transparent">
      <AppNavbar backTo="/dashboard" />
      {limitError && (
          <UpgradePrompt
            feature={limitError.feature}
            message={limitError.message}
            onClose={dismissUpgrade}
          />
        )}

      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <section className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-sm sm:text-lg font-bold text-gray-900 dark:text-slate-100 truncate">НВО Математика – Тренировка</h1>
          <div className="flex items-center gap-2 sm:gap-3">
            <div className="px-3 py-2 rounded-lg bg-slate-100 text-slate-700 text-sm font-semibold">
              ⏱ {formatTime(timeLeft)}
            </div>
            <div className={`px-3 py-2 rounded-lg text-sm font-semibold ${DIFFICULTY_COLORS[examDifficulty] || 'text-blue-600 bg-blue-100'}`}>
              ⭐ {DIFFICULTY_LABELS[examDifficulty] || '1.0x XP'}
            </div>
            <div className="hidden sm:block px-3 py-2 rounded-lg bg-blue-50 text-blue-700 text-sm font-semibold">
              {answeredCount}/{examQuestions.length} отговорени
            </div>
            <button
              onClick={exitToDashboard}
              disabled={isSubmittingExam}
              className="px-3 py-2 rounded-lg border border-gray-300 text-gray-700 text-sm font-semibold hover:bg-gray-50 disabled:opacity-60 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              Към таблото
            </button>
            <button
              onClick={trySubmit}
              disabled={isReviewMode || !examReady || isSubmittingExam}
              className="px-4 py-2 rounded-lg bg-rose-600 text-white text-sm font-semibold hover:bg-rose-700 disabled:opacity-60"
            >
              {isReviewMode ? 'Режим преглед' : isSubmittingExam ? 'Предаване...' : 'Предай теста'}
            </button>
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)] gap-6">
        <aside className="bg-white border border-gray-200 rounded-2xl p-4 h-fit lg:sticky lg:top-24">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-900">Навигация</h2>
            <span className="text-xs text-gray-500">{answeredCount}/{examQuestions.length}</span>
          </div>

          <div className="grid grid-cols-6 sm:grid-cols-8 lg:grid-cols-5 gap-2">
            {examQuestions.map((q) => {
              const answered = isQuestionAnswered(q, answers[q.id]) || (q.type === 'open' && Boolean(answerImages[q.id]));
              const isCurrent = q.id === currentQuestion;
              const marked = markedForReview.includes(q.id);

              const baseClass = isCurrent
                ? 'bg-blue-600 text-white border-blue-700 shadow-lg'
                : answered
                ? 'bg-emerald-500 text-white border-emerald-600 shadow-md'
                : 'bg-gray-200 text-gray-900 border-gray-300 shadow';

              return (
                <button
                  key={q.id}
                  onClick={() => setCurrentQuestion(q.id)}
                  className={`relative h-10 rounded-lg border text-sm font-bold transition-all hover:scale-[1.05] ${baseClass}`}
                  title={`Задача ${q.id}`}
                >
                  {q.id}
                  {marked && <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-amber-400 border-2 border-white shadow-md" />}
                </button>
              );
            })}
          </div>

          <div className="mt-4 text-xs text-gray-500 space-y-1">
            <p><span className="inline-block w-2 h-2 rounded-full bg-gray-400 mr-1" /> Неотговорен</p>
            <p><span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1" /> Отговорен</p>
            <p><span className="inline-block w-2 h-2 rounded-full bg-blue-600 mr-1" /> Текущ</p>
            <p><span className="inline-block w-2 h-2 rounded-full bg-amber-400 mr-1" /> За преглед</p>
          </div>
        </aside>

        <main>
          {!submitted ? (
            <section className="bg-white border border-gray-200 rounded-2xl p-6 sm:p-8 shadow-sm">
              <div className="flex items-start justify-between gap-3 mb-5">
                <div>
                  <p className="text-xs uppercase tracking-widest text-gray-400 mb-1">
                    Модул {current.module} • Задача {current.id}
                  </p>
                  <h2 className="text-xl font-bold text-gray-900">Задача {current.id}</h2>
                </div>
                {!isReviewMode && (
                  <button
                    onClick={() => toggleReview(current.id)}
                    className={`px-3 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                      markedForReview.includes(current.id)
                        ? 'bg-amber-100 text-amber-800 border-amber-300'
                        : 'bg-white text-gray-700 border-gray-300 hover:border-amber-300'
                    }`}
                  >
                    {markedForReview.includes(current.id) ? 'Отбелязано за преглед' : 'Маркирай за преглед'}
                  </button>
                )}
              </div>

              {waitingForQuestions && (
                <div className="mb-5 inline-flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-700">
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Зареждане на теста. Таймерът ще стартира след пълното зареждане.
                </div>
              )}

              <div className="text-gray-800 leading-relaxed mb-5">{renderMathText(
                current.type === 'open' && current.parts && current.parts.length > 0
                  ? current.text.replace(/(^|\n)[АБВГ]\)[^\n]*/gu, '').trim()
                  : current.text
              )}</div>

              {current.hasDiagram && (
                current.diagramType
                  ? renderNvoDiagram(current.diagramType, current.diagramConfig ?? {})
                  : <DiagramRenderer problemText={current.text} enabled={!waitingForQuestions} />
              )}

              {current.type === 'mcq' ? (
                <div className="space-y-3">
                  {current.options.map((option) => {
                    const selected = answers[current.id] === option.key;
                    return (
                      <button
                        key={option.key}
                        onClick={() => saveMCQ(current.id, option.key)}
                        disabled={isReviewMode || waitingForQuestions}
                        className={`w-full text-left p-4 rounded-xl border transition-all ${
                          selected
                            ? 'border-blue-500 bg-blue-50 text-blue-900'
                            : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50/50'
                        } disabled:opacity-80`}
                      >
                        <span className="font-semibold mr-2">{option.key})</span>
                        {renderMathText(option.text)}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="space-y-5">
                  {current.parts && current.parts.length > 0 ? (
                    current.parts.map((partKey) => {
                      const partRegex = new RegExp(`(?:^|\\n)${partKey}\\)\\s*([^\\n]+)`, 'u');
                      const match = current.text.match(partRegex);
                      const partText = match ? match[1].trim() : null;
                      return (
                        <div key={partKey} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                          <p className="text-sm font-bold text-gray-800 mb-1">
                            {partKey})&nbsp;{partText ? renderMathText(partText) : <span className="font-normal text-gray-500">Отговор</span>}
                          </p>
                          <input
                            type="text"
                            value={
                              typeof answers[current.id] === 'object'
                                ? ((answers[current.id] as OpenPartsAnswer)[partKey] || '')
                                : ''
                            }
                            onChange={(e) => saveOpenPart(current.id, partKey, e.target.value)}
                            readOnly={isReviewMode || waitingForQuestions}
                            className="w-full rounded-lg border border-gray-300 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400 bg-white text-sm"
                            placeholder={`Въведи отговор за ${partKey})`}
                          />
                        </div>
                      );
                    })
                  ) : (
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-1">Отговор</label>
                      <textarea
                        value={typeof currentAnswer === 'string' ? currentAnswer : ''}
                        onChange={(e) => saveOpenAnswer(current.id, e.target.value)}
                        readOnly={isReviewMode || waitingForQuestions}
                        rows={4}
                        className="w-full rounded-xl border border-gray-300 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400"
                        placeholder="Въведи решението си"
                      />
                    </div>
                  )}
                </div>
              )}

              {current.type === 'open' && answerImages[current.id] && (
                <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                  <p className="mb-2 text-xs font-semibold text-emerald-700">📷 Снимка от телефона</p>
                  <img
                    src={answerImages[current.id]}
                    alt={`Отговор на задача ${current.id}`}
                    className="w-full max-h-72 rounded-lg object-contain border border-emerald-200"
                  />
                </div>
              )}

              {current.type === 'open' && current.parts && current.parts.length > 0 && !isReviewMode && (
                <div className="mt-4 space-y-3">
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">📎 Качи снимка на решение по подточки</p>
                  {current.parts.map((partKey) => {
                    const imgKey = `${current.id}-${partKey}`;
                    const img = partImages[imgKey];
                    return (
                      <div key={partKey} className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p className="text-xs font-bold text-slate-700 mb-2">Подточка {partKey})</p>
                        {img ? (
                          <div className="space-y-2">
                            <img src={img} alt={`Подточка ${partKey}`} className="w-full max-h-48 rounded-lg object-contain border border-slate-200" />
                            <button
                              type="button"
                              onClick={() => setPartImages((prev) => { const next = { ...prev }; delete next[imgKey]; return next; })}
                              className="text-xs text-red-600 hover:text-red-800"
                            >
                              Изтрий снимката
                            </button>
                          </div>
                        ) : (
                          <label className="flex items-center gap-2 cursor-pointer text-sm text-blue-700 font-semibold hover:text-blue-900">
                            <span className="px-3 py-1.5 rounded-lg border border-blue-300 bg-blue-50 hover:bg-blue-100 transition-colors">+ Прикачи снимка</span>
                            <input
                              type="file"
                              accept="image/*"
                              className="hidden"
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (!file) return;
                                const reader = new FileReader();
                                reader.onload = () => {
                                  if (typeof reader.result === 'string') {
                                    setPartImages((prev) => ({ ...prev, [imgKey]: reader.result as string }));
                                  }
                                };
                                reader.readAsDataURL(file);
                                e.currentTarget.value = '';
                              }}
                            />
                          </label>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              <div className="mt-8 flex items-center justify-between gap-3">
                <button
                  onClick={() => setCurrentQuestion((prev) => Math.max(1, prev - 1))}
                  disabled={current.id === 1}
                  className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 disabled:opacity-40"
                >
                  ← Предишна
                </button>

                <button
                  onClick={() => setCurrentQuestion((prev) => Math.min(examQuestions.length, prev + 1))}
                  disabled={current.id === examQuestions.length}
                  className="px-4 py-2 rounded-lg bg-blue-600 text-white disabled:opacity-40"
                >
                  Следваща →
                </button>
              </div>
            </section>
          ) : (
            <section className="bg-white border border-gray-200 rounded-2xl p-8 shadow-sm text-center">
              <h2 className="text-2xl font-bold text-gray-900 mb-2">Тестът е предаден</h2>
              {(() => {
                const { score, maxScore } = scoreCurrentExam();
                const pct = maxScore > 0 ? Math.round((score / maxScore) * 100) : 0;
                return (
                  <div className="max-w-md mx-auto mb-5">
                    <p className="text-5xl font-black text-blue-600 mb-1">{pct}%</p>
                    <p className="text-sm text-gray-500">{score} верни от {maxScore} задачи с избор (Модул 1)</p>
                  </div>
                );
              })()}
              
              {/* XP Award Breakdown */}
              {xpAwardResult && (
                <div className="max-w-md mx-auto mb-6 rounded-xl border border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50 p-4">
                  <h3 className="text-sm font-bold text-amber-800 mb-3 flex items-center justify-center gap-2">
                    <span>⭐</span> Получени XP
                  </h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Базови XP ({xpAwardResult.percentage_correct}%):</span>
                      <span className="font-semibold">+{xpAwardResult.base_xp}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Трудност ({xpAwardResult.difficulty} {xpAwardResult.difficulty_multiplier}x):</span>
                      <span className={`font-semibold ${xpAwardResult.difficulty_bonus_xp >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {xpAwardResult.difficulty_bonus_xp >= 0 ? '+' : ''}{xpAwardResult.difficulty_bonus_xp}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Време ({xpAwardResult.minutes_taken}мин, {xpAwardResult.time_multiplier}x):</span>
                      <span className={`font-semibold ${xpAwardResult.time_bonus_xp >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {xpAwardResult.time_bonus_xp >= 0 ? '+' : ''}{xpAwardResult.time_bonus_xp}
                      </span>
                    </div>
                    <div className="border-t border-amber-200 pt-2 mt-2">
                      <div className="flex justify-between text-lg font-bold">
                        <span className="text-amber-800">Общо XP:</span>
                        <span className="text-amber-700">+{xpAwardResult.final_xp} XP</span>
                      </div>
                    </div>
                    {xpAwardResult.leveled_up && (
                      <div className="mt-2 text-center">
                        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-purple-100 text-purple-700 text-xs font-bold">
                          🎉 Ново ниво {xpAwardResult.level_info.level}!
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              <div className="max-w-md mx-auto rounded-xl bg-slate-50 border border-slate-200 p-4 text-left mb-6">
                <p className="text-sm text-gray-700 mb-1">Отговорени задачи: <strong>{answeredCount}/{examQuestions.length}</strong></p>
                <p className="text-sm text-gray-700">Маркирани за преглед: <strong>{markedForReview.length}</strong></p>
              </div>
              <div className="flex justify-center gap-3">
                <button
                  onClick={() => {
                    setSubmitted(false);
                    setExamStarted(false);
                  }}
                  className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700"
                >
                  Към НВО таблото
                </button>
                <button
                  onClick={restartExam}
                  className="px-4 py-2 rounded-lg bg-blue-600 text-white"
                >
                  Нова тренировка
                </button>
              </div>
            </section>
          )}
        </main>
      </div>
      </div>

      {showTabWarning && isExamLocked && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl text-center">
            <div className="text-4xl mb-3">⚠️</div>
            <h3 className="text-lg font-bold text-gray-900 mb-2">Напуснахте теста!</h3>
            <p className="text-gray-600 mb-5 text-sm">
              По време на НВО тренировка не можете да превключвате табове. Върнете се към теста.
            </p>
            <button
              onClick={() => setShowTabWarning(false)}
              className="w-full px-4 py-2.5 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700"
            >
              Върни се към теста
            </button>
          </div>
        </div>
      )}

      {showUnansweredWarning && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 max-w-md w-full">
            <h3 className="text-lg font-bold text-gray-900 mb-2">Има непопълнени задачи</h3>
            <p className="text-gray-600 mb-5">
              Имате {unansweredCount} непопълнени задачи. Искате ли да предадете теста все пак?
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowUnansweredWarning(false)}
                className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700"
              >
                Продължи решаването
              </button>
              <button
                onClick={forceSubmit}
                disabled={isSubmittingExam}
                className="px-4 py-2 rounded-lg bg-rose-600 text-white disabled:opacity-60"
              >
                {isSubmittingExam ? 'Предаване...' : 'Предай все пак'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default NVOPracticeExamPage;
