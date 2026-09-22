import { useNavigate } from 'react-router-dom';
import { ArrowLeftIcon, PrinterIcon } from '@phosphor-icons/react';

import { Button } from '@/components/ui/button';

/**
 * A printable page: an A4-width sheet with a toolbar that disappears on
 * paper. Saved as PDF from the browser's print dialog, so there is no PDF
 * library in the bundle and nothing to keep in step with the screen views.
 */
export const ReportShell: React.FC<{
  title: string;
  subtitle: string;
  children: React.ReactNode;
}> = ({ title, subtitle, children }) => {
  const navigate = useNavigate();
  const today = new Date().toLocaleDateString('bg-BG', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="min-h-screen bg-paper px-4 py-6 print:bg-white print:p-0">
      <div className="mx-auto mb-4 flex max-w-[52rem] items-center justify-between gap-3 print:hidden">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ArrowLeftIcon />
          Назад
        </Button>
        <div className="flex items-center gap-3">
          <span className="hidden text-caption text-ink-muted sm:inline">
            За PDF избери „Запази като PDF“ в прозореца за печат.
          </span>
          <Button size="sm" onClick={() => window.print()}>
            <PrinterIcon />
            Печат
          </Button>
        </div>
      </div>

      <article className="mx-auto max-w-[52rem] rounded-xl border border-line bg-surface p-8 shadow-lift-1 print:max-w-none print:rounded-none print:border-0 print:p-0 print:shadow-none">
        <header className="mb-8 flex items-end justify-between gap-6 border-b-2 border-ink pb-4">
          <div>
            <p className="text-micro font-semibold uppercase tracking-[0.12em] text-brand-ink">
              SmartNVO · Математика
            </p>
            <h1 className="mt-1 font-display text-[1.75rem] font-semibold leading-tight text-ink">
              {title}
            </h1>
            <p className="mt-1 text-caption text-ink-muted">{subtitle}</p>
          </div>
          <p className="tnum shrink-0 text-right text-caption text-ink-muted">{today}</p>
        </header>
        {children}
        <footer className="mt-10 border-t border-line pt-3 text-micro text-ink-faint">
          Резултатите са от изпити, оценени на сървъра на SmartNVO, по формата на НВО по
          математика след 7. клас.
        </footer>
      </article>
    </div>
  );
};

export const ReportSection: React.FC<{ title: string; children: React.ReactNode }> = ({
  title,
  children,
}) => (
  <section className="print-avoid-break mb-8">
    <h2 className="mb-3 font-display text-title font-semibold text-ink">{title}</h2>
    {children}
  </section>
);

export const ReportFigure: React.FC<{ label: string; value: string; hint?: string }> = ({
  label,
  value,
  hint,
}) => (
  <div className="rounded-lg border border-line px-4 py-3">
    <p className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">{label}</p>
    <p className="tnum mt-1 text-[1.5rem] font-semibold leading-none text-ink">{value}</p>
    {hint && <p className="mt-1 text-micro text-ink-muted">{hint}</p>}
  </div>
);
