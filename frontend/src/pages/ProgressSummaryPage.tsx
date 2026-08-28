import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRightIcon, TargetIcon } from '@phosphor-icons/react';

import AppNavbar from '../components/AppNavbar';
import ActivityFeed from '../components/ActivityFeed';
import BadgeShelf from '../components/BadgeShelf';
import {
  getDashboardStats,
  getRecommendations,
  getTopicProgress,
  type DashboardStats,
  type ProgressRecommendations,
  type TopicProgress,
} from '../services/progress';
import { useIsDevMode } from '../context/DeveloperModeContext';
import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageShell,
  SectionHeading,
  StatTile,
} from '../components/app/PageShell';
import { Reveal, RevealGroup, RevealItem } from '@/components/motion/Reveal';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';

/* Sample data behind the developer-only toggle, used for screenshots on an
   empty account. It is never shown to a signed-in student by default. */
const DEMO_STATS: DashboardStats = {
  total_exercises_completed: 148,
  total_exercises_attempted: 196,
  accuracy_percentage: 75.5,
  topics_started: 10,
  topics_completed: 6,
  total_topics_available: 12,
  lessons_started: 29,
  lessons_completed: 21,
  total_lessons_available: 36,
  recent_activity: [],
};

const DEMO_RECOMMENDATIONS: ProgressRecommendations = {
  weak_topics: [
    { topic_id: 101, title: 'Рационални изрази', accuracy: 58, reason: 'Точност 58% при цел 60%' },
    { topic_id: 102, title: 'Геометрични доказателства', accuracy: 54, reason: 'Точност 54% при цел 60%' },
  ],
  recommended_lessons: [
    {
      lesson_id: 701,
      topic_id: 101,
      lesson_title: 'Опростяване на рационални изрази',
      topic_title: 'Рационални изрази',
      reason: 'Практика за повишаване на точността',
    },
    {
      lesson_id: 702,
      topic_id: 102,
      lesson_title: 'Доказване на еднаквост на триъгълници',
      topic_title: 'Геометрични доказателства',
      reason: 'Практика за повишаване на точността',
    },
  ],
  encouragement_message:
    'Стабилен напредък. Няколко целенасочени упражнения ще вдигнат точността над 80 процента.',
};

const DEMO_TOPICS: TopicProgress[] = [
  {
    topic_id: 1,
    title: 'Алгебраични изрази',
    description: 'Преобразуване и пресмятане',
    grade_number: 5,
    progress_percentage: 82,
    accuracy: 84,
    completed_exercises: 41,
    total_exercises: 50,
    lessons_completed: 6,
    total_lessons: 7,
    needs_practice: false,
  },
  {
    topic_id: 2,
    title: 'Линейни уравнения',
    description: 'Уравнения с една променлива',
    grade_number: 6,
    progress_percentage: 76,
    accuracy: 72,
    completed_exercises: 38,
    total_exercises: 50,
    lessons_completed: 5,
    total_lessons: 7,
    needs_practice: false,
  },
];

const ProgressSummaryPage: React.FC = () => {
  const navigate = useNavigate();
  const isDevMode = useIsDevMode();
  const reduced = useReducedMotion();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recommendations, setRecommendations] = useState<ProgressRecommendations | null>(null);
  const [topics, setTopics] = useState<TopicProgress[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [demoMode, setDemoMode] = useState(false);

  const load = useCallback(async () => {
    if (demoMode) {
      setStats(DEMO_STATS);
      setRecommendations(DEMO_RECOMMENDATIONS);
      setTopics(DEMO_TOPICS);
      setLoading(false);
      return;
    }

    setLoading(true);
    setLoadError('');
    try {
      const [statsData, recsData, topicData] = await Promise.all([
        getDashboardStats(),
        getRecommendations(),
        getTopicProgress(),
      ]);
      setStats(statsData);
      setRecommendations(recsData);
      setTopics(topicData);
    } catch {
      setLoadError('Прогресът не се зареди. Провери връзката и опитай пак.');
    } finally {
      setLoading(false);
    }
  }, [demoMode]);

  useEffect(() => {
    void load();
  }, [load]);

  const byGrade = useMemo(() => {
    const map = new Map<number, { completed: number; total: number; accuracySum: number; count: number }>();
    topics.forEach((topic) => {
      const current = map.get(topic.grade_number) ?? {
        completed: 0,
        total: 0,
        accuracySum: 0,
        count: 0,
      };
      current.completed += topic.completed_exercises;
      current.total += topic.total_exercises;
      current.accuracySum += topic.accuracy;
      current.count += 1;
      map.set(topic.grade_number, current);
    });
    return Array.from(map.entries())
      .map(([grade, values]) => ({
        grade,
        progress: values.total > 0 ? (values.completed / values.total) * 100 : 0,
        accuracy: values.count > 0 ? values.accuracySum / values.count : 0,
      }))
      .sort((a, b) => a.grade - b.grade);
  }, [topics]);

  const accuracy = stats?.accuracy_percentage ?? 0;
  const sortedTopics = useMemo(
    () => [...topics].sort((a, b) => a.accuracy - b.accuracy),
    [topics]
  );

  return (
    <>
      <AppNavbar backTo="/dashboard" backLabel="Обратно към таблото" />

      <PageShell>
        <PageHeader
          title="Твоят прогрес"
          description="Точност по теми, завършени уроци и какво си струва да се повтори."
          crumbs={[{ label: 'Табло', to: '/dashboard' }, { label: 'Прогрес' }]}
          actions={
            isDevMode ? (
              <Button variant="outline" size="sm" onClick={() => setDemoMode((v) => !v)}>
                {demoMode ? 'Реални данни' : 'Демо данни'}
              </Button>
            ) : undefined
          }
        />

        {demoMode && (
          <div className="mb-6">
            <Badge variant="warn">Показани са демонстрационни данни</Badge>
          </div>
        )}

        {loadError && (
          <div className="mb-6">
            <ErrorState description={loadError} onRetry={() => void load()} />
          </div>
        )}

        {loading ? (
          <ProgressSkeleton />
        ) : (
          <div className="space-y-10">
            <RevealGroup className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <RevealItem>
                <StatTile
                  label="Решени задачи"
                  value={stats?.total_exercises_completed ?? 0}
                  hint={`от ${stats?.total_exercises_attempted ?? 0} опита`}
                  onClick={() => navigate('/grades')}
                />
              </RevealItem>
              <RevealItem>
                <StatTile
                  label="Средна точност"
                  value={`${accuracy.toFixed(0)}%`}
                  tone={accuracy >= 80 ? 'brand' : accuracy >= 60 ? 'default' : 'warn'}
                  hint="по всички решени задачи"
                />
              </RevealItem>
              <RevealItem>
                <StatTile
                  label="Завършени теми"
                  value={stats?.topics_completed ?? 0}
                  suffix={`/ ${stats?.total_topics_available ?? 0}`}
                />
              </RevealItem>
              <RevealItem>
                <StatTile
                  label="Завършени уроци"
                  value={stats?.lessons_completed ?? 0}
                  suffix={`/ ${stats?.total_lessons_available ?? 0}`}
                  onClick={() => navigate('/learn/grades')}
                />
              </RevealItem>
            </RevealGroup>

            <Reveal>
              <Tabs defaultValue="topics">
                <TabsList>
                  <TabsTrigger value="topics">По теми</TabsTrigger>
                  <TabsTrigger value="grades">По клас</TabsTrigger>
                  <TabsTrigger value="history">История</TabsTrigger>
                </TabsList>

                <TabsContent value="topics">
                  {sortedTopics.length === 0 ? (
                    <EmptyState
                      icon={<TargetIcon weight="duotone" />}
                      title="Още няма решени задачи"
                      description="Щом решиш първите задачи, тук ще се появи точността ти по всяка тема."
                      action={
                        <Button onClick={() => navigate('/grades')}>
                          Към упражненията
                          <ArrowRightIcon />
                        </Button>
                      }
                    />
                  ) : (
                    <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
                      {sortedTopics.map((topic) => (
                        <li key={topic.topic_id}>
                          <button
                            type="button"
                            onClick={() => navigate(`/topics/${topic.topic_id}/lessons`)}
                            className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-sunken"
                          >
                            <span className="min-w-0 flex-1">
                              <span className="flex items-center gap-2">
                                <span className="truncate text-body font-semibold text-ink">
                                  {topic.title}
                                </span>
                                <Badge variant="neutral" numeric>
                                  {topic.grade_number}. клас
                                </Badge>
                                {topic.needs_practice && <Badge variant="warn">за повторение</Badge>}
                              </span>
                              <span className="tnum mt-1 block text-caption text-ink-muted">
                                {topic.completed_exercises} от {topic.total_exercises} задачи,{' '}
                                {topic.lessons_completed} от {topic.total_lessons} урока
                              </span>
                            </span>

                            <span className="hidden w-40 shrink-0 sm:block">
                              <span className="block h-1.5 overflow-hidden rounded-full bg-sunken">
                                <motion.span
                                  initial={reduced ? false : { width: 0 }}
                                  whileInView={{ width: `${topic.accuracy}%` }}
                                  viewport={{ once: true }}
                                  transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
                                  className={cn(
                                    'block h-full rounded-full',
                                    topic.accuracy >= 80
                                      ? 'bg-brand'
                                      : topic.accuracy >= 60
                                        ? 'bg-warn'
                                        : 'bg-danger'
                                  )}
                                />
                              </span>
                            </span>

                            <span
                              className={cn(
                                'tnum w-14 shrink-0 text-right text-title font-semibold',
                                topic.accuracy >= 80
                                  ? 'text-brand-ink'
                                  : topic.accuracy >= 60
                                    ? 'text-ink'
                                    : 'text-danger'
                              )}
                            >
                              {topic.accuracy.toFixed(0)}%
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </TabsContent>

                <TabsContent value="grades">
                  {byGrade.length === 0 ? (
                    <EmptyState
                      title="Няма данни по класове"
                      description="Данните се появяват, след като решиш задачи поне по една тема."
                    />
                  ) : (
                    <ul className="grid gap-4 sm:grid-cols-3">
                      {byGrade.map((row) => (
                        <li
                          key={row.grade}
                          className="space-y-3 rounded-xl border border-line bg-surface p-5 shadow-lift-1"
                        >
                          <div className="flex items-baseline justify-between">
                            <h3 className="text-body font-semibold text-ink">{row.grade}. клас</h3>
                            <span className="tnum text-caption text-ink-muted">
                              {row.accuracy.toFixed(0)}% точност
                            </span>
                          </div>
                          <Progress
                            value={row.progress}
                            aria-label={`Изминат материал за ${row.grade}. клас`}
                          />
                          <p className="tnum text-caption text-ink-muted">
                            {row.progress.toFixed(0)}% от задачите решени
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </TabsContent>

                <TabsContent value="history">
                  <ActivityFeed />
                </TabsContent>
              </Tabs>
            </Reveal>

            {recommendations && recommendations.recommended_lessons.length > 0 && (
              <Reveal>
                <SectionHeading
                  title="Препоръчани уроци"
                  description="Избрани заради темите с най-ниска точност."
                />
                <ul className="grid gap-3 sm:grid-cols-2">
                  {recommendations.recommended_lessons.map((lesson) => (
                    <li key={lesson.lesson_id}>
                      <button
                        type="button"
                        onClick={() => navigate(`/lessons/${lesson.lesson_id}/exercises`)}
                        className="flex w-full flex-col gap-1 rounded-xl border border-line bg-surface p-5 text-left shadow-lift-1 transition-[border-color,box-shadow] hover:border-brand hover:shadow-lift-2"
                      >
                        <span className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
                          {lesson.topic_title}
                        </span>
                        <span className="text-body font-semibold text-ink">{lesson.lesson_title}</span>
                        <span className="text-caption text-ink-muted">{lesson.reason}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </Reveal>
            )}

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

const ProgressSkeleton: React.FC = () => (
  <div className="space-y-10" role="status" aria-live="polite">
    <span className="sr-only">Прогресът се зарежда</span>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-28" />
      ))}
    </div>
    <Skeleton className="h-10 w-72" />
    <div className="space-y-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-16" />
      ))}
    </div>
  </div>
);

export default ProgressSummaryPage;
