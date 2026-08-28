import * as React from 'react';
import { motion, useReducedMotion, type Variants } from 'framer-motion';

import { cn } from '@/lib/utils';

/**
 * The one scroll-reveal in the system.
 *
 * Everything enters the same way: a short rise with a low-amplitude offset, on
 * the ease the rest of the product uses. Children stagger at 60ms, capped so a
 * long list never leaves its last item trailing behind the reader.
 *
 * With reduced motion requested, content is simply present. No fade, no delay.
 */

const EASE = [0.22, 1, 0.36, 1] as const;

export const riseVariants: Variants = {
  hidden: { opacity: 0, y: 14 },
  shown: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE } },
};

type BaseProps = {
  children?: React.ReactNode;
  className?: string;
  id?: string;
};

/** A single element that rises into place the first time it is scrolled into view. */
export const Reveal: React.FC<BaseProps & { delay?: number }> = ({
  children,
  className,
  id,
  delay = 0,
}) => {
  const reduced = useReducedMotion();

  if (reduced) {
    return (
      <div id={id} className={className}>
        {children}
      </div>
    );
  }

  return (
    <motion.div
      id={id}
      className={className}
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -12% 0px' }}
      transition={{ duration: 0.45, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
};

/** Wrap a group; every direct <RevealItem> inside enters in sequence. */
export const RevealGroup: React.FC<BaseProps & { step?: number }> = ({
  children,
  className,
  id,
  step = 0.06,
}) => {
  const reduced = useReducedMotion();

  if (reduced) {
    return (
      <div id={id} className={className}>
        {children}
      </div>
    );
  }

  return (
    <motion.div
      id={id}
      className={className}
      initial="hidden"
      whileInView="shown"
      viewport={{ once: true, margin: '0px 0px -10% 0px' }}
      variants={{ shown: { transition: { staggerChildren: step } } }}
    >
      {children}
    </motion.div>
  );
};

export const RevealItem: React.FC<BaseProps> = ({ children, className, id }) => {
  const reduced = useReducedMotion();

  if (reduced) {
    return (
      <div id={id} className={className}>
        {children}
      </div>
    );
  }

  return (
    <motion.div id={id} className={className} variants={riseVariants}>
      {children}
    </motion.div>
  );
};

/**
 * Hover physics for primary calls to action: a spring, not a duration. Lift is
 * deliberately small; the point is that the control feels sprung under the
 * cursor, not that it jumps off the page.
 */
export function useSpringHover() {
  const reduced = useReducedMotion();
  if (reduced) return {};
  return {
    whileHover: { y: -2, scale: 1.015 },
    whileTap: { y: 0, scale: 0.985 },
    transition: { type: 'spring' as const, stiffness: 420, damping: 26, mass: 0.6 },
  };
}

/** Shared class for anything that should sit on the measured content column. */
export const shellClass = (extra?: string) =>
  cn('mx-auto w-full max-w-[75rem] shell-x', extra);
