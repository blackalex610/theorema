/**
 * NVOBlueprintSelector.tsx
 *
 * Which *shape* of exam to sit — a separate axis from NVOFormatSelector, which
 * picks the length (full sitting vs. short practice run).
 *
 * The format changed for real in June 2026: Part 1 went from 75 to 90 minutes,
 * multiple choice was cut from 20 items to 14, and a short-answer block
 * (задачи с кратък свободен отговор) came back at positions 15–21, pushing
 * Part 2 to 22–24. Students who have been drilling on 2024/2025 past papers
 * still want that shape, so both are offered rather than one silently
 * replacing the other.
 *
 * Counts and durations are read from the server rather than hard-coded here,
 * so a third format costs a blueprint entry in Python and nothing in the UI.
 */
import React from 'react';
import type { NVOBlueprintCode, NVOBlueprintInfo } from '../services/nvo';

interface Props {
  blueprints: NVOBlueprintInfo[];
  selected: NVOBlueprintCode;
  onSelect: (code: NVOBlueprintCode) => void;
  disabled?: boolean;
  loading?: boolean;
}

const ACCENT: Record<string, { ring: string; border: string; bg: string; text: string; chip: string }> = {
  nvo2026: {
    ring: 'ring-sky-400',
    border: 'border-sky-200 dark:border-sky-800',
    bg: 'bg-gradient-to-br from-sky-50 to-cyan-50 dark:from-sky-950/30 dark:to-cyan-950/20',
    text: 'text-sky-700 dark:text-sky-300',
    chip: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300',
  },
  classic: {
    ring: 'ring-amber-400',
    border: 'border-amber-200 dark:border-amber-800',
    bg: 'bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/30 dark:to-orange-950/20',
    text: 'text-amber-700 dark:text-amber-300',
    chip: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  },
};

const fallbackAccent = ACCENT.classic;

const structureLine = (bp: NVOBlueprintInfo): string => {
  const bits = [`${bp.mcCount} с избираем отговор`];
  if (bp.shortCount > 0) bits.push(`${bp.shortCount} с кратък отговор`);
  bits.push(`${bp.openCount} с пълно решение`);
  return bits.join(' · ');
};

const NVOBlueprintSelector: React.FC<Props> = ({
  blueprints,
  selected,
  onSelect,
  disabled = false,
  loading = false,
}) => {
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="text-center space-y-2">
          <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100">
            Избери формат на изпита
          </h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[0, 1].map((i) => (
            <div
              key={i}
              className="h-40 rounded-2xl border-2 border-slate-200 dark:border-slate-700
                         bg-slate-50 dark:bg-slate-800/40 animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  if (blueprints.length === 0) return null;

  return (
    <div className="space-y-4">
      <div className="text-center space-y-2">
        <h3 className="text-lg font-bold text-slate-800 dark:text-slate-100">
          Избери формат на изпита
        </h3>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Структурата на НВО се промени през 2026 г. Избери по кой формат да се подготвяш.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3" role="radiogroup" aria-label="Формат на изпита">
        {blueprints.map((bp) => {
          const accent = ACCENT[bp.code] ?? fallbackAccent;
          const isSelected = selected === bp.code;
          return (
            <button
              key={bp.code}
              type="button"
              role="radio"
              aria-checked={isSelected}
              id={`nvo-blueprint-${bp.code}`}
              onClick={() => !disabled && onSelect(bp.code)}
              disabled={disabled}
              className={`
                relative rounded-2xl border-2 p-4 text-left transition-all duration-200
                ${accent.border} ${accent.bg}
                ${isSelected ? `ring-2 ring-offset-2 ${accent.ring}` : ''}
                ${disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:shadow-md hover:-translate-y-0.5'}
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-blue-500
              `}
            >
              {isSelected && (
                <span
                  className="absolute -top-2 -right-2 flex h-6 w-6 items-center justify-center
                             rounded-full bg-blue-500 text-white text-sm shadow-sm"
                  aria-hidden="true"
                >
                  ✓
                </span>
              )}

              <div className="space-y-3">
                <div>
                  <div className={`text-sm font-bold ${accent.text}`}>{bp.label}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">{bp.subtitle}</div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${accent.chip}`}>
                    {bp.questionCount} задачи
                  </span>
                  <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${accent.chip}`}>
                    {bp.part1Minutes} + {bp.part2Minutes} мин
                  </span>
                  <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${accent.chip}`}>
                    {bp.totalPoints} точки
                  </span>
                </div>

                <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                  {structureLine(bp)}
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-500 leading-relaxed">
                  {bp.years}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default NVOBlueprintSelector;
