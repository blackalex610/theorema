import { MoonIcon, SunIcon } from '@phosphor-icons/react';
import { motion, useReducedMotion } from 'framer-motion';

import { useSettings } from '../context/SettingsContext';
import { cn } from '@/lib/utils';

/**
 * Two-state theme control.
 *
 * Rendered as a single track with a sliding thumb rather than a swap-the-icon
 * button, so the current mode is readable without hovering for a tooltip.
 */
const ThemeSwitch: React.FC<{ className?: string }> = ({ className }) => {
  const { theme, setTheme } = useSettings();
  const reduced = useReducedMotion();

  const modes = [
    { value: 'light' as const, label: 'Светла тема', Icon: SunIcon },
    { value: 'dark' as const, label: 'Тъмна тема', Icon: MoonIcon },
  ];

  return (
    <div
      role="radiogroup"
      aria-label="Тема на интерфейса"
      className={cn(
        'relative inline-flex items-center gap-0.5 rounded-lg border border-line bg-sunken p-0.5',
        className
      )}
    >
      {modes.map(({ value, label, Icon }) => {
        const active = theme === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={label}
            title={label}
            onClick={() => setTheme(value)}
            className={cn(
              'relative inline-flex size-8 items-center justify-center rounded-md transition-colors duration-200',
              active ? 'text-ink' : 'text-ink-faint hover:text-ink-muted'
            )}
          >
            {active && (
              <motion.span
                layoutId="theme-thumb"
                transition={
                  reduced
                    ? { duration: 0 }
                    : { type: 'spring', stiffness: 480, damping: 34 }
                }
                className="absolute inset-0 rounded-md bg-surface shadow-lift-1"
              />
            )}
            <Icon weight={active ? 'fill' : 'regular'} className="relative size-4" />
          </button>
        );
      })}
    </div>
  );
};

export default ThemeSwitch;
