import { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowRightIcon, CheckIcon, XIcon } from '@phosphor-icons/react';

import { renderMathText } from '../MathRenderer';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/**
 * The hero's thesis: a real NVO question, gradeable on the spot.
 *
 * This is the product in one object. Rather than showing a picture of the app,
 * the landing page hands the visitor an actual exam item rendered through the
 * same KaTeX pipeline the exam screens use, and grades it the same way. Nothing
 * here is a mock.
 */

type Question = {
  prompt: string;
  options: string[];
  correct: number;
  explanation: string;
  topic: string;
};

/** Items follow the 7th grade NVO style: four choices, labelled А to Г. */
const QUESTIONS: Question[] = [
  {
    topic: 'Обикновени дроби',
    prompt: 'Стойността на израза $\\frac{3}{4} + \\frac{5}{6}$ е:',
    options: ['$\\frac{19}{12}$', '$\\frac{8}{10}$', '$\\frac{15}{24}$', '$\\frac{4}{5}$'],
    correct: 0,
    explanation:
      'Общият знаменател е 12. Тогава $\\frac{3}{4}=\\frac{9}{12}$ и $\\frac{5}{6}=\\frac{10}{12}$, а сборът е $\\frac{19}{12}$.',
  },
  {
    topic: 'Линейни уравнения',
    prompt: 'Ако $3x - 7 = 14$, то стойността на $x$ е:',
    options: ['$5$', '$7$', '$21$', '$-7$'],
    correct: 1,
    explanation:
      'Прибавяме 7 от двете страни: $3x = 21$. Разделяме на 3 и получаваме $x = 7$.',
  },
  {
    topic: 'Лице и периметър',
    prompt:
      'Правоъгълник има периметър 36 cm и дължина 11 cm. Лицето на правоъгълника е:',
    options: ['$77\\ \\text{cm}^2$', '$88\\ \\text{cm}^2$', '$99\\ \\text{cm}^2$', '$121\\ \\text{cm}^2$'],
    correct: 0,
    explanation:
      'От $2(11 + b) = 36$ следва $b = 7$ cm. Лицето е $11 \\cdot 7 = 77$ cm$^2$.',
  },
];

const LABELS = ['А', 'Б', 'В', 'Г'];

const HeroExamCard: React.FC = () => {
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const reduced = useReducedMotion();

  const question = QUESTIONS[index];
  const answered = picked !== null;
  const isRight = picked === question.correct;
  const isLast = index === QUESTIONS.length - 1;

  const next = () => {
    setPicked(null);
    setIndex((current) => (current + 1) % QUESTIONS.length);
  };

  return (
    <div className="rounded-2xl border border-line bg-surface shadow-lift-2">
      {/* Sheet header, styled like the exam paper it stands in for */}
      <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="text-micro font-semibold uppercase tracking-[0.1em] text-ink-faint">
            Пробен въпрос
          </span>
          <Badge variant="neutral" className="normal-case tracking-normal">
            {question.topic}
          </Badge>
        </div>
        <span className="tnum text-caption text-ink-faint" aria-label={`Въпрос ${index + 1} от ${QUESTIONS.length}`}>
          {String(index + 1).padStart(2, '0')} / {String(QUESTIONS.length).padStart(2, '0')}
        </span>
      </div>

      <div className="p-5 sm:p-6">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={index}
            initial={reduced ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? undefined : { opacity: 0, y: -8 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
          >
            <p className="text-lead text-ink">{renderMathText(question.prompt)}</p>

            <fieldset className="mt-5">
              <legend className="sr-only">Избери отговор</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {question.options.map((option, optionIndex) => {
                  const chosen = picked === optionIndex;
                  const correct = question.correct === optionIndex;
                  const showAsCorrect = answered && correct;
                  const showAsWrong = answered && chosen && !correct;

                  return (
                    <motion.button
                      key={optionIndex}
                      type="button"
                      disabled={answered}
                      onClick={() => setPicked(optionIndex)}
                      whileTap={reduced || answered ? undefined : { scale: 0.98 }}
                      aria-label={`Отговор ${LABELS[optionIndex]}`}
                      className={cn(
                        'flex items-center gap-3 rounded-lg border px-3.5 py-3 text-left transition-[border-color,background-color] duration-200',
                        !answered &&
                          'border-line bg-sunken hover:border-brand hover:bg-brand-wash',
                        showAsCorrect &&
                          'border-brand bg-brand-wash' + (isRight ? ' animate-verdict-ring' : ''),
                        showAsWrong && 'border-danger bg-danger-wash',
                        answered && !showAsCorrect && !showAsWrong && 'border-line opacity-55'
                      )}
                    >
                      <span
                        className={cn(
                          'tnum inline-flex size-6 shrink-0 items-center justify-center rounded-md border text-caption font-semibold',
                          showAsCorrect
                            ? 'border-brand bg-brand text-white'
                            : showAsWrong
                              ? 'border-danger bg-danger text-white'
                              : 'border-line-strong text-ink-muted'
                        )}
                      >
                        {showAsCorrect ? (
                          <CheckIcon weight="bold" className="size-3.5" />
                        ) : showAsWrong ? (
                          <XIcon weight="bold" className="size-3.5" />
                        ) : (
                          LABELS[optionIndex]
                        )}
                      </span>
                      <span className="text-body text-ink">{renderMathText(option)}</span>
                    </motion.button>
                  );
                })}
              </div>
            </fieldset>
          </motion.div>
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {answered && (
            <motion.div
              initial={reduced ? false : { opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={reduced ? undefined : { opacity: 0, height: 0 }}
              transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden"
            >
              <div
                role="status"
                className={cn(
                  'mt-5 rounded-lg border p-4',
                  isRight
                    ? 'border-brand-edge bg-brand-wash'
                    : 'border-warn-edge bg-warn-wash'
                )}
              >
                <p
                  className={cn(
                    'text-caption font-semibold',
                    isRight ? 'text-brand-ink' : 'text-warn'
                  )}
                >
                  {isRight ? 'Вярно.' : `Верният отговор е ${LABELS[question.correct]}.`}
                </p>
                <p className="mt-1.5 text-body text-ink-muted">
                  {renderMathText(question.explanation)}
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mt-5 flex items-center justify-between gap-3">
          <p className="text-caption text-ink-muted">
            {answered ? 'Всяка задача идва с решение.' : 'Избери отговор и виж решението.'}
          </p>
          {answered && (
            <Button variant="soft" size="sm" onClick={next}>
              {isLast ? 'Отначало' : 'Следващ въпрос'}
              <ArrowRightIcon />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default HeroExamCard;
