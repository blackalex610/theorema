import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import {
  ArrowRightIcon,
  BookOpenIcon,
  ChartLineUpIcon,
  FireIcon,
  PencilSimpleLineIcon,
  SparkleIcon,
  TargetIcon,
} from '@phosphor-icons/react';

import AppNavbar from '../components/AppNavbar';
import BadgeShelf from '../components/BadgeShelf';
import {
  getDailyMissions,
  getDashboardStats,
  getRecommendations,
  getXpSummary,
  recordActivity,
  type DailyMission,
  type DashboardStats,
  type ProgressRecommendations,
  type XpSummary,
} from '../services/progress';
import { useXp } from '../context/XpContext';
import { useAuth } from '../context/AuthContext';
import { useIsDevMode } from '../context/DeveloperModeContext';
import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageShell,
  SectionHeading,
} from '../components/app/PageShell';
import { Reveal, RevealGroup, RevealItem, useSpringHover } from '@/components/motion/Reveal';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

/* ── Cache ───────────────────────────────────────────────────────────────── */

const DASHBOARD_CACHE_KEY = 'dashboard_cache_v1';
const CACHE_FRESH_MS = 5 * 60 * 1000;

interface DashboardCache {
  stats: DashboardStats;
  recommendations: ProgressRecommendations;
  xpSummary: XpSummary;
  missions: DailyMission[];
  savedAt: number;
}

function readCache(): DashboardCache | null {
  try {
    const raw = localStorage.getItem(DASHBOARD_CACHE_KEY);
    return raw ? (JSON.parse(raw) as DashboardCache) : null;
  } catch {
    return null;
  }
}

function writeCache(data: Omit<DashboardCache, 'savedAt'>) {
  try {
    localStorage.setItem(DASHBOARD_CACHE_KEY, JSON.stringify({ ...data, savedAt: Date.now() }));
  } catch {
    /* storage full, not worth failing the render over */
  }
}

/* ── Page ────────────────────────────────────────────────────────────────── */

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const isDevMode = useIsDevMode();
  const { refreshXp } = useXp();
  const reduced = useReducedMotion();
  const hover = useSpringHover();

  const { user } = useAuth();
  const firstName = user?.name?.split(' ')[0] ?? 'Ученик';

  const [stats, setStats] = useState<DashboardStats | null>(() => readCache()?.stats ?? null);
  const [recommendations, setRecommendations] = useState<ProgressRecommendations | null>(
    () => readCache()?.recommendations ?? null
  );
  const [xpSummary, setXpSummary] = useState<XpSummary | null>(() => readCache()?.xpSummary ?? null);
  const [missions, setMissions] = useState<DailyMission[]>(() => readCache()?.missions ?? []);
  const [loading, setLoading] = useState(() => readCache() === null);
  const [loadError, setLoadError] = useState('');

  const load = useCallback(
    async (force = false) => {
      // Guests now hold a real backend account, so every call below succeeds
      // for them exactly as it does for a signed-in user — no short-circuit.
      const cached = readCache();
      if (!force && cached && Date.now() - cached.savedAt < CACHE_FRESH_MS) {
        setLoading(false);
        return;
      }
      if (!cached) setLoading(true);
      setLoadError('');

      try {
        const [s, r, x, m] = await Promise.allSettled([
          getDashboardStats(),
          getRecommendations(),
          recordActivity(),
          getDailyMissions(),
        ]);

        const nextStats = s.status === 'fulfilled' ? s.value : null;
        const nextRecs = r.status === 'fulfilled' ? r.value : null;
        let nextXp = x.status === 'fulfilled' ? x.value : null;
        if (!nextXp) nextXp = await getXpSummary().catch(() => null);
        const nextMissions = m.status === 'fulfilled' ? m.value : null;

        if (nextStats) setStats(nextStats);
        if (nextRecs) setRecommendations(nextRecs);
        if (nextXp) setXpSummary(nextXp);
        if (nextMissions) setMissions(nextMissions);

        if (nextStats && nextRecs && nextXp && nextMissions) {
          writeCache({
            stats: nextStats,
            recommendations: nextRecs,
            xpSummary: nextXp,
            missions: nextMissions,
          });
        }

        if (!nextStats && !nextRecs) {
          setLoadError('Връзката със сървъра не се осъществи. Провери дали backend работи.');
        }
        refreshXp();
      } finally {
        setLoading(false);
      }
    },
    [refreshXp]
  );

  useEffect(() => {
    void load();
  }, [load]);

  const accuracy = stats?.accuracy_percentage ?? 0;
  const topicsTotal = stats?.total_topics_available ?? 0;
  const topicsDone = stats?.topics_completed ?? 0;
  const lessonsTotal = stats?.total_lessons_available ?? 0;
  const lessonsDone = stats?.lessons_completed ?? 0;
  const weakTopics = recommendations?.weak_topics ?? [];

  return (
    <>
      <AppNavbar showBack={false} />

      <PageShell>
        <PageHeader
          title={`Здравей, ${firstName}`}
          description={
            recommendations?.encouragement_message ||
            'Продължи оттам, докъдето стигна миналия път.'
          }
          actions={
            <>
              <motion.div {...hover}>
                <Button onClick={() => navigate('/nvo/practice')}>
                  <SparkleIcon weight="fill" />
                  Пробен НВО изпит
                </Button>
              </motion.div>
              <Button variant="outline" onClick={() => navigate('/grades')}>
                <PencilSimpleLineIcon />
                Упражнения
              </Button>
            </>
          }
        />

        {loadError && (
          <div className="mb-6">
            <ErrorState description={loadError} onRetry={() => void load(true)} />
          </div>
        )}

        {loading ? (
          <DashboardSkeleton />
        ) : (
          <div className="space-y-10">
            {/* ── Level plus the four measurements ───────────────────────── */}
            <RevealGroup className="grid gap-4 lg:grid-cols-12">
              <RevealItem className="lg:col-span-4">
                <LevelCard xp={xpSummary} />
              </RevealItem>

              <RevealItem className="lg:col-span-8">
                <div className="grid h-full gap-4 sm:grid-cols-2">
                  <MetricCard
                    label="Средна точност"
                    value={`${accuracy.toFixed(0)}%`}
                    progress={accuracy}
                    hint={`${stats?.total_exercises_attempted ?? 0} опита общо`}
                    tone={accuracy >= 80 ? 'brand' : accuracy >= 50 ? 'warn' : 'danger'}
                    onClick={() => navigate('/progress')}
                    icon={<TargetIcon weight="fill" />}
                  />
                  <MetricCard
                    label="Решени задачи"
                    value={String(stats?.total_exercises_completed ?? 0)}
                    hint="от началото на профила"
                    onClick={() => navigate('/grades')}
                    icon={<PencilSimpleLineIcon weight="fill" />}
                  />
                  <MetricCard
                    label="Завършени теми"
                    value={String(topicsDone)}
                    suffix={topicsTotal ? `/ ${topicsTotal}` : undefined}
                    progress={topicsTotal ? (topicsDone / topicsTotal) * 100 : 0}
                    onClick={() => navigate('/progress')}
                    icon={<ChartLineUpIcon weight="fill" />}
                  />
                  <MetricCard
                    label="Завършени уроци"
                    value={String(lessonsDone)}
                    suffix={lessonsTotal ? `/ ${lessonsTotal}` : undefined}
                    progress={lessonsTotal ? (lessonsDone / lessonsTotal) * 100 : 0}
                    onClick={() => navigate('/learn/grades')}
                    icon={<BookOpenIcon weight="fill" />}
                  />
                </div>
              </RevealItem>
            </RevealGroup>

            {/* ── Where the effort should go next ────────────────────────── */}
            <Reveal>
              <SectionHeading
                id="focus"
                title="Теми за упражняване"
                description="Подредени по точност, най-слабата отгоре."
                action={
                  weakTopics.length > 0 ? (
                    <Button variant="ghost" size="sm" onClick={() => navigate('/progress')}>
                      Целият прогрес
                      <ArrowRightIcon />
                    </Button>
                  ) : undefined
                }
              />

              {weakTopics.length === 0 ? (
                <EmptyState
                  icon={<TargetIcon weight="duotone" />}
                  title="Още няма достатъчно данни"
                  description="Реши няколко задачи и тук ще се появят темите, които се получават най-трудно."
                  action={
                    <Button onClick={() => navigate('/grades')}>
                      Към упражненията
                      <ArrowRightIcon />
                    </Button>
                  }
                />
              ) : (
                <ul className="grid gap-3 sm:grid-cols-2">
                  {weakTopics.map((topic) => (
                    <li key={topic.topic_id}>
                      <button
                        type="button"
                        onClick={() => navigate(`/topics/${topic.topic_id}/lessons`)}
                        className="flex w-full items-start justify-between gap-4 rounded-xl border border-line bg-surface p-5 text-left shadow-lift-1 transition-[border-color,box-shadow] duration-200 hover:border-brand hover:shadow-lift-2"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-body font-semibold text-ink">
                            {topic.title}
                          </span>
                          <span className="mt-0.5 block text-caption text-ink-muted">
                            {topic.reason}
                          </span>
                          <span className="mt-3 block h-1.5 w-full overflow-hidden rounded-full bg-sunken">
                            <motion.span
                              initial={reduced ? false : { width: 0 }}
                              animate={{ width: `${topic.accuracy}%` }}
                              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
                              className={cn(
                                'block h-full rounded-full',
                                topic.accuracy < 50 ? 'bg-danger' : 'bg-warn'
                              )}
                            />
                          </span>
                        </span>
                        <span className="tnum shrink-0 text-title font-semibold text-ink">
                          {topic.accuracy.toFixed(0)}%
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </Reveal>

            {/* ── Daily missions ─────────────────────────────────────────── */}
            <Reveal>
              <SectionHeading
                id="missions"
                title="Задачи за днес"
                description="Кратки сесии, съобразени с това, което вече си решавал."
              />

              {missions.length === 0 ? (
                <EmptyState
                  icon={<FireIcon weight="duotone" />}
                  title="Няма активни задачи за днес"
                  description="Започни свободна сесия по тема и задачите за утре ще се подредят около нея."
                  action={
                    <Button variant="outline" onClick={() => navigate('/grades')}>
                      Избери тема
                    </Button>
                  }
                />
              ) : (
                <ul className="grid gap-3 sm:grid-cols-2">
                  {missions.map((mission) => (
                    <li key={mission.id}>
                      <MissionCard mission={mission} onStart={() => navigate(mission.route)} />
                    </li>
                  ))}
                </ul>
              )}
            </Reveal>

            {isDevMode && (
              <Reveal>
                <BadgeShelf />
              </Reveal>
            )}
          </div>
        )}
      </PageShell>
    </>
  );
};

/* ── Pieces ──────────────────────────────────────────────────────────────── */

const LevelCard: React.FC<{ xp: XpSummary | null }> = ({ xp }) => {
  const level = xp?.level ?? 1;
  const intoLevel = xp?.xp_into_level ?? 0;
  const toNext = xp?.xp_to_next_level ?? 100;
  const percent = xp?.progress_percentage ?? 0;
  const span = Math.max(1, intoLevel + toNext);

  return (
    <section className="flex h-full flex-col justify-between gap-6 rounded-xl border border-line bg-surface p-6 shadow-lift-1">
      <div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
            Ниво
          </span>
          {(xp?.streak_days ?? 0) > 1 && (
            <Badge variant="warn" numeric>
              <FireIcon weight="fill" />
              {xp?.streak_days} дни поред
            </Badge>
          )}
        </div>
        <p className="tnum mt-2 text-[3rem] font-semibold leading-none text-ink">{level}</p>
        <p className="mt-2 text-caption text-ink-muted">
          Общо <span className="tnum font-semibold text-ink">{xp?.total_xp ?? 0}</span> XP, от тях{' '}
          <span className="tnum font-semibold text-brand-ink">{xp?.today_xp ?? 0}</span> днес.
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-2">
          <span className="tnum text-caption text-ink-muted">
            {intoLevel} / {span} XP
          </span>
          <span className="tnum text-caption text-ink-muted">
            остават {toNext} до ниво {level + 1}
          </span>
        </div>
        <Progress value={percent} aria-label={`Прогрес към ниво ${level + 1}`} />
      </div>
    </section>
  );
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  suffix?: string;
  hint?: string;
  progress?: number;
  tone?: 'default' | 'brand' | 'warn' | 'danger';
  icon?: React.ReactNode;
  onClick?: () => void;
}> = ({ label, value, suffix, hint, progress, tone = 'default', icon, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className="flex flex-col justify-between gap-4 rounded-xl border border-line bg-surface p-5 text-left shadow-lift-1 transition-[border-color,box-shadow] duration-200 hover:border-brand hover:shadow-lift-2"
  >
    <span className="flex items-center justify-between gap-2">
      <span className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
        {label}
      </span>
      <span aria-hidden="true" className="text-ink-faint [&_svg]:size-4">
        {icon}
      </span>
    </span>

    <span>
      <span className="flex items-baseline gap-1.5">
        <span
          className={cn(
            'tnum text-[2rem] font-semibold leading-none',
            tone === 'brand' && 'text-brand-ink',
            tone === 'warn' && 'text-warn',
            tone === 'danger' && 'text-danger',
            tone === 'default' && 'text-ink'
          )}
        >
          {value}
        </span>
        {suffix && <span className="tnum text-body text-ink-faint">{suffix}</span>}
      </span>
      {typeof progress === 'number' && (
        <span className="mt-3 block h-1.5 w-full overflow-hidden rounded-full bg-sunken">
          <span
            className={cn(
              'block h-full rounded-full transition-[width] duration-700',
              tone === 'danger' ? 'bg-danger' : tone === 'warn' ? 'bg-warn' : 'bg-brand'
            )}
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </span>
      )}
      {hint && <span className="mt-2 block text-caption text-ink-muted">{hint}</span>}
    </span>
  </button>
);

const DIFFICULTY_VARIANT: Record<string, 'brand' | 'warn' | 'danger' | 'neutral'> = {
  Лесно: 'brand',
  Средно: 'warn',
  Трудно: 'danger',
};

const MissionCard: React.FC<{ mission: DailyMission; onStart: () => void }> = ({
  mission,
  onStart,
}) => {
  const target = mission.target_count ?? 0;
  const done = mission.completed_count ?? 0;

  return (
    <article className="flex h-full flex-col gap-4 rounded-xl border border-line bg-surface p-5 shadow-lift-1">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-body font-semibold text-ink">{mission.title}</h3>
          <p className="mt-0.5 text-caption text-ink-muted">{mission.description}</p>
        </div>
        <Badge variant={DIFFICULTY_VARIANT[mission.difficulty] ?? 'neutral'}>
          {mission.difficulty}
        </Badge>
      </header>

      <dl className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-ink-muted">
        <div className="flex items-center gap-1.5">
          <dt className="sr-only">Времетраене</dt>
          <dd className="tnum">{mission.duration}</dd>
        </div>
        <div className="flex items-center gap-1.5">
          <dt className="sr-only">Награда</dt>
          <dd className="tnum">
            +{mission.xp_base} XP
            {mission.xp_bonus > 0 && (
              <span className="text-brand-ink"> и +{mission.xp_bonus} бонус</span>
            )}
          </dd>
        </div>
      </dl>

      {target > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between">
            <span className="text-caption text-ink-muted">
              {mission.is_completed ? 'Завършена' : 'Прогрес'}
            </span>
            <span className="tnum text-caption font-semibold text-ink">
              {done} / {target}
            </span>
          </div>
          <Progress value={Math.min(100, (done / target) * 100)} />
        </div>
      )}

      <Button
        variant={mission.is_completed ? 'outline' : 'soft'}
        className="mt-auto w-full"
        onClick={onStart}
      >
        {mission.is_completed ? 'Реши отново' : 'Започни'}
        <ArrowRightIcon />
      </Button>
    </article>
  );
};

const DashboardSkeleton: React.FC = () => (
  <div className="space-y-10" role="status" aria-live="polite">
    <span className="sr-only">Таблото се зарежда</span>
    <div className="grid gap-4 lg:grid-cols-12">
      <Skeleton className="h-56 lg:col-span-4" />
      <div className="grid gap-4 sm:grid-cols-2 lg:col-span-8">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-[6.5rem]" />
        ))}
      </div>
    </div>
    <div className="space-y-4">
      <Skeleton className="h-6 w-48" />
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
    </div>
  </div>
);

export default DashboardPage;
