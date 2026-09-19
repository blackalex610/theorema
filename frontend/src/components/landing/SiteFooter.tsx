import { Link } from 'react-router-dom';

import Brand from '../Brand';
import { scrollToSection } from '../SmoothScroll';

type FooterLink = { label: string; to?: string; section?: string };

/*
 * Every link here used to point at '/' — seven dead ends on the one page a
 * parent actually reads, including "Създаване на профил" pointing at
 * /register, which only redirects back to '/'. Links now either scroll to a
 * real section of the marketing page or go to a route that exists.
 */
const COLUMNS: Array<{ heading: string; links: FooterLink[] }> = [
  {
    heading: 'Платформа',
    links: [
      { label: 'Какво включва', section: 'vkljuchva' },
      { label: 'Как работи', section: 'kak-raboti' },
      { label: 'Изпитният формат', section: 'format' },
      { label: 'Мнения', section: 'mnenia' },
    ],
  },
  {
    heading: 'Учебно съдържание',
    links: [
      { label: 'Упражнения по теми', to: '/grades' },
      { label: 'Теория по уроци', to: '/learn/grades' },
      { label: 'Пробни НВО изпити', to: '/nvo/practice' },
      { label: 'Моят напредък', to: '/progress' },
    ],
  },
  {
    heading: 'Профил',
    links: [
      { label: 'Вход', to: '/' },
      { label: 'Табло', to: '/dashboard' },
    ],
  },
  {
    heading: 'Правна информация',
    links: [
      { label: 'Поверителност', to: '/privacy' },
      { label: 'Условия за ползване', to: '/terms' },
    ],
  },
];

const SiteFooter: React.FC = () => (
  <footer className="border-t border-line bg-surface">
    <div className="mx-auto w-full max-w-[75rem] shell-x py-14">
      <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(2,1fr)] lg:grid-cols-[1.4fr_repeat(4,1fr)]">
        <div className="space-y-4">
          <Brand />
          <p className="max-w-xs text-caption text-ink-muted">
            Подготовка по математика за Националното външно оценяване, за ученици от 5. до 7. клас.
          </p>
        </div>

        {COLUMNS.map((column) => (
          <nav key={column.heading} aria-label={column.heading}>
            <h2 className="text-micro font-semibold uppercase tracking-[0.1em] text-ink-faint">
              {column.heading}
            </h2>
            <ul className="mt-4 space-y-2.5">
              {column.links.map((link) => (
                <li key={link.label}>
                  {link.to ? (
                    <Link
                      to={link.to}
                      className="rounded text-caption text-ink-muted transition-colors hover:text-ink"
                    >
                      {link.label}
                    </Link>
                  ) : (
                    <button
                      type="button"
                      onClick={() => scrollToSection(String(link.section))}
                      className="rounded text-caption text-ink-muted transition-colors hover:text-ink"
                    >
                      {link.label}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>

      <div className="mt-12 flex flex-col gap-3 border-t border-line pt-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="tnum text-caption text-ink-faint">
          &copy; 2026 Smart NVO. Всички права запазени.
        </p>
        <p className="text-caption text-ink-faint">
          Платформата е с образователна цел и не е свързана с МОН.
        </p>
      </div>
    </div>
  </footer>
);

export default SiteFooter;
