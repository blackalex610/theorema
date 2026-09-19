import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import {
  ArrowRightIcon,
  CameraIcon,
  ChartLineUpIcon,
  ChatCircleDotsIcon,
  DeviceMobileIcon,
  ListChecksIcon,
  QuotesIcon,
} from '@phosphor-icons/react';

import MarketingHeader from '../components/landing/MarketingHeader';
import HeroExamCard from '../components/landing/HeroExamCard';
import SiteFooter from '../components/landing/SiteFooter';
import { MathFormula, renderMathText } from '../components/MathRenderer';
import { Reveal, RevealGroup, RevealItem, useSpringHover } from '@/components/motion/Reveal';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

/* ── Content ─────────────────────────────────────────────────────────────── */

const STEPS = [
  {
    title: 'Избери клас и тема',
    body: 'Учебната програма за 5., 6. и 7. клас е разделена на теми и уроци. Тръгваш от там, където си спрял.',
  },
  {
    title: 'Реши и виж решението',
    body: 'Всяка задача се оценява веднага, с пълно решение стъпка по стъпка, а не само с верния отговор.',
  },
  {
    title: 'Върни се на слабите теми',
    body: 'Платформата следи точността ти по теми и подрежда следващата сесия около това, което още не се получава.',
  },
];

const EXAM_FACTS = [
  { label: 'Задачи в изпита', value: '23' },
  { label: 'Модула', value: '2' },
  { label: 'Минути общо', value: '150' },
  { label: 'Максимален брой точки', value: '100' },
];

const EXAM_PARTS = [
  { part: 'Модул 1', detail: 'Задачи с избираем отговор и кратък свободен отговор', minutes: '60' },
  { part: 'Модул 2', detail: 'Задачи с подробно писмено решение', minutes: '90' },
];

const TESTIMONIALS = [
  {
    quote:
      'Дробите ми бяха слабото място. След месец упражнения по темата вдигнах точността си от 40 на 85 процента.',
    name: 'Мартин Стоянов',
    role: 'ученик, 7. клас, Пловдив',
    span: 'lg:col-span-5',
  },
  {
    quote:
      'Виждам по кои теми детето ми греши, без да трябва да го разпитвам. Това само по себе си спести доста вечери.',
    name: 'Радостина Ганева',
    role: 'родител на седмокласник',
    span: 'lg:col-span-4',
  },
  {
    quote:
      'Ползвам пробните изпити за домашни. Форматът съвпада с реалния, а решенията са коректно записани.',
    name: 'Виолета Кръстева',
    role: 'учител по математика',
    span: 'lg:col-span-3',
  },
];

/* ── Page ────────────────────────────────────────────────────────────────── */

const LandingPage: React.FC = () => {
  const reduced = useReducedMotion();
  const hover = useSpringHover();

  return (
    <div className="min-h-dvh bg-paper">
      <MarketingHeader />

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-28">
        {/* The graph-paper substrate: the material students actually work on. */}
        <div
          aria-hidden="true"
          className="grid-paper-fade pointer-events-none absolute inset-0 -z-10"
        />

        <div className="mx-auto grid w-full max-w-[75rem] shell-x gap-12 lg:grid-cols-12 lg:items-center lg:gap-10">
          <div className="lg:col-span-6 xl:col-span-5">
            <motion.h1
              initial={reduced ? false : { opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className="font-display text-hero font-semibold text-ink"
            >
              Математиката за НВО,
              <span className="block text-brand-ink">разложена на стъпки.</span>
            </motion.h1>

            <motion.p
              initial={reduced ? false : { opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
              className="mt-6 max-w-lg text-lead text-ink-muted"
            >
              Пробни изпити в реалния формат, упражнения по всяка тема от програмата за
              5.-7. клас и решение към всяка задача. Без зубрене на отговори.
            </motion.p>

            <motion.div
              initial={reduced ? false : { opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.18, ease: [0.22, 1, 0.36, 1] }}
              className="mt-9 flex flex-col gap-3 sm:flex-row sm:items-center"
            >
              <motion.div {...hover} className="sm:w-auto">
                <Button asChild size="lg" className="w-full sm:w-auto">
                  <Link to="/">
                    Започни безплатно
                    <ArrowRightIcon />
                  </Link>
                </Button>
              </motion.div>
              <Button asChild size="lg" variant="outline" className="w-full sm:w-auto">
                <Link to="/">Влез в профила си</Link>
              </Button>
            </motion.div>

            <motion.p
              initial={reduced ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.26 }}
              className="mt-5 text-caption text-ink-faint"
            >
              Безплатен профил с дневен лимит. Без карта при регистрация.
            </motion.p>
          </div>

          <motion.div
            initial={reduced ? false : { opacity: 0, y: 26 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
            className="lg:col-span-6 lg:col-start-7 xl:col-span-7"
          >
            <HeroExamCard />
          </motion.div>
        </div>
        <div id="hero-sentinel" aria-hidden="true" className="h-px" />
      </section>

      {/* ── Bento: what the platform contains ───────────────────────────── */}
      <section id="vkljuchva" className="section-y scroll-mt-16">
        <div className="mx-auto w-full max-w-[75rem] shell-x">
          <Reveal className="max-w-2xl">
            <p className="text-micro font-semibold uppercase tracking-[0.1em] text-brand-ink">
              Какво включва
            </p>
            <h2 className="mt-3 font-display text-section font-semibold text-ink">
              Всичко около изпита, на едно място
            </h2>
            <p className="mt-3 text-lead text-ink-muted">
              Съдържанието следва учебната програма, а форматът следва изпита.
            </p>
          </Reveal>

          <RevealGroup className="mt-12 grid gap-4 lg:grid-cols-12">
            {/* Tall anchor tile */}
            <RevealItem className="lg:col-span-7 lg:row-span-2">
              <article className="flex h-full flex-col justify-between gap-8 rounded-2xl border border-line bg-surface p-6 shadow-lift-1 sm:p-8">
                <div>
                  <Badge variant="brand">
                    <ListChecksIcon weight="fill" />
                    Пробни изпити
                  </Badge>
                  <h3 className="mt-4 font-display text-title font-semibold text-ink">
                    Пълен изпит в реалния формат
                  </h3>
                  <p className="mt-2 max-w-md text-body text-ink-muted">
                    Двата модула, броят задачи и разпределението на точките съвпадат с
                    изпитния лист. Оценяването е по същата скала.
                  </p>
                </div>

                <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
                  {EXAM_FACTS.map((fact) => (
                    <div key={fact.label} className="bg-surface p-4">
                      <dt className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
                        {fact.label}
                      </dt>
                      <dd className="tnum mt-1.5 text-[1.75rem] font-semibold leading-none text-ink">
                        {fact.value}
                      </dd>
                    </div>
                  ))}
                </dl>
              </article>
            </RevealItem>

            {/* Worked solution tile: the math itself does the talking */}
            <RevealItem className="lg:col-span-5">
              <article className="flex h-full flex-col gap-4 rounded-2xl border border-line bg-surface p-6 shadow-lift-1">
                <div>
                  <Badge variant="neutral">
                    <ChatCircleDotsIcon weight="fill" />
                    Решения
                  </Badge>
                  <h3 className="mt-4 font-display text-title font-semibold text-ink">
                    Стъпка по стъпка, не само отговор
                  </h3>
                </div>
                <ol className="space-y-2 rounded-xl border border-line bg-sunken p-4">
                  {[
                    '2(x + 3) = 5x - 9',
                    '2x + 6 = 5x - 9',
                    '15 = 3x',
                    'x = 5',
                  ].map((line, i) => (
                    <li key={line} className="flex items-baseline gap-3">
                      <span className="tnum text-micro text-ink-faint">{i + 1}</span>
                      <MathFormula formula={line} className="text-body text-ink" />
                    </li>
                  ))}
                </ol>
              </article>
            </RevealItem>

            {/* Progress tile: a small, real visualisation */}
            <RevealItem className="lg:col-span-5">
              <article className="flex h-full flex-col gap-4 rounded-2xl border border-line bg-surface p-6 shadow-lift-1">
                <div>
                  <Badge variant="neutral">
                    <ChartLineUpIcon weight="fill" />
                    Прогрес
                  </Badge>
                  <h3 className="mt-4 font-display text-title font-semibold text-ink">
                    Точност по теми, а не обща оценка
                  </h3>
                </div>
                <ul className="space-y-3">
                  {[
                    { topic: 'Рационални числа', value: 88 },
                    { topic: 'Линейни уравнения', value: 72 },
                    { topic: 'Лице и обем', value: 46 },
                  ].map((row) => (
                    <li key={row.topic} className="space-y-1.5">
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="text-caption text-ink-muted">{row.topic}</span>
                        <span className="tnum text-caption font-semibold text-ink">
                          {row.value}%
                        </span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
                        <motion.div
                          initial={reduced ? false : { width: 0 }}
                          whileInView={{ width: `${row.value}%` }}
                          viewport={{ once: true }}
                          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
                          className={cn(
                            'h-full rounded-full',
                            row.value < 50 ? 'bg-warn' : 'bg-brand'
                          )}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              </article>
            </RevealItem>

            {/* Photo tile */}
            <RevealItem className="lg:col-span-4">
              <article className="flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-surface shadow-lift-1">
                <img
                  src="https://picsum.photos/seed/maths-notebook-squared-paper-pencil/800/500"
                  alt="Тетрадка на квадратчета с решена задача и молив върху нея"
                  width={800}
                  height={500}
                  loading="lazy"
                  className="h-44 w-full object-cover"
                />
                <div className="p-6">
                  <Badge variant="neutral">
                    <CameraIcon weight="fill" />
                    От учебника
                  </Badge>
                  <h3 className="mt-4 font-display text-title font-semibold text-ink">
                    Снимай задача и я реши тук
                  </h3>
                  <p className="mt-2 text-body text-ink-muted">
                    Условието се разчита от снимката и влиза в платформата като обикновена задача.
                  </p>
                </div>
              </article>
            </RevealItem>

            <RevealItem className="lg:col-span-4">
              <article className="flex h-full flex-col gap-3 rounded-2xl border border-line bg-surface p-6 shadow-lift-1">
                <Badge variant="neutral">Теория</Badge>
                <h3 className="font-display text-title font-semibold text-ink">
                  Уроци по програмата за 5.-7. клас
                </h3>
                <p className="text-body text-ink-muted">
                  Всяка тема започва с кратко обяснение и примери, преди да се стигне до задачите.
                </p>
                <p className="mt-auto text-body text-ink">
                  {renderMathText(
                    'Например: лице на трапец $S = \\frac{(a + b) \\cdot h}{2}$'
                  )}
                </p>
              </article>
            </RevealItem>

            <RevealItem className="lg:col-span-4">
              <article className="flex h-full flex-col gap-3 rounded-2xl border border-line bg-surface p-6 shadow-lift-1">
                <Badge variant="neutral">
                  <DeviceMobileIcon weight="fill" />
                  Телефон
                </Badge>
                <h3 className="font-display text-title font-semibold text-ink">
                  Сдвояване с код
                </h3>
                <p className="text-body text-ink-muted">
                  Отваряш камерата на телефона с четирицифрен код и снимката се появява на
                  компютъра веднага.
                </p>
                <p className="tnum mt-auto text-[1.75rem] font-semibold tracking-[0.2em] text-brand-ink">
                  4821
                </p>
              </article>
            </RevealItem>
          </RevealGroup>
        </div>
      </section>

      {/* ── How it works: a real three-step sequence, so it is numbered ─── */}
      <section id="kak-raboti" className="section-y scroll-mt-16 border-y border-line bg-surface">
        <div className="mx-auto w-full max-w-[75rem] shell-x">
          <Reveal className="max-w-2xl">
            <h2 className="font-display text-section font-semibold text-ink">Как работи</h2>
            <p className="mt-3 text-lead text-ink-muted">
              Един и същ цикъл всеки път, докато темата спре да е слаба.
            </p>
          </Reveal>

          <RevealGroup className="mt-12 grid gap-8 lg:grid-cols-3 lg:gap-12" step={0.08}>
            {STEPS.map((step, index) => (
              <RevealItem key={step.title}>
                <div className="relative flex flex-col gap-3 lg:pt-8">
                  {/* The rule that ties the sequence together on wide screens */}
                  <span
                    aria-hidden="true"
                    className="absolute inset-x-0 top-0 hidden h-px bg-line lg:block"
                  />
                  <span
                    aria-hidden="true"
                    className="absolute left-0 top-0 hidden h-px w-10 bg-brand lg:block"
                  />
                  <span className="tnum text-caption font-semibold text-brand-ink">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <h3 className="font-display text-title font-semibold text-ink">{step.title}</h3>
                  <p className="text-body text-ink-muted">{step.body}</p>
                </div>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* ── Exam format ─────────────────────────────────────────────────── */}
      <section id="format" className="section-y scroll-mt-16">
        <div className="mx-auto grid w-full max-w-[75rem] shell-x gap-12 lg:grid-cols-12 lg:items-center">
          <Reveal className="lg:col-span-5">
            <img
              src="https://picsum.photos/seed/classroom-desk-exam-paper-morning-light/1000/1100"
              alt="Ученическа маса със свитък изпитни листове и молив под утринна светлина"
              width={1000}
              height={1100}
              loading="lazy"
              className="aspect-[10/11] w-full rounded-2xl border border-line object-cover shadow-lift-2"
            />
          </Reveal>

          <Reveal className="lg:col-span-6 lg:col-start-7" delay={0.08}>
            <p className="text-micro font-semibold uppercase tracking-[0.1em] text-brand-ink">
              Изпитният формат
            </p>
            <h2 className="mt-3 font-display text-section font-semibold text-ink">
              Знай точно какво те чака в залата
            </h2>
            <p className="mt-3 text-lead text-ink-muted">
              Пробните изпити повтарят структурата на НВО по математика за 7. клас, включително
              разпределението на времето между двата модула.
            </p>

            <ul className="mt-8 divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
              {EXAM_PARTS.map((part) => (
                <li key={part.part} className="flex items-start justify-between gap-4 p-5">
                  <div>
                    <p className="text-body font-semibold text-ink">{part.part}</p>
                    <p className="mt-0.5 text-caption text-ink-muted">{part.detail}</p>
                  </div>
                  <span className="tnum shrink-0 text-body font-semibold text-ink">
                    {part.minutes} мин
                  </span>
                </li>
              ))}
            </ul>

            <Button asChild variant="soft" className="mt-6">
              <Link to="/">
                Реши пробен изпит
                <ArrowRightIcon />
              </Link>
            </Button>
          </Reveal>
        </div>
      </section>

      {/* ── Testimonials ────────────────────────────────────────────────── */}
      <section id="mnenia" className="section-y scroll-mt-16 border-t border-line bg-surface">
        <div className="mx-auto w-full max-w-[75rem] shell-x">
          {/* These three quotes are not from verified, identified users. A
              named testimonial with a specific outcome claim ("вдигнах
              точността си от 40 на 85") is a consumer-law problem if it isn't
              real, so it is labelled as illustrative until it can be replaced
              with a quote from an actual named student, parent or teacher who
              has agreed to it. Remove the note at the same time as the swap. */}
          <Reveal className="max-w-2xl">
            <h2 className="font-display text-section font-semibold text-ink">
              Какво казват хората, които я ползват
            </h2>
            <p className="mt-3 text-caption text-ink-muted">
              Примерни отзиви — показват типични сценарии на употреба, а не изказвания на
              конкретни потребители.
            </p>
          </Reveal>

          <RevealGroup className="mt-12 grid gap-4 lg:grid-cols-12">
            {TESTIMONIALS.map((item) => (
              <RevealItem key={item.name} className={item.span}>
                <figure className="flex h-full flex-col justify-between gap-6 rounded-2xl border border-line bg-paper p-6">
                  <QuotesIcon
                    weight="fill"
                    aria-hidden="true"
                    className="size-6 text-brand-edge"
                  />
                  <blockquote className="text-lead text-ink">{item.quote}</blockquote>
                  <figcaption className="border-t border-line pt-4">
                    <p className="text-body font-semibold text-ink">{item.name}</p>
                    <p className="text-caption text-ink-muted">{item.role}</p>
                  </figcaption>
                </figure>
              </RevealItem>
            ))}
          </RevealGroup>
        </div>
      </section>

      {/* ── Closing call to action ──────────────────────────────────────── */}
      <section className="section-y">
        <div className="mx-auto w-full max-w-[75rem] shell-x">
          <Reveal>
            <div className="relative overflow-hidden rounded-2xl border border-brand-edge bg-brand-wash px-6 py-14 sm:px-12">
              <div aria-hidden="true" className="grid-paper absolute inset-0 -z-10 opacity-70" />
              <div className="max-w-xl">
                <h2 className="font-display text-section font-semibold text-ink">
                  Започни от темата, която не се получава
                </h2>
                <p className="mt-3 text-lead text-ink-muted">
                  Създаваш профил за секунди и решаваш първите задачи веднага.
                </p>
                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <motion.div {...hover}>
                    <Button asChild size="lg" className="w-full sm:w-auto">
                      <Link to="/">
                        Създай профил
                        <ArrowRightIcon />
                      </Link>
                    </Button>
                  </motion.div>
                  <Button asChild size="lg" variant="outline" className="w-full sm:w-auto">
                    <Link to="/">Влез</Link>
                  </Button>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
};

export default LandingPage;
