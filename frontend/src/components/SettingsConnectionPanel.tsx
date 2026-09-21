import React from 'react';
import { useConnect } from '../context/ConnectContext';
import MathVisionPanel from './MathVisionPanel';

const relativeTime = (announcedAt: number): string => {
  const seconds = Math.max(0, Math.round((Date.now() - announcedAt) / 1000));
  if (seconds < 60) return 'преди малко';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `преди ${minutes} мин`;
  return `преди ${Math.round(minutes / 60)} ч`;
};

const Countdown: React.FC<{ expiresAt: number }> = ({ expiresAt }) => {
  const [left, setLeft] = React.useState(() =>
    Math.max(0, Math.round((expiresAt - Date.now()) / 1000))
  );

  React.useEffect(() => {
    const timer = window.setInterval(
      () => setLeft(Math.max(0, Math.round((expiresAt - Date.now()) / 1000))),
      1000
    );
    return () => window.clearInterval(timer);
  }, [expiresAt]);

  return <span className="tnum">{left} с</span>;
};

const SettingsConnectionPanel: React.FC = () => {
  const {
    status,
    error,
    devices,
    linkedDevice,
    pendingRequest,
    latestImage,
    refreshDevices,
    requestLink,
    cancelRequest,
    endLink,
  } = useConnect();

  React.useEffect(() => {
    void refreshDevices();
  }, [refreshDevices]);

  const busyElsewhere = (deviceId: string) =>
    linkedDevice?.deviceId !== deviceId && pendingRequest?.deviceId !== deviceId;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-line bg-surface p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h4 className="text-sm font-bold text-ink">Свързване с телефон</h4>
            <p className="mt-1 text-caption text-ink-muted">
              Телефоните се появяват тук, докато са отворили раздел „Свързване“.
            </p>
          </div>
          <span className="rounded-full bg-sunken px-3 py-1 text-caption font-semibold text-ink-muted">
            {devices.length}
          </span>
        </div>

        {error ? (
          <p role="status" className="mt-3 text-caption font-medium text-danger">
            {error}
          </p>
        ) : null}

        {linkedDevice ? (
          <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-brand-edge bg-brand-wash px-4 py-3">
            <div className="min-w-0">
              <p className="truncate font-semibold text-brand-ink">{linkedDevice.name}</p>
              <p className="mt-0.5 text-caption text-brand-ink/80">Свързан</p>
            </div>
            <button
              type="button"
              onClick={() => void endLink()}
              className="shrink-0 rounded-xl border border-brand-edge px-3 py-2 text-caption font-semibold text-brand-ink transition-colors hover:bg-brand-edge/40"
            >
              Прекъсни
            </button>
          </div>
        ) : null}

        {pendingRequest ? (
          <div className="mt-4 flex items-center justify-between gap-3 rounded-xl border border-line-strong bg-sunken px-4 py-3">
            <p className="text-caption font-medium text-ink">
              Изчаква потвърждение от телефона · <Countdown expiresAt={pendingRequest.expiresAt} />
            </p>
            <button
              type="button"
              onClick={() => void cancelRequest()}
              className="shrink-0 rounded-xl border border-line-strong px-3 py-2 text-caption font-semibold text-ink transition-colors hover:bg-line/40"
            >
              Откажи
            </button>
          </div>
        ) : null}

        <div className="mt-4 space-y-2">
          {devices.length === 0 ? (
            <div className="rounded-xl border border-dashed border-line-strong px-4 py-6 text-center text-caption text-ink-muted">
              {status === 'connecting'
                ? 'Свързване със сървъра…'
                : 'Отвори приложението на телефона си и влез в раздел „Свързване“.'}
            </div>
          ) : (
            devices.map((device) => {
              const isLinked = linkedDevice?.deviceId === device.deviceId;
              const isPending = pendingRequest?.deviceId === device.deviceId;
              const blocked = device.busy || Boolean(pendingRequest) || Boolean(linkedDevice);

              return (
                <div
                  key={device.deviceId}
                  className="flex items-center justify-between gap-3 rounded-xl border border-line bg-sunken px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-ink">{device.name}</p>
                    <p className="mt-0.5 text-caption text-ink-muted">
                      {device.platform} · {relativeTime(device.announcedAt)}
                      {device.busy && busyElsewhere(device.deviceId) ? ' · заето' : ''}
                    </p>
                  </div>
                  <button
                    type="button"
                    disabled={blocked}
                    onClick={() => void requestLink(device.deviceId)}
                    className="shrink-0 rounded-xl bg-brand px-3 py-2 text-caption font-semibold text-white transition-colors hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isLinked ? 'Свързан' : isPending ? 'Изчаква…' : 'Свържи'}
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-line bg-surface p-4">
        <div className="mb-3">
          <h4 className="text-sm font-bold text-ink">Математическо разпознаване</h4>
          <p className="mt-0.5 text-caption text-ink-muted">
            Качи снимка — AI ще извлече уравненията и текста.
          </p>
        </div>
        <MathVisionPanel autoImage={latestImage} />
      </div>
    </div>
  );
};

export default SettingsConnectionPanel;
