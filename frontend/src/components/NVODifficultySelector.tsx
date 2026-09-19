import React from 'react';
import type { NVODifficultyCode } from '../services/nvo';

/**
 * The four levels a student can sit the same paper at.
 *
 * `actual` is the real exam: the structure, the item mix and the timing of an
 * official НВО paper. The other three are versions of it — the positions,
 * topics and points never change, only how hard each item is and how long the
 * clock runs. Mirrors `backend/app/nvo_gen/difficulty.py`.
 *
 * `standard` and `hard` are the names this used to use. The server still
 * resolves them (to `actual` and `extra_hard`), so exams stored before the
 * rename keep rendering; nothing new should be written with them.
 */
export type NVODifficulty = NVODifficultyCode;
export type NVODifficultyStored = NVODifficulty | 'standard' | 'hard';

/** Resolve any stored or legacy spelling to a current level. */
export const normalizeDifficulty = (value: string | null | undefined): NVODifficulty => {
  switch (value) {
    case 'easy':
    case 'medium':
    case 'actual':
    case 'extra_hard':
      return value;
    case 'hard':
      return 'extra_hard';
    default:
      return 'actual';
  }
};

/** XP multiplier per level. Must stay in step with NVO_DIFFICULTY_MULTIPLIERS. */
export const DIFFICULTY_XP: Record<NVODifficulty, string> = {
  easy: '0.5x XP',
  medium: '0.8x XP',
  actual: '1.0x XP',
  extra_hard: '2.0x XP',
};

export const DIFFICULTY_BADGE: Record<NVODifficulty, string> = {
  easy: 'text-green-600 bg-green-100 dark:text-green-300 dark:bg-green-900/40',
  medium: 'text-teal-600 bg-teal-100 dark:text-teal-300 dark:bg-teal-900/40',
  actual: 'text-blue-600 bg-blue-100 dark:text-blue-300 dark:bg-blue-900/40',
  extra_hard: 'text-rose-600 bg-rose-100 dark:text-rose-300 dark:bg-rose-900/40',
};

interface DifficultyOption {
  value: NVODifficulty;
  label: string;
  emoji: string;
  shortDescription: string;
  fullDescription: string;
  colorClasses: {
    border: string;
    bg: string;
    bgHover: string;
    text: string;
    badge: string;
    selectedRing: string;
  };
}

const DIFFICULTY_OPTIONS: DifficultyOption[] = [
  {
    value: 'easy',
    label: 'Лесно',
    emoji: '🌱',
    shortDescription: 'За начало',
    fullDescription: 'Същият изпит, но с по-малки числа и по-кратки задачи. Подходящо, докато си припомняш материала.',
    colorClasses: {
      border: 'border-green-200 dark:border-green-800',
      bg: 'bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/30 dark:to-emerald-950/20',
      bgHover: 'hover:from-green-100 hover:to-emerald-100 dark:hover:from-green-900/40 dark:hover:to-emerald-900/30',
      text: 'text-green-700 dark:text-green-300',
      badge: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
      selectedRing: 'ring-green-400 ring-offset-2',
    },
  },
  {
    value: 'medium',
    label: 'Средно',
    emoji: '📗',
    shortDescription: 'Към реалното ниво',
    fullDescription: 'Малко по-леко от истинския изпит. Същите теми и същият брой задачи, но без най-тежките разсъждения.',
    colorClasses: {
      border: 'border-teal-200 dark:border-teal-800',
      bg: 'bg-gradient-to-br from-teal-50 to-cyan-50 dark:from-teal-950/30 dark:to-cyan-950/20',
      bgHover: 'hover:from-teal-100 hover:to-cyan-100 dark:hover:from-teal-900/40 dark:hover:to-cyan-900/30',
      text: 'text-teal-700 dark:text-teal-300',
      badge: 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300',
      selectedRing: 'ring-teal-400 ring-offset-2',
    },
  },
  {
    value: 'actual',
    label: 'Като на НВО',
    emoji: '📚',
    shortDescription: 'Реалният формат',
    fullDescription: 'Точно както на истинското НВО: същата структура, същата трудност и същото време. Това е изпитът, за който се готвиш.',
    colorClasses: {
      border: 'border-blue-200 dark:border-blue-800',
      bg: 'bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/20',
      bgHover: 'hover:from-blue-100 hover:to-indigo-100 dark:hover:from-blue-900/40 dark:hover:to-indigo-900/30',
      text: 'text-blue-700 dark:text-blue-300',
      badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
      selectedRing: 'ring-blue-400 ring-offset-2',
    },
  },
  {
    value: 'extra_hard',
    label: 'Много трудно',
    emoji: '🔥',
    shortDescription: 'Над нивото на НВО',
    fullDescription: 'По-тежко от изпита: по-големи числа, повече стъпки и по-малко време. За когато реалният вариант вече ти е лесен.',
    colorClasses: {
      border: 'border-rose-200 dark:border-rose-800',
      bg: 'bg-gradient-to-br from-rose-50 to-orange-50 dark:from-rose-950/30 dark:to-orange-950/20',
      bgHover: 'hover:from-rose-100 hover:to-orange-100 dark:hover:from-rose-900/40 dark:hover:to-orange-900/30',
      text: 'text-rose-700 dark:text-rose-300',
      badge: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
      selectedRing: 'ring-rose-400 ring-offset-2',
    },
  },
];

interface NVODifficultySelectorProps {
  selected: NVODifficulty;
  onSelect: (difficulty: NVODifficulty) => void;
  disabled?: boolean;
}

const NVODifficultySelector: React.FC<NVODifficultySelectorProps> = ({
  selected,
  onSelect,
  disabled = false,
}) => {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="text-center space-y-2">
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100">
          Избери ниво на трудност
        </h3>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Какво ниво на сложност искаш за генерирания НВО тест?
        </p>
      </div>

      {/* Difficulty Cards — two up on tablets, four across on desktop */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {DIFFICULTY_OPTIONS.map((option) => {
          const isSelected = selected === option.value;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => !disabled && onSelect(option.value)}
              disabled={disabled}
              className={`
                relative group rounded-2xl border-2 p-4 text-left transition-all duration-200
                ${option.colorClasses.border}
                ${option.colorClasses.bg}
                ${!disabled ? option.colorClasses.bgHover : ''}
                ${isSelected ? `ring-2 ${option.colorClasses.selectedRing}` : ''}
                ${disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:shadow-md hover:-translate-y-0.5'}
              `}
            >
              {/* Selected indicator */}
              {isSelected && (
                <div className="absolute -top-2 -right-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-500 text-white text-sm shadow-sm">
                    ✓
                  </span>
                </div>
              )}

              {/* Content */}
              <div className="space-y-3">
                {/* Emoji & Label */}
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{option.emoji}</span>
                  <span className={`text-sm font-bold ${option.colorClasses.text}`}>
                    {option.label}
                  </span>
                </div>

                {/* Short description + what the level is worth in XP */}
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${option.colorClasses.badge}`}>
                    {option.shortDescription}
                  </span>
                  <span className="inline-block rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {DIFFICULTY_XP[option.value]}
                  </span>
                </div>

                {/* Full description */}
                <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                  {option.fullDescription}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Current selection indicator */}
      <div className="flex items-center justify-center gap-2 pt-2">
        <span className="text-xs text-slate-500 dark:text-slate-400">Избрано:</span>
        <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold ${
          DIFFICULTY_OPTIONS.find(o => o.value === selected)?.colorClasses.badge
        }`}>
          {DIFFICULTY_OPTIONS.find(o => o.value === selected)?.emoji}
          {DIFFICULTY_OPTIONS.find(o => o.value === selected)?.label}
        </span>
      </div>
    </div>
  );
};

export default NVODifficultySelector;
