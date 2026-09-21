import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

export type ThemeMode = 'light' | 'dark';
export type DashboardLayout = 'coach' | 'classic';

type SettingsContextValue = {
  theme: ThemeMode;
  dashboardLayout: DashboardLayout;
  isSettingsOpen: boolean;
  openSettings: () => void;
  closeSettings: () => void;
  toggleTheme: () => void;
  setTheme: (theme: ThemeMode) => void;
  setDashboardLayout: (layout: DashboardLayout) => void;
};

const THEME_STORAGE_KEY = 'app_theme_mode';
const DASHBOARD_LAYOUT_KEY = 'app_dashboard_layout';
export const OPEN_SETTINGS_MODAL_EVENT = 'open-settings-modal';

const SettingsContext = createContext<SettingsContextValue | null>(null);

const getStoredTheme = (): ThemeMode => {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  return stored === 'dark' ? 'dark' : 'light';
};

const getStoredDashboardLayout = (): DashboardLayout => {
  const stored = localStorage.getItem(DASHBOARD_LAYOUT_KEY);
  return stored === 'classic' ? 'classic' : 'coach';
};

export const SettingsProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [theme, setThemeState] = useState<ThemeMode>(() => getStoredTheme());
  const [dashboardLayout, setDashboardLayoutState] = useState<DashboardLayout>(() => getStoredDashboardLayout());
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(DASHBOARD_LAYOUT_KEY, dashboardLayout);
  }, [dashboardLayout]);

  useEffect(() => {
    const onOpenSettings = () => setIsSettingsOpen(true);
    window.addEventListener(OPEN_SETTINGS_MODAL_EVENT, onOpenSettings);
    return () => window.removeEventListener(OPEN_SETTINGS_MODAL_EVENT, onOpenSettings);
  }, []);

  const value = useMemo<SettingsContextValue>(
    () => ({
      theme,
      dashboardLayout,
      isSettingsOpen,
      openSettings: () => setIsSettingsOpen(true),
      closeSettings: () => setIsSettingsOpen(false),
      toggleTheme: () => setThemeState((current) => (current === 'light' ? 'dark' : 'light')),
      setTheme: setThemeState,
      setDashboardLayout: setDashboardLayoutState,
    }),
    [theme, dashboardLayout, isSettingsOpen]
  );

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
};

export const useSettings = (): SettingsContextValue => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
};