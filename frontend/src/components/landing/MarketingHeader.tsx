import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ListIcon } from '@phosphor-icons/react';
import { motion, useReducedMotion } from 'framer-motion';

import Brand from '../Brand';
import ThemeSwitch from '../ThemeSwitch';
import { scrollToSection } from '../SmoothScroll';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

const SECTIONS = [
  { id: 'vkljuchva', label: 'Какво включва' },
  { id: 'kak-raboti', label: 'Как работи' },
  { id: 'format', label: 'Изпитният формат' },
  { id: 'mnenia', label: 'Мнения' },
];

/**
 * Marketing navigation. One line, 64px, and it earns its sticky position by
 * shrinking its border and gaining a surface once the hero is behind it.
 *
 * Anchors are handed to Lenis rather than to scrollIntoView so in-page jumps
 * use the same easing as the rest of the scroll.
 */
const MarketingHeader: React.FC = () => {
  const [lifted, setLifted] = useState(false);
  const reduced = useReducedMotion();

  useEffect(() => {
    const target = document.getElementById('hero-sentinel');
    if (!target) return;
    const observer = new IntersectionObserver(
      ([entry]) => setLifted(!entry.isIntersecting),
      { rootMargin: '-64px 0px 0px 0px' }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  return (
    <motion.header
      initial={reduced ? false : { y: -64 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        'fixed inset-x-0 top-0 z-50 transition-[background-color,border-color,backdrop-filter] duration-300',
        lifted
          ? 'border-b border-line bg-paper/85 backdrop-blur-xl'
          : 'border-b border-transparent bg-transparent'
      )}
    >
      <div className="mx-auto flex h-16 w-full max-w-[75rem] items-center gap-6 shell-x">
        <Link to="/" aria-label="Smart NVO, начало" className="rounded-lg">
          <Brand />
        </Link>

        <nav aria-label="Разделите на страницата" className="hidden items-center gap-1 md:flex">
          {SECTIONS.map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => scrollToSection(section.id)}
              className="rounded-lg px-3 py-2 text-caption font-semibold text-ink-muted transition-colors hover:bg-sunken hover:text-ink"
            >
              {section.label}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <ThemeSwitch className="hidden sm:inline-flex" />
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link to="/">Вход</Link>
          </Button>
          <Button asChild size="sm" className="hidden sm:inline-flex">
            <Link to="/">Започни безплатно</Link>
          </Button>

          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" aria-label="Отвори менюто" className="sm:hidden">
                <ListIcon />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[18rem] gap-0 p-0">
              <SheetHeader className="border-b border-line px-5 py-4">
                <SheetTitle className="text-left">
                  <Brand size="sm" />
                </SheetTitle>
              </SheetHeader>
              <nav aria-label="Разделите на страницата" className="flex flex-col p-3">
                {SECTIONS.map((section) => (
                  <SheetClose asChild key={section.id}>
                    <button
                      type="button"
                      onClick={() => scrollToSection(section.id)}
                      className="rounded-lg px-3 py-3 text-left text-body font-semibold text-ink-muted transition-colors hover:bg-sunken hover:text-ink"
                    >
                      {section.label}
                    </button>
                  </SheetClose>
                ))}
              </nav>
              <Separator />
              <div className="flex items-center justify-between px-5 py-4">
                <span className="text-caption font-semibold text-ink-muted">Тема</span>
                <ThemeSwitch />
              </div>
              <Separator />
              <div className="flex flex-col gap-2 p-5">
                <Button asChild>
                  <Link to="/">Започни безплатно</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link to="/">Вход</Link>
                </Button>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </motion.header>
  );
};

export default MarketingHeader;
