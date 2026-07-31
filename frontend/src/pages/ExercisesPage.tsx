import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import 'katex/dist/katex.min.css';
import { getAIExercises, submitAnswer, type Exercise, type ExerciseSubmissionResponse } from '../services/curriculum';
import { trackMissionProgress } from '../services/progress';
import { trackEvent } from '../services/analytics';
import AppNavbar from '../components/AppNavbar';
import XpToast from '../components/XpToast';
import LevelUpModal from '../components/LevelUpModal';
import UpgradePrompt from '../components/UpgradePrompt';
import FeedbackButtons from '../components/FeedbackButtons';
import { getLimitErrorDetail } from '../services/api';
import { usePlan } from '../hooks/usePlan';
import { usePlanPrompt } from '../hooks/usePlanPrompt';
import { useXp } from '../context/XpContext';
import { renderMathText } from '../components/MathRenderer';

interface ExerciseState {
  exercise: Exercise;
  userAnswer: string;
  submission: ExerciseSubmissionResponse | null;
  isSubmitted: boolean;
}

const ExercisesPage: React.FC = () => {
  const { lessonId } = useParams<{ lessonId: string }>();
  const [searchParams] = useSearchParams();
  const missionId = searchParams.get('mission_id');
  
  const [exerciseStates, setExerciseStates] = useState<ExerciseState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  // XP feedback state
  const [xpToast, setXpToast] = useState<{ key: number; xp: number } | null>(null);
  const [levelUpModal, setLevelUpModal] = useState<{ level: number } | null>(null);
  const [limitError, setLimitError] = useState<{ feature: string; message: string } | null>(null);

  const { status: planStatus } = usePlan();
  const { refreshXp } = useXp();
  const { maybeShow: maybeShowUpgrade, dismiss: dismissUpgrade } = usePlanPrompt(setLimitError);

  const loadExercises = async (regenerate = false) => {
    if (!lessonId) return;
    try {
      if (regenerate) setGenerating(true);
      else setLoading(true);
      setError(null);
      const exercises = await getAIExercises(parseInt(lessonId), regenerate);
      setExerciseStates(
        exercises.map((exercise) => ({
          exercise,
          userAnswer: '',
          submission: null,
          isSubmitted: false,
        }))
      );
    } catch (err: any) {
      const limitDetail = getLimitErrorDetail(err);
      if (limitDetail) {
        maybeShowUpgrade({
          feature: limitDetail.feature,
          message: limitDetail.message,
          daysSinceSignup: planStatus.days_since_signup,
          isPremium: planStatus.is_premium,
        });
      } else {
        const detail = err?.response?.data?.detail;
        let message = 'Грешка при генериране на упражненията';
        if (typeof detail === 'string') message = detail;
        else if (detail?.message) message = detail.message;
        setError(message);
      }
      console.error('Error fetching exercises:', err);
    } finally {
      setLoading(false);
      setGenerating(false);
    }
  };

  useEffect(() => {
    loadExercises();
  }, [lessonId]);

  const latexToPlainAnswer = (input: string): string => {
    let normalized = input;

    // Convert simple LaTeX fractions to slash form for backend answer checks.
    normalized = normalized.replace(/\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}/g, '($1)/($2)');
    normalized = normalized.replace(/\\cdot/g, '*');
    normalized = normalized.replace(/\\times/g, '*');
    normalized = normalized.replace(/\\div/g, '/');

    return normalized;
  };

  const insertTemplate = (index: number, template: string) => {
    setExerciseStates((prev) =>
      prev.map((state, i) =>
        i === index ? { ...state, userAnswer: state.userAnswer + template } : state
      )
    );
  };

  const handleAnswerChange = (index: number, value: string) => {
    setExerciseStates((prev) =>
      prev.map((state, i) =>
        i === index ? { ...state, userAnswer: value } : state
      )
    );
  };

  const handleSubmit = async (index: number) => {
    const state = exerciseStates[index];
    if (!state.userAnswer.trim()) {
      alert('Моля, въведете отговор');
      return;
    }

    const allSubmittedAfterThisAnswer = exerciseStates.every((s, i) => (i === index ? true : s.isSubmitted));

    try {
      const normalizedAnswer = latexToPlainAnswer(state.userAnswer);
      const result = await submitAnswer(state.exercise.id, normalizedAnswer);
      trackEvent('exercise_completed', {
        lesson_id: lessonId ? parseInt(lessonId, 10) : null,
        exercise_id: state.exercise.id,
        correct: result.correct,
        difficulty: state.exercise.difficulty,
        exercise_type: state.exercise.exercise_type,
      });
      if (allSubmittedAfterThisAnswer) {
        trackEvent('lesson_completed', {
          lesson_id: lessonId ? parseInt(lessonId, 10) : null,
          total_exercises: exerciseStates.length,
        });
      }
      setExerciseStates((prev) =>
        prev.map((s, i) =>
          i === index
            ? { ...s, submission: result, isSubmitted: true }
            : s
        )
      );
      // Show XP feedback
      if (result.xp_gained > 0) {
        setXpToast({ key: Date.now(), xp: result.xp_gained });
        refreshXp();
      }
      if (result.leveled_up) {
        setLevelUpModal({ level: result.new_level });
      }

      // Mission completion tracking
      if (missionId) {
        try {
          const missionResult = await trackMissionProgress(missionId, state.exercise.id, result.correct);
          if (missionResult.xp_earned > 0) {
            setTimeout(() => {
              setXpToast({ key: Date.now(), xp: missionResult.xp_earned });
              alert(`🎉 Мисията е завършена!\n+${missionResult.xp_earned} XP бонус за мисия`);
            }, 1200);
          }
        } catch (err) {
          console.error('Error tracking mission progress:', err);
        }
      }
    } catch (err) {
      console.error('Error submitting answer:', err);
      alert('Грешка при изпращане на отговора');
    }
  };

  const handleReset = (index: number) => {
    setExerciseStates((prev) =>
      prev.map((s, i) =>
        i === index
          ? { ...s, userAnswer: '', submission: null, isSubmitted: false }
          : s
      )
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-xl text-gray-600 mb-2">Генериране на упражнения с AI...</div>
          <div className="text-sm text-gray-400">Моля, изчакайте</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-xl text-red-600">{error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-transparent">
      <AppNavbar />

      {limitError && (
        <UpgradePrompt
          feature={limitError.feature}
          message={limitError.message}
          onClose={dismissUpgrade}
        />
      )}

      {/* XP gain toast */}
      {xpToast && (
        <XpToast key={xpToast.key} xp={xpToast.xp} onDone={() => setXpToast(null)} />
      )}
      {/* Level-up modal */}
      {levelUpModal && (
        <LevelUpModal newLevel={levelUpModal.level} onClose={() => setLevelUpModal(null)} />
      )}

      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-gray-900">Упражнения</h2>
          <p className="mt-2 text-gray-600">
            Решете упражненията и проверете отговорите си
          </p>
          <button
            onClick={() => loadExercises(true)}
            disabled={generating}
            className="mt-3 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-60 transition-colors"
          >
            {generating ? (
              <>
                <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                Генериране...
              </>
            ) : (
              <>
                ✨ Генерирай нови упражнения
              </>
            )}
          </button>
        </div>

        {exerciseStates.length === 0 ? (
          <div className="bg-white p-8 rounded-lg shadow-md text-center">
            <p className="text-gray-600 mb-4">Няма генерирани упражнения за този урок</p>
            <button
              onClick={() => loadExercises(true)}
              disabled={generating}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-60"
            >
              {generating ? 'Генериране...' : '✨ Генерирай с AI'}
            </button>
          </div>
        ) : (
          <div className="space-y-8">
            {exerciseStates.map((state, index) => (
              <div
                key={state.exercise.id}
                className="bg-white p-6 rounded-lg shadow-md border border-gray-200"
              >
                {/* Exercise Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <span className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 font-bold">
                      {index + 1}
                    </span>
                    <div className="flex items-center space-x-2">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          state.exercise.difficulty === 'easy'
                            ? 'bg-green-100 text-green-700'
                            : state.exercise.difficulty === 'medium'
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-red-100 text-red-700'
                        }`}
                      >
                        {state.exercise.difficulty === 'easy' && 'Лесно'}
                        {state.exercise.difficulty === 'medium' && 'Средно'}
                        {state.exercise.difficulty === 'hard' && 'Трудно'}
                      </span>
                      <span className="px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700">
                        {state.exercise.exercise_type === 'multiple_choice' && 'Избор'}
                        {state.exercise.exercise_type === 'numeric' && 'Числов отговор'}
                        {state.exercise.exercise_type === 'algebra' && 'Алгебра'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Exercise Question */}
                <div className="mb-6 text-lg text-gray-800 leading-relaxed">
                  {renderMathText(state.exercise.question)}
                </div>

                {/* Answer Input */}
                {!state.isSubmitted ? (
                  <div className="space-y-4">
                    <div className="rounded-md border border-blue-200 bg-blue-50 p-3 dark:border-blue-700 dark:bg-slate-800">
                      <p className="text-xs font-semibold text-blue-800 mb-2 dark:text-blue-300">
                        Математична нотация
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => insertTemplate(index, '\\frac{a}{b}')}
                          className="px-2 py-1 text-xs bg-white border border-blue-200 rounded hover:bg-blue-100 dark:bg-slate-900 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                        >
                          Дроб: a/b
                        </button>
                        <button
                          type="button"
                          onClick={() => insertTemplate(index, 'x^{2}')}
                          className="px-2 py-1 text-xs bg-white border border-blue-200 rounded hover:bg-blue-100 dark:bg-slate-900 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                        >
                          Степен: x^2
                        </button>
                        <button
                          type="button"
                          onClick={() => insertTemplate(index, '\\sqrt{x}')}
                          className="px-2 py-1 text-xs bg-white border border-blue-200 rounded hover:bg-blue-100 dark:bg-slate-900 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                        >
                          Корен: √x
                        </button>
                        <button
                          type="button"
                          onClick={() => insertTemplate(index, '(')}
                          className="px-2 py-1 text-xs bg-white border border-blue-200 rounded hover:bg-blue-100 dark:bg-slate-900 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                        >
                          (
                        </button>
                        <button
                          type="button"
                          onClick={() => insertTemplate(index, ')')}
                          className="px-2 py-1 text-xs bg-white border border-blue-200 rounded hover:bg-blue-100 dark:bg-slate-900 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-700"
                        >
                          )
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2 dark:text-slate-200">
                        Вашият отговор:
                      </label>
                      <input
                        type="text"
                        value={state.userAnswer}
                        onChange={(e) => handleAnswerChange(index, e.target.value)}
                        placeholder="Напр. \frac{3}{4} или 3/4"
                        className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:placeholder-slate-400"
                        onKeyPress={(e) => {
                          if (e.key === 'Enter') {
                            handleSubmit(index);
                          }
                        }}
                      />
                      <p className="mt-2 text-xs text-gray-500 dark:text-slate-400">
                        Може да пишете с LaTeX: \frac{'{a}'}{'{b}'}, x^2, \sqrt{'{x}'}.
                      </p>
                    </div>

                    <div className="p-3 bg-gray-50 border border-gray-200 rounded-md dark:bg-slate-900 dark:border-slate-700">
                      <p className="text-xs font-medium text-gray-500 mb-2 dark:text-slate-400">Преглед:</p>
                      <div className="text-gray-900 min-h-6 dark:text-slate-100">
                        {renderMathText(state.userAnswer)}
                      </div>
                    </div>
                    <button
                      onClick={() => handleSubmit(index)}
                      className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors font-medium"
                    >
                      Провери отговора
                    </button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Result Display */}
                    <div
                      className={`p-4 rounded-md ${
                        state.submission?.correct
                          ? 'bg-green-50 border border-green-200'
                          : 'bg-red-50 border border-red-200'
                      }`}
                    >
                      <div className="flex items-center space-x-2 mb-2">
                        {state.submission?.correct ? (
                          <>
                            <svg
                              className="w-6 h-6 text-green-600"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M5 13l4 4L19 7"
                              />
                            </svg>
                            <span className="font-semibold text-green-800">
                              Вярно! Браво!
                            </span>
                          </>
                        ) : (
                          <>
                            <svg
                              className="w-6 h-6 text-red-600"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                              />
                            </svg>
                            <span className="font-semibold text-red-800">
                              Грешно. Опитай отново!
                            </span>
                          </>
                        )}
                      </div>
                      <div className="text-sm space-y-1">
                        <p>
                          <span className="font-medium">Твоят отговор:</span>{' '}
                          <span className={state.submission?.correct ? 'text-green-700' : 'text-red-700'}>
                            {state.submission?.submitted_answer}
                          </span>
                        </p>
                        {!state.submission?.correct && (
                          <p>
                            <span className="font-medium">Верен отговор:</span>{' '}
                            <span className="text-green-700">
                              {state.submission?.correct_answer}
                            </span>
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Solution Display */}
                    {state.submission?.solution && (
                      <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
                        <h4 className="font-semibold text-blue-900 mb-2">
                          Решение:
                        </h4>
                        <div className="text-gray-800 leading-relaxed">
                          {renderMathText(state.submission.solution)}
                        </div>
                        <div className="mt-3 pt-3 border-t border-blue-100">
                          <FeedbackButtons
                            contentType="explanation"
                            contentId={String(state.exercise?.id ?? '')}
                            topic={state.exercise?.lesson_id ? String(state.exercise.lesson_id) : undefined}
                            difficulty={state.exercise?.difficulty}
                          />
                        </div>
                      </div>
                    )}

                    {/* Reset Button */}
                    <button
                      onClick={() => handleReset(index)}
                      className="w-full bg-gray-500 text-white py-2 px-4 rounded-md hover:bg-gray-600 transition-colors font-medium"
                    >
                      Опитай отново
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default ExercisesPage;
