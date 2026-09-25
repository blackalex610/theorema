import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

// End-to-end smoke tests: the production build (vite preview) against a real
// backend, both started here. The backend runs with ENVIRONMENT=production
// so the checks that only exist there (secret key, database URL, CORS) are
// part of what is tested.
//
//   npm run test:e2e
//
// E2E_DATABASE_URL points it at PostgreSQL (CI does); by default each run
// gets a fresh SQLite file. E2E_PYTHON picks the interpreter that has
// backend/requirements.txt installed.

const API_PORT = Number(process.env.E2E_API_PORT ?? 8010);
// Set on process.env so the worker processes inherit the same value instead
// of each creating a temp directory of their own.
process.env.E2E_DATABASE_URL ??= `sqlite:///${path.join(
  mkdtempSync(path.join(tmpdir(), 'smartnvo-e2e-')),
  'e2e.db'
)}`;

export default defineConfig({
  testDir: './e2e',
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:4173',
    locale: 'bg-BG',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'phone', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [
    {
      command: `${process.env.E2E_PYTHON ?? 'python3'} -m uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        ENVIRONMENT: 'production',
        SECRET_KEY: 'e2e-only-secret-key-0123456789abcdef0123456789abcdef',
        DATABASE_URL: process.env.E2E_DATABASE_URL,
        CORS_ORIGINS: 'http://127.0.0.1:4173',
        OPENAI_API_KEY: '',
        MEDIA_LOCAL_DIR: path.join(tmpdir(), 'smartnvo-e2e-media'),
      },
    },
    {
      command: 'npm run build && npx vite preview',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: { E2E_API_PORT: String(API_PORT) },
    },
  ],
});
