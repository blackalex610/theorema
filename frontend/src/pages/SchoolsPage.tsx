import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BuildingsIcon, ChalkboardTeacherIcon, PlusIcon } from '@phosphor-icons/react';

import AppNavbar from '../components/AppNavbar';
import {
  EmptyState,
  ErrorState,
  PageHeader,
  PageShell,
  SectionHeading,
} from '../components/app/PageShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  createSchool,
  joinSchool,
  listSchoolsIDirect,
  listSchoolsIJoined,
  type JoinedSchool,
  type School,
} from '../services/schools';

/**
 * Both sides of schools on one screen, mirroring "Моите класове": the same
 * account can direct a school and teach in someone else's.
 *
 * Joining comes first because teachers far outnumber directors. The copy
 * says plainly what joining does and does not do — a teacher joining a
 * school shares nothing until they attach a class themselves.
 */
const SchoolsPage: React.FC = () => {
  const [directed, setDirected] = useState<School[] | null>(null);
  const [joined, setJoined] = useState<JoinedSchool[] | null>(null);
  const [loadError, setLoadError] = useState(false);

  const [code, setCode] = useState('');
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);
  const [joinedNotice, setJoinedNotice] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [city, setCity] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(false);
    try {
      const [mine, theirs] = await Promise.all([listSchoolsIDirect(), listSchoolsIJoined()]);
      setDirected(mine);
      setJoined(theirs);
    } catch {
      setLoadError(true);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onJoin = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!code.trim()) return;
    setJoining(true);
    setJoinError(null);
    setJoinedNotice(null);
    try {
      const school = await joinSchool(code.trim());
      setJoinedNotice(
        `Вече си учител в „${school.name}“. Отвори свой клас, за да го включиш в отчетите на училището.`
      );
      setCode('');
      await load();
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      setJoinError(
        status === 404
          ? 'Няма училище с този код. Провери го с директора.'
          : status === 410
            ? 'Това училище вече не приема учители.'
            : 'Нещо се обърка. Опитай пак.'
      );
    } finally {
      setJoining(false);
    }
  };

  const onCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      await createSchool(name.trim(), city.trim() || null);
      setName('');
      setCity('');
      await load();
    } catch {
      setCreateError('Училището не беше създадено. Опитай пак.');
    } finally {
      setCreating(false);
    }
  };

  if (loadError) {
    return (
      <>
        <AppNavbar />
        <PageShell>
          <ErrorState description="Училищата не се заредиха." onRetry={load} />
        </PageShell>
      </>
    );
  }

  const loading = directed === null || joined === null;

  return (
    <>
      <AppNavbar />
      <PageShell>
        <PageHeader
          kicker="Училища"
          title="Моето училище"
          description="Учителите се присъединяват с код от директора и сами решават кои от класовете си да включат. Директорът вижда средни резултати по класове и теми — никога имена на ученици."
        />

        {/* ── Join, first: most people here are teachers ──────────────── */}
        <section className="mb-10">
          <SectionHeading title="Присъедини се като учител" />
          <form
            onSubmit={onJoin}
            className="mt-4 flex flex-col gap-3 rounded-xl border border-line bg-surface p-5 sm:flex-row sm:items-end"
          >
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="school-code">Код на училището</Label>
              <Input
                id="school-code"
                value={code}
                onChange={(event) => setCode(event.target.value.toUpperCase())}
                placeholder="напр. H4TWQ9"
                maxLength={12}
                autoComplete="off"
                spellCheck={false}
                className="font-mono uppercase tracking-[0.15em]"
              />
            </div>
            <Button type="submit" disabled={joining || !code.trim()}>
              {joining ? 'Момент…' : 'Присъедини се'}
            </Button>
          </form>
          {joinError && (
            <p role="alert" className="mt-2 text-caption font-medium text-danger">
              {joinError}
            </p>
          )}
          {joinedNotice && (
            <p className="mt-2 text-caption font-medium text-brand-ink">
              {joinedNotice}{' '}
              <Link to="/classrooms" className="underline underline-offset-4">
                Към класовете
              </Link>
            </p>
          )}

          {loading ? (
            <Skeleton className="mt-4 h-16 w-full" />
          ) : joined.length > 0 ? (
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">
              {joined.map((school) => (
                <li
                  key={school.id}
                  className="flex items-center gap-3 rounded-xl border border-line bg-surface p-4"
                >
                  <ChalkboardTeacherIcon aria-hidden="true" className="size-5 shrink-0 text-brand" />
                  <div className="min-w-0">
                    <p className="truncate text-body font-semibold text-ink">{school.name}</p>
                    <p className="text-caption text-ink-muted">
                      {school.city ? `${school.city} · ` : ''}учител
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        {/* ── Direct ──────────────────────────────────────────────────── */}
        <section>
          <SectionHeading title="Училища, които ръководя" />
          <form
            onSubmit={onCreate}
            className="mt-4 grid gap-3 rounded-xl border border-line bg-surface p-5 sm:grid-cols-[2fr_1fr_auto] sm:items-end"
          >
            <div className="space-y-1.5">
              <Label htmlFor="school-name">Име на училището</Label>
              <Input
                id="school-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="напр. СУ „Иван Вазов“"
                maxLength={160}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="school-city">Град</Label>
              <Input
                id="school-city"
                value={city}
                onChange={(event) => setCity(event.target.value)}
                placeholder="Пловдив"
                maxLength={120}
              />
            </div>
            <Button type="submit" disabled={creating || !name.trim()}>
              <PlusIcon aria-hidden="true" /> {creating ? 'Създаване…' : 'Създай'}
            </Button>
          </form>
          {createError && (
            <p role="alert" className="mt-2 text-caption font-medium text-danger">
              {createError}
            </p>
          )}

          {loading ? (
            <Skeleton className="mt-4 h-28 w-full" />
          ) : directed.length === 0 ? (
            <div className="mt-4">
              <EmptyState
                icon={<BuildingsIcon />}
                title="Не ръководиш училище"
                description="Ако си директор, създай училището и раздай кода на учителите."
              />
            </div>
          ) : (
            <ul className="mt-4 grid gap-3 sm:grid-cols-2">
              {directed.map((school) => (
                <li key={school.id}>
                  <Link
                    to={`/schools/${school.id}`}
                    className="flex h-full flex-col gap-3 rounded-xl border border-line bg-surface p-5 transition-[border-color] hover:border-brand"
                  >
                    <p className="truncate text-title font-semibold text-ink">{school.name}</p>
                    {school.city && <p className="text-caption text-ink-muted">{school.city}</p>}
                    <p className="mt-auto">
                      <span className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
                        Код за учители
                      </span>
                      <span className="mt-1 block font-mono text-title font-semibold tracking-[0.2em] text-brand-ink">
                        {school.join_code}
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

export default SchoolsPage;
