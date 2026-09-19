import { Link } from 'react-router-dom';

import Brand from '../Brand';
import SiteFooter from '../landing/SiteFooter';

/**
 * Shell for the public legal documents.
 *
 * Deliberately not MarketingHeader: that header's nav is a set of
 * scroll-to-section buttons that only exist on the landing page, so reusing
 * it here would put four dead controls above a privacy policy.
 */
const LegalPage: React.FC<
  React.PropsWithChildren<{ title: string; updated: string; lead: string }>
> = ({ title, updated, lead, children }) => (
  <div className="min-h-dvh bg-paper">
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex h-16 w-full max-w-[75rem] items-center shell-x">
        <Link to="/" aria-label="Smart NVO, начало" className="rounded-lg">
          <Brand />
        </Link>
      </div>
    </header>

    <main className="mx-auto w-full max-w-[48rem] shell-x py-14">
      <p className="text-micro font-semibold uppercase tracking-[0.1em] text-ink-faint">
        Последна редакция: {updated}
      </p>
      <h1 className="mt-3 font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
        {title}
      </h1>
      <p className="mt-4 text-lead text-ink-muted">{lead}</p>

      <div className="legal-body mt-10 space-y-8">{children}</div>
    </main>

    <SiteFooter />
  </div>
);

export const Section: React.FC<React.PropsWithChildren<{ heading: string }>> = ({
  heading,
  children,
}) => (
  <section className="space-y-3">
    <h2 className="font-display text-xl font-semibold text-ink">{heading}</h2>
    <div className="space-y-3 text-body text-ink-muted [&_a]:text-brand-ink [&_a]:underline [&_li]:ml-5 [&_li]:list-disc [&_strong]:font-semibold [&_strong]:text-ink">
      {children}
    </div>
  </section>
);

export default LegalPage;
