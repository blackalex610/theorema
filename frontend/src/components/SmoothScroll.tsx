import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import Lenis from 'lenis';

/**
 * Global smooth scrolling.
 *
 * Lenis drives the real document scroll position rather than transforming a
 * wrapper, so Motion's `useScroll` and `whileInView` read it for free and no
 * component ever needs a `window.scrollY` listener.
 *
 * The instance is exposed on `window.__lenis` so in-page anchors can hand the
 * target off to Lenis instead of fighting it with `scrollIntoView`.
 */

declare global {
  interface Window {
    __lenis?: Lenis;
  }
}

export function scrollToSection(target: string | HTMLElement, offset = -88) {
  const lenis = window.__lenis;
  const el = typeof target === 'string' ? document.getElementById(target) : target;
  if (!el) return;
  if (lenis) {
    lenis.scrollTo(el, { offset, duration: 0.9 });
  } else {
    el.scrollIntoView({ behavior: 'auto', block: 'start' });
  }
}

const SmoothScroll: React.FC<React.PropsWithChildren> = ({ children }) => {
  const { pathname } = useLocation();

  useEffect(() => {
    // Anyone who asked their OS for less motion gets the browser's native
    // scroll, untouched. Instantiating Lenis at all would override it.
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (query.matches) return;

    const lenis = new Lenis({
      lerp: 0.1,
      wheelMultiplier: 1,
      touchMultiplier: 1.6,
      smoothWheel: true,
      // Native scrolling inside modals, dropdowns and code blocks.
      prevent: (node: Element) => node.closest('[data-lenis-prevent]') !== null,
    });
    window.__lenis = lenis;

    let frame = 0;
    const raf = (time: number) => {
      lenis.raf(time);
      frame = requestAnimationFrame(raf);
    };
    frame = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(frame);
      lenis.destroy();
      delete window.__lenis;
    };
  }, []);

  // A route change should land at the top of the new page, immediately.
  useEffect(() => {
    window.__lenis?.scrollTo(0, { immediate: true });
    window.scrollTo(0, 0);
  }, [pathname]);

  return <>{children}</>;
};

export default SmoothScroll;
