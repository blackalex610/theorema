import '@testing-library/jest-dom/vitest';

// jsdom has no IntersectionObserver, and framer-motion's whileInView (used by
// the Reveal wrapper inside PageShell/PageHeader) calls it on mount. Without
// this, any test that renders a page built on PageShell dies at import time.
// The stub reports nothing as intersecting, which is fine: Reveal renders its
// children either way, it only animates them.
if (!('IntersectionObserver' in globalThis)) {
  class StubIntersectionObserver implements IntersectionObserver {
    readonly root: Element | Document | null = null;
    readonly rootMargin: string = '';
    readonly thresholds: ReadonlyArray<number> = [];
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  }
  globalThis.IntersectionObserver =
    StubIntersectionObserver as unknown as typeof IntersectionObserver;
}
