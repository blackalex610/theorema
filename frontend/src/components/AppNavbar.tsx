import React, { useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowLeftIcon,
  BookOpenIcon,
  ChalkboardTeacherIcon,
  ChartLineUpIcon,
  DeviceMobileIcon,
  GearSixIcon,
  HouseIcon,
  ListIcon,
  PencilSimpleLineIcon,
  SignOutIcon,
  SparkleIcon,
  UserIcon,
} from '@phosphor-icons/react';

import { useSettings } from '../context/SettingsContext';
import { useConnect } from '../context/ConnectContext';
import { useXp } from '../context/XpContext';
import { useAuth } from '../context/AuthContext';
import { usePlan } from '../hooks/usePlan';
import { trackEvent } from '../services/analytics';
import Brand from './Brand';
import ThemeSwitch from './ThemeSwitch';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

/**
 * The application header.
 *
 * One line, 64px tall, sticky. It replaces the previous collapsible sidebar
 * plus mobile tab bar: a single source of navigation means the content column
 * is the same width on every screen, and the document keeps a single scroll
 * container so Lenis and Motion's viewport hooks work everywhere.
 *
 * The props are unchanged from the previous navbar so no calling page had to
 * be edited to adopt it.
 */

interface AppNavbarProps {
  showBack?: boolean;
  backLabel?: string;
  backTo?: string;
  maxWidthClassName?: string;
  sticky?: boolean;
}

const NAV_ITEMS = [
  { label: 'Табло', path: '/dashboard', Icon: HouseIcon, exact: true },
  { label: 'Теория', path: '/learn/grades', Icon: BookOpenIcon, exact: false },
  { label: 'Упражнения', path: '/grades', Icon: PencilSimpleLineIcon, exact: false },
  { label: 'НВО изпити', path: '/nvo/practice', Icon: SparkleIcon, exact: false },
  { label: 'Прогрес', path: '/progress', Icon: ChartLineUpIcon, exact: false },
  { label: 'Класове', path: '/classrooms', Icon: ChalkboardTeacherIcon, exact: false },
] as const;

const USAGE_ROWS = [
  { key: 'ai_exercises', label: 'AI задачи' },
  { key: 'ai_theory', label: 'AI теория' },
  { key: 'ai_chat', label: 'AI чат' },
  { key: 'nvo_exams', label: 'НВО изпити' },
  { key: 'image_scans', label: 'Снимки' },
] as const;

const AppNavbar: React.FC<AppNavbarProps> = ({
  showBack = true,
  backLabel = 'Назад',
  backTo,
  sticky = true,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { openSettings } = useSettings();
  const { xpSummary } = useXp();
  const { status: planStatus } = usePlan();
  const { user, isGuest, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  // Every user now holds a real token (guests included), so mobile pairing
  // works identically for both — no isGuest exception needed.
  const canUseMobileConnect = Boolean(user);
  const firstName = user?.name?.split(' ')[0] ?? 'Ученик';

  const handleBack = () => (backTo ? navigate(backTo) : navigate(-1));

  const handleLogout = () => {
    trackEvent('logout');
    signOut();
    navigate('/');
  };

  const isItemActive = (path: string, exact: boolean) =>
    exact ? location.pathname === path : location.pathname.startsWith(path);

  return (
    <header
      className={cn(
        'z-40 border-b border-line bg-paper/85 backdrop-blur-xl',
        sticky && 'sticky top-0'
      )}
    >
      <div className="mx-auto flex h-16 w-full max-w-[90rem] items-center gap-3 px-4 sm:px-6">
        {/* Left: back, brand, primary navigation */}
        <div className="flex min-w-0 items-center gap-2">
          {showBack && (
            <Button
              variant="ghost"
              size="icon"
              onClick={handleBack}
              aria-label={backLabel}
              title={backLabel}
              className="shrink-0"
            >
              <ArrowLeftIcon />
            </Button>
          )}

          <NavLink
            to="/dashboard"
            className="shrink-0 rounded-lg"
            aria-label="Smart NVO, начало"
          >
            <Brand size="sm" className="hidden sm:inline-flex" />
            <Brand size="sm" markOnly className="sm:hidden" />
          </NavLink>
        </div>

        <nav aria-label="Основна навигация" className="ml-4 hidden items-center gap-1 lg:flex">
          {NAV_ITEMS.map(({ label, path, Icon, exact }) => {
            const active = isItemActive(path, exact);
            return (
              <NavLink
                key={path}
                to={path}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'inline-flex h-9 items-center gap-2 rounded-lg px-3 text-caption font-semibold transition-colors duration-200',
                  active
                    ? 'bg-brand-wash text-brand-ink'
                    : 'text-ink-muted hover:bg-sunken hover:text-ink'
                )}
              >
                <Icon weight={active ? 'fill' : 'regular'} className="size-4" />
                {label}
              </NavLink>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {/* Level and XP, set in the mono face like every other number */}
          {xpSummary && (
            <div
              className="hidden items-center gap-2 rounded-lg border border-line bg-surface px-2.5 py-1.5 sm:flex"
              title={`Ниво ${xpSummary.level}, общо ${xpSummary.total_xp} XP`}
            >
              <span className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
                Ниво
              </span>
              <span className="tnum text-caption font-semibold text-ink">{xpSummary.level}</span>
              <span className="h-3.5 w-px bg-line" />
              <span className="tnum text-caption text-ink-muted">{xpSummary.total_xp} XP</span>
              {xpSummary.streak_days > 1 && (
                <>
                  <span className="h-3.5 w-px bg-line" />
                  <span className="tnum text-caption font-semibold text-warn">
                    {xpSummary.streak_days} дни
                  </span>
                </>
              )}
            </div>
          )}

          {canUseMobileConnect && <PairingChip />}

          <ThemeSwitch className="hidden sm:inline-flex" />

          {/* Account */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface py-1 pl-1 pr-2.5 transition-colors duration-200 hover:border-line-strong"
                aria-label="Меню на профила"
              >
                <Avatar user={user} />
                <span className="hidden max-w-28 truncate text-caption font-semibold text-ink md:inline">
                  {firstName}
                </span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-60">
              <DropdownMenuLabel className="flex flex-col gap-0.5">
                <span className="text-body font-semibold text-ink">{user?.name ?? 'Ученик'}</span>
                {user?.email && (
                  <span className="truncate text-caption font-normal text-ink-muted">
                    {user.email}
                  </span>
                )}
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              {isGuest && (
                <DropdownMenuItem onSelect={() => navigate('/')}>
                  <UserIcon className="size-4" />
                  Запази прогреса си
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onSelect={() => navigate('/progress')}>
                <UserIcon className="size-4" />
                Моят прогрес
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => openSettings()}>
                <GearSixIcon className="size-4" />
                Настройки
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={handleLogout} variant="destructive">
                <SignOutIcon className="size-4" />
                Излизане
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Mobile navigation */}
          <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" aria-label="Отвори менюто" className="lg:hidden">
                <ListIcon />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[19rem] gap-0 p-0">
              <SheetHeader className="border-b border-line px-5 py-4">
                <SheetTitle className="text-left">
                  <Brand size="sm" />
                </SheetTitle>
              </SheetHeader>

              <nav aria-label="Навигация" className="flex flex-col gap-1 p-3">
                {NAV_ITEMS.map(({ label, path, Icon, exact }) => {
                  const active = isItemActive(path, exact);
                  return (
                    <SheetClose asChild key={path}>
                      <NavLink
                        to={path}
                        aria-current={active ? 'page' : undefined}
                        className={cn(
                          'flex h-11 items-center gap-3 rounded-lg px-3 text-body font-semibold transition-colors',
                          active
                            ? 'bg-brand-wash text-brand-ink'
                            : 'text-ink-muted hover:bg-sunken hover:text-ink'
                        )}
                      >
                        <Icon weight={active ? 'fill' : 'regular'} className="size-5" />
                        {label}
                      </NavLink>
                    </SheetClose>
                  );
                })}
              </nav>

              <Separator />

              <div className="flex items-center justify-between gap-3 px-5 py-4">
                <span className="text-caption font-semibold text-ink-muted">Тема</span>
                <ThemeSwitch />
              </div>

              {!planStatus.is_premium && (
                <>
                  <Separator />
                  <div className="space-y-3 px-5 py-4">
                    <p className="text-micro font-semibold uppercase tracking-[0.08em] text-ink-faint">
                      Дневно използване
                    </p>
                    {USAGE_ROWS.map(({ key, label }) => {
                      const counter = planStatus.usage[key];
                      // A server payload missing this counter key (or a
                      // limit of 0, e.g. a misconfigured plan) used to throw
                      // here rather than just skip the row.
                      if (!counter) return null;
                      const pct = counter.limit > 0 ? Math.min(100, (counter.used / counter.limit) * 100) : 0;
                      const exhausted = counter.remaining === 0;
                      return (
                        <div key={key} className="space-y-1">
                          <div className="flex items-baseline justify-between gap-2">
                            <span className="text-caption text-ink-muted">{label}</span>
                            <span
                              className={cn(
                                'tnum text-caption font-semibold',
                                exhausted ? 'text-danger' : 'text-ink'
                              )}
                            >
                              {counter.used}/{counter.limit}
                            </span>
                          </div>
                          <div className="h-1 overflow-hidden rounded-full bg-sunken">
                            <div
                              className={cn(
                                'h-full rounded-full transition-[width] duration-500',
                                exhausted ? 'bg-danger' : 'bg-brand'
                              )}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                    <SheetClose asChild>
                      <Button
                        variant="soft"
                        className="w-full"
                        onClick={() => {
                          window.location.hash = 'upgrade';
                          openSettings();
                        }}
                      >
                        Виж Premium
                      </Button>
                    </SheetClose>
                  </div>
                </>
              )}
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
};

const Avatar: React.FC<{ user: { name?: string | null; picture?: string | null } | null }> = ({ user }) =>
  user?.picture ? (
    <img
      src={user.picture}
      alt=""
      referrerPolicy="no-referrer"
      className="size-7 rounded-md object-cover"
    />
  ) : (
    <span
      aria-hidden="true"
      className="inline-flex size-7 items-center justify-center rounded-md bg-brand-wash text-caption font-semibold text-brand-ink"
    >
      {user?.name?.[0]?.toUpperCase() ?? '?'}
    </span>
  );

/**
 * Phone connection status. Shows the linked device, or a button that opens the
 * settings panel where the device list lives.
 */
const PairingChip: React.FC = () => {
  const { linkedDevice, status } = useConnect();
  const { openSettings } = useSettings();

  if (linkedDevice) {
    return (
      <Badge variant="brand" className="hidden h-9 gap-1.5 px-2.5 xl:inline-flex">
        <DeviceMobileIcon weight="fill" />
        <span className="max-w-24 truncate normal-case">{linkedDevice.name}</span>
      </Badge>
    );
  }

  return (
    <button
      type="button"
      onClick={() => openSettings()}
      className="hidden h-9 items-center gap-1.5 rounded-lg border border-line bg-surface px-2 text-caption text-ink-muted transition-colors hover:text-ink xl:flex"
    >
      <DeviceMobileIcon className="size-4" />
      <span>{status === 'connecting' ? 'Свързване' : 'Свържи телефон'}</span>
    </button>
  );
};

export default AppNavbar;
