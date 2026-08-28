import React from 'react';
import { useSettings } from '../context/SettingsContext';
import SettingsSection from './SettingsSection';
import SettingsConnectionPanel from './SettingsConnectionPanel';
import ThemeSwitch from './ThemeSwitch';
import { usePlan } from '../hooks/usePlan';
import { useDeveloperMode, DevOnly } from '../context/DeveloperModeContext';

const SettingsModal: React.FC = () => {
  const { isSettingsOpen, closeSettings, language, setLanguage } = useSettings();
  const { status: planStatus, upgrade, refresh } = usePlan();
  const [isUpgrading, setIsUpgrading] = React.useState(false);
  const [upgradeError, setUpgradeError] = React.useState<string | null>(null);
  const premiumSectionRef = React.useRef<HTMLDivElement | null>(null);
  const { isDevMode, toggleDevMode } = useDeveloperMode();
  const [devClickCount, setDevClickCount] = React.useState(0);
  const devClickTimerRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (!isSettingsOpen) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeSettings();
      }
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [closeSettings, isSettingsOpen]);

  React.useEffect(() => {
    if (!isSettingsOpen) return;
    if (window.location.hash !== '#upgrade') return;
    premiumSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [isSettingsOpen]);

  const handleUpgrade = async () => {
    setIsUpgrading(true);
    setUpgradeError(null);
    try {
      await upgrade();
      await refresh();
    } catch (error) {
      // /plan/upgrade no longer grants premium without a verified payment, so
      // it answers 402 until a provider is wired up. Show that instead of
      // letting the rejection escape and leaving the button silently dead.
      const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setUpgradeError(
        typeof detail === 'string'
          ? detail
          : 'Премиум ъпгрейдът все още не е активен.'
      );
    } finally {
      setIsUpgrading(false);
    }
  };

  if (!isSettingsOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/45 p-4 backdrop-blur-sm sm:p-6">
      <button
        type="button"
        aria-label="Close settings"
        className="absolute inset-0 cursor-default"
        onClick={closeSettings}
      />

      <div className="relative z-10 mt-10 flex max-h-[calc(100vh-4rem)] w-full max-w-2xl flex-col overflow-hidden rounded-[28px] border border-gray-200 bg-white shadow-2xl shadow-slate-900/15 dark:border-slate-700 dark:bg-slate-900 dark:shadow-black/40">
        <div className="border-b border-gray-100 bg-gradient-to-r from-slate-50 via-white to-blue-50 px-6 py-5 dark:border-slate-800 dark:from-slate-900 dark:via-slate-900 dark:to-slate-800">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-600 dark:text-blue-400">Global preferences</p>
              {/* Developer mode activation: triple-click the Settings title */}
              <h2
                className="mt-2 text-2xl font-bold text-gray-900 dark:text-slate-100 cursor-default select-none"
                onClick={() => {
                  const newCount = devClickCount + 1;
                  setDevClickCount(newCount);
                  if (devClickTimerRef.current) {
                    window.clearTimeout(devClickTimerRef.current);
                  }
                  devClickTimerRef.current = window.setTimeout(() => {
                    setDevClickCount(0);
                  }, 800);
                  if (newCount >= 3) {
                    toggleDevMode();
                    setDevClickCount(0);
                  }
                }}
                title={isDevMode ? 'Developer mode active - triple-click to disable' : 'Triple-click to toggle developer mode'}
              >
                Settings
                {isDevMode && (
                  <span className="ml-2 inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                    <span>⚠️</span> DEV
                  </span>
                )}
              </h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
                Personalize appearance and app defaults across the entire experience.
              </p>
            </div>
            <button
              type="button"
              onClick={closeSettings}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-500 transition-colors hover:border-blue-300 hover:text-blue-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400 dark:hover:border-blue-400 dark:hover:text-blue-300"
              aria-label="Close settings"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </div>
        </div>

        <div className="min-h-0 space-y-4 overflow-y-auto px-6 py-6">
          <SettingsSection
            title="Външен вид"
            description="Избери светла или тъмна тема. Настройката се прилага навсякъде."
          >
            <ThemeSwitch />
          </SettingsSection>

          <SettingsSection
            title="Език"
            description="Езикът на интерфейса. Пълните преводи се добавят постепенно."
          >
            <label className="block">
              <span className="mb-2 block text-sm font-medium text-gray-700 dark:text-slate-300">App language</span>
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value as 'en' | 'bg')}
                className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800 shadow-sm outline-none transition-colors focus:border-blue-400 focus:ring-4 focus:ring-blue-100 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:focus:border-blue-400 dark:focus:ring-blue-500/20"
              >
                <option value="en">English</option>
                <option value="bg">Bulgarian</option>
              </select>
            </label>
          </SettingsSection>

          <DevOnly badgeLabel="Experimental">
            <SettingsSection
              title="Connection / Pairing"
              description="Create a room on desktop and join it from a phone using a 4-letter code."
            >
              <SettingsConnectionPanel />
            </SettingsSection>
          </DevOnly>

          <div ref={premiumSectionRef}>
            <SettingsSection
              title="Premium"
              description="Unlock unlimited AI learning features."
            >
              <div className="space-y-3">
                <div className={`rounded-2xl border p-4 ${planStatus.is_premium ? 'border-emerald-300 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-900/20' : 'border-amber-300 bg-amber-50 dark:border-amber-700 dark:bg-amber-900/20'}`}>
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                    Current plan: {planStatus.is_premium ? 'Premium ⚡' : 'Free'}
                  </p>
                  {!planStatus.is_premium && (
                    <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                      Free limits: {planStatus.usage.ai_exercises.used}/{planStatus.usage.ai_exercises.limit} AI tasks, {planStatus.usage.ai_chat.used}/{planStatus.usage.ai_chat.limit} chat, {planStatus.usage.nvo_exams.used}/{planStatus.usage.nvo_exams.limit} NVO, {planStatus.usage.image_scans.used}/{planStatus.usage.image_scans.limit} scans today.
                    </p>
                  )}
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
                    <p className="text-xs font-bold uppercase tracking-widest text-slate-500">Monthly</p>
                    <p className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">$4.99<span className="text-sm font-medium text-slate-500">/month</span></p>
                    <ul className="mt-3 space-y-1 text-xs text-slate-600 dark:text-slate-300">
                      <li>• Unlimited AI tasks</li>
                      <li>• Unlimited AI chat</li>
                      <li>• Unlimited NVO exams</li>
                      <li>• Unlimited image scans</li>
                    </ul>
                  </div>
                  <div className="rounded-2xl border border-blue-300 bg-blue-50 p-4 dark:border-blue-700 dark:bg-blue-900/20">
                    <p className="text-xs font-bold uppercase tracking-widest text-blue-600">Yearly</p>
                    <p className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">$39.99<span className="text-sm font-medium text-slate-500">/year</span></p>
                    <p className="mt-2 inline-block rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold text-white">Save 33%</p>
                    <ul className="mt-3 space-y-1 text-xs text-slate-600 dark:text-slate-300">
                      <li>• Everything in monthly</li>
                      <li>• Best value for exam prep</li>
                    </ul>
                  </div>
                </div>

                {!planStatus.is_premium ? (
                  <button
                    type="button"
                    onClick={handleUpgrade}
                    disabled={isUpgrading}
                    className="w-full rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-3 text-sm font-bold text-white shadow-sm transition-all hover:from-amber-600 hover:to-orange-600 disabled:cursor-not-allowed disabled:opacity-70"
                  >
                    {isUpgrading ? 'Upgrading...' : '⚡ Buy Premium'}
                  </button>
                ) : (
                  <div className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-300">
                    Premium is active. Enjoy unlimited access.
                  </div>
                )}

                {upgradeError && (
                  <p className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-200">
                    {upgradeError}
                  </p>
                )}

                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  Payment provider is not connected yet, so upgrading is disabled. The endpoint no longer grants premium without a verified payment.
                </p>
              </div>
            </SettingsSection>
          </div>
        </div>

        <div className="flex items-center justify-end border-t border-gray-100 px-6 py-4 dark:border-slate-800">
          <button
            type="button"
            onClick={closeSettings}
            className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsModal;