import React from 'react';
import { getNickname, setNickname } from '../../utils/deviceIdentity';

type Props = { deviceName: string; onNicknameChange: (name: string) => void };

const PhoneVisibleScreen: React.FC<Props> = ({ deviceName, onNicknameChange }) => {
  const [draft, setDraft] = React.useState(() => getNickname());

  const commit = () => {
    setNickname(draft);
    onNicknameChange(draft.trim());
  };

  return (
    <div className="text-center">
      <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-brand-wash">
        <span className="size-3 animate-pulse rounded-full bg-brand" aria-hidden />
      </div>
      <h1 className="mt-4 text-2xl font-bold text-ink">Видим си</h1>
      <p className="mt-2 text-caption text-ink-muted">Компютърът ти може да те види като</p>
      <p className="mt-1 text-base font-semibold text-ink">{deviceName}</p>

      <label className="mt-6 block text-left">
        <span className="text-caption font-semibold text-ink-muted">Име на устройството</span>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value.slice(0, 40))}
          onBlur={commit}
          placeholder="напр. Телефонът на Иван"
          className="mt-1 h-12 w-full rounded-2xl border border-line bg-surface px-4 text-base text-ink outline-none transition-colors focus:border-brand"
        />
      </label>

      <p className="mt-6 text-caption text-ink-muted">
        Избери това устройство на компютъра, за да се свържеш.
      </p>
    </div>
  );
};

export default PhoneVisibleScreen;
