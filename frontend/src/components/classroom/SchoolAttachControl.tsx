import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BuildingsIcon } from '@phosphor-icons/react';

import { Button } from '@/components/ui/button';
import {
  attachClassroom,
  detachClassroom,
  listSchoolsIDirect,
  listSchoolsIJoined,
} from '../../services/schools';

interface SchoolOption {
  id: number;
  name: string;
}

/**
 * The teacher's decision to put this class in a school's reports.
 *
 * It lives on the teacher's own class page, not on the director's screen, on
 * purpose: the director cannot sweep a class in. What the director will see
 * is spelled out next to the button, so the teacher opts in knowing it.
 */
const SchoolAttachControl: React.FC<{
  classroomId: number;
  schoolId: number | null | undefined;
  onChange: () => void;
}> = ({ classroomId, schoolId, onChange }) => {
  const [schools, setSchools] = useState<SchoolOption[] | null>(null);
  const [selected, setSelected] = useState<string>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listSchoolsIJoined(), listSchoolsIDirect()])
      .then(([joined, directed]) => {
        if (cancelled) return;
        const byId = new Map<number, SchoolOption>();
        [...directed, ...joined].forEach((s) => byId.set(s.id, { id: s.id, name: s.name }));
        const options = [...byId.values()];
        setSchools(options);
        if (options.length > 0) setSelected(String(options[0].id));
      })
      .catch(() => {
        if (!cancelled) setSchools([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (schools === null) return null;

  const current = schools.find((s) => s.id === schoolId);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChange();
    } catch {
      setError('Промяната не беше записана.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-4 sm:flex-row sm:items-center">
      <BuildingsIcon aria-hidden="true" className="size-5 shrink-0 text-ink-faint" />
      <div className="min-w-0 flex-1 text-caption text-ink-muted">
        {schoolId ? (
          <>
            Класът е в отчетите на{' '}
            <span className="font-semibold text-ink">{current?.name ?? 'училището'}</span>.
            Директорът вижда средни резултати и теми, не отделни ученици.
          </>
        ) : schools.length === 0 ? (
          <>
            Класът не е към училище.{' '}
            <Link to="/schools" className="font-medium text-brand-ink underline-offset-4 hover:underline">
              Присъедини се към училище с код
            </Link>
            , за да го включиш в отчетите му.
          </>
        ) : (
          <>Включи класа в отчетите на училище. Директорът ще вижда средни резултати, не имена.</>
        )}
        {error && (
          <span role="alert" className="mt-1 block text-danger">
            {error}
          </span>
        )}
      </div>

      {schoolId ? (
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() => run(() => detachClassroom(classroomId))}
        >
          Извади от училището
        </Button>
      ) : (
        schools.length > 0 && (
          <div className="flex gap-2">
            {schools.length > 1 && (
              <select
                aria-label="Училище"
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                className="h-9 rounded-lg border border-line bg-surface px-2 text-caption text-ink"
              >
                {schools.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            )}
            <Button
              size="sm"
              disabled={busy || !selected}
              onClick={() => run(() => attachClassroom(Number(selected), classroomId))}
            >
              Включи {schools.length === 1 ? `в ${schools[0].name}` : ''}
            </Button>
          </div>
        )
      )}
    </div>
  );
};

export default SchoolAttachControl;
