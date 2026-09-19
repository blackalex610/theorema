import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChalkboardTeacherIcon, PlusIcon, StudentIcon } from '@phosphor-icons/react';

import AppNavbar from '../components/AppNavbar';
import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageShell,
  SectionHeading,
} from '../components/app/PageShell';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  createClassroom,
  joinClassroom,
  listClassesIJoined,
  listMyClasses,
  type Classroom,
  type JoinedClassroom,
} from '../services/classrooms';

/**
 * Both sides of classrooms on one screen, because a person is not a role: the
 * same account can run a class and be in someone else's. Built mobile-first
 * — the audit's whole S3 finding was that the product pages were not.
 */
const ClassroomsPage: React.FC = () => {
  const [taught, setTaught] = useState<Classroom[] | null>(null);
  const [joined, setJoined] = useState<JoinedClassroom[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [code, setCode] = useState('');
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [joinedNotice, setJoinedNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(false);
    try {
      const [mine, theirs] = await Promise.all([listMyClasses(), listClassesIJoined()]);
      setTaught(mine);
      setJoined(theirs);
    } catch {
      setLoadError(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      await createClassroom(newName.trim());
      setNewName('');
      await load();
    } catch {
      setCreateError('Класът не беше създаден. Опитай пак.');
    } finally {
      setCreating(false);
    }
  };

  const onJoin = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!code.trim()) return;
    setJoining(true);
    setJoinError(null);
    setJoinedNotice(null);
    try {
      const classroom = await joinClassroom(code.trim());
      setJoinedNotice(`Вече си в „${classroom.name}“.`);
      setCode('');
      await load();
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      setJoinError(
        status === 404
          ? 'Няма клас с този код. Провери го с учителя си.'
          : status === 410
            ? 'Този клас вече не приема нови ученици.'
            : status === 400
              ? 'Това е твоят собствен клас.'
              : 'Нещо се обърка. Опитай пак.'
      );
    } finally {
      setJoining(false);
    }
  };

  if (loadError) {
    return (
      <>
        <AppNavbar />
        <PageShell>
          <ErrorState description="Класовете не се заредиха." onRetry={load} />
        </PageShell>
      </>
    );
  }

  const loading = taught === null || joined === null;

  return (
    <>
      <AppNavbar />
      <PageShell>
        <PageHeader
          kicker="Класове"
          title="Моите класове"
          description="Създай клас и дай кода на учениците си, или се присъедини към клас с код от учителя."
        />

        {/* ── Join, first: most people who open this page are students ── */}
        <section className="mb-10">
          <SectionHeading title="Присъедини се към клас" />
          <form
            onSubmit={onJoin}
            className="mt-4 flex flex-col gap-3 rounded-xl border border-line bg-surface p-5 sm:flex-row sm:items-end"
          >
            <label className="flex-1">
              <span className="mb-1.5 block text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
                Код на класа
              </span>
              <input
                value={code}
                onChange={(event) => setCode(event.target.value.toUpperCase())}
                placeholder="напр. K7RMPQ"
                maxLength={12}
                autoComplete="off"
                spellCheck={false}
                className="tnum w-full rounded-lg border border-line bg-paper px-3 py-2.5 font-mono text-body uppercase tracking-[0.15em] text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand-edge"
              />
            </label>
            <Button type="submit" disabled={joining || !code.trim()} className="sm:w-auto">
              {joining ? 'Момент…' : 'Влез в класа'}
            </Button>
          </form>
          {joinError && (
            <p role="alert" className="mt-2 text-caption font-medium text-danger">
              {joinError}
            </p>
          )}
          {joinedNotice && (
            <p className="mt-2 text-caption font-medium text-brand-ink">{joinedNotice}</p>
          )}

          {loading ? (
            <Skeleton className="mt-4 h-16 w-full" />
          ) : joined.length > 0 ? (
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">
              {joined.map((classroom) => (
                <li
                  key={classroom.id}
                  className="flex items-center gap-3 rounded-xl border border-line bg-surface p-4"
                >
                  <StudentIcon aria-hidden="true" className="size-5 shrink-0 text-brand" />
                  <div className="min-w-0">
                    <p className="truncate text-body font-semibold text-ink">{classroom.name}</p>
                    <p className="text-caption text-ink-muted">
                      {classroom.is_active ? 'Активен клас' : 'Архивиран клас'}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        {/* ── Teach ────────────────────────────────────────────────────── */}
        <section>
          <SectionHeading title="Класове, които водя" />
          <form
            onSubmit={onCreate}
            className="mt-4 flex flex-col gap-3 rounded-xl border border-line bg-surface p-5 sm:flex-row sm:items-end"
          >
            <label className="flex-1">
              <span className="mb-1.5 block text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
                Име на новия клас
              </span>
              <input
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
                placeholder="напр. 7А математика"
                maxLength={120}
                className="w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-body text-ink outline-none transition-colors focus:border-brand focus:ring-2 focus:ring-brand-edge"
              />
            </label>
            <Button type="submit" disabled={creating || !newName.trim()} className="sm:w-auto">
              <PlusIcon aria-hidden="true" /> {creating ? 'Създаване…' : 'Създай клас'}
            </Button>
          </form>
          {createError && (
            <p role="alert" className="mt-2 text-caption font-medium text-danger">
              {createError}
            </p>
          )}

          {loading ? (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          ) : taught.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                icon={<ChalkboardTeacherIcon />}
                title="Още нямаш свой клас"
                description="Създай клас, дай кода на учениците и ще виждаш напредъка им на едно място."
              />
            </div>
          ) : (
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">
              {taught.map((classroom) => (
                <li key={classroom.id}>
                  <Link
                    to={`/classrooms/${classroom.id}`}
                    className="flex h-full flex-col gap-3 rounded-xl border border-line bg-surface p-5 transition-[border-color] hover:border-brand"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="min-w-0 truncate text-title font-semibold text-ink">
                        {classroom.name}
                      </p>
                      {!classroom.is_active && (
                        <span className="shrink-0 rounded-full border border-line-strong px-2 py-0.5 text-micro font-semibold uppercase text-ink-faint">
                          Архивиран
                        </span>
                      )}
                    </div>
                    <p className="text-caption text-ink-muted">
                      {classroom.student_count}{' '}
                      {classroom.student_count === 1 ? 'ученик' : 'ученици'}
                    </p>
                    <p className="mt-auto">
                      <span className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
                        Код за присъединяване
                      </span>
                      <span className="mt-1 block font-mono text-title font-semibold tracking-[0.2em] text-brand-ink">
                        {classroom.join_code}
                      </span>
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </PageShell>
    </>
  );
};

export default ClassroomsPage;
