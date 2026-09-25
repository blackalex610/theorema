import { expect, test, type Page } from '@playwright/test';

// The first minutes of a new student, against the production build and a
// real backend: sign in as a guest, the one-time consent step, the
// dashboard. Every test fails on an uncaught error in the page.

let pageErrors: string[] = [];

// Each test is a different student, so each comes from its own address — as
// behind Vercel, which sets X-Forwarded-For. From one address, the guest
// sign-in limit (5 per 10 minutes) would stop the suite halfway.
function addressFor(testId: string): string {
  let hash = 0;
  for (const char of testId) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return `10.${(hash >>> 16) & 255}.${(hash >>> 8) & 255}.${hash & 255}`;
}

test.beforeEach(async ({ page }, testInfo) => {
  pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  await page.setExtraHTTPHeaders({ 'X-Forwarded-For': addressFor(testInfo.testId) });
});

test.afterEach(() => {
  expect(pageErrors, 'uncaught errors in the page').toEqual([]);
});

async function continueAsGuest(page: Page) {
  await page.getByRole('button', { name: 'Продължи като гост' }).click();
  await expect(page).toHaveURL(/\/consent$/);
  await expect(page.getByRole('heading', { name: 'Преди да започнеш' })).toBeVisible();
}

async function giveConsent(page: Page) {
  await page.getByLabel('На 14 или повече години съм').check();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'Продължи' }).click();
}

test('a new student signs in as a guest, consents once and reaches the dashboard', async ({ page }) => {
  await page.goto('/');
  await continueAsGuest(page);

  const submit = page.getByRole('button', { name: 'Продължи' });
  await expect(submit).toBeDisabled();

  await giveConsent(page);
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('button', { name: 'Меню на профила' })).toBeVisible();

  // Recorded on the server, not just in this tab: a reload goes straight
  // back to the dashboard.
  await page.reload();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole('button', { name: 'Меню на профила' })).toBeVisible();
});

test('a deep link survives signing in and the consent step', async ({ page }) => {
  await page.goto('/progress');
  await expect(page).toHaveURL(/\/$/);

  await continueAsGuest(page);
  await giveConsent(page);
  await expect(page).toHaveURL(/\/progress$/);
});

test('under 14, only a parent can give consent', async ({ page }) => {
  await page.goto('/');
  await continueAsGuest(page);

  await page.getByLabel('Под 14 години съм').check();
  await expect(page.getByText('За родител или настойник')).toBeVisible();
  const parentBox = page.getByRole('checkbox', { name: /Аз съм родител или настойник/ });
  await parentBox.check();
  await expect(page.getByRole('button', { name: 'Продължи' })).toBeEnabled();

  // Changing the answer clears the confirmation that went with it.
  await page.getByLabel('На 14 или повече години съм').check();
  await expect(page.getByRole('checkbox')).not.toBeChecked();
  await expect(page.getByRole('button', { name: 'Продължи' })).toBeDisabled();

  await page.getByLabel('Под 14 години съм').check();
  await parentBox.check();
  await page.getByRole('button', { name: 'Продължи' }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test('settings open, and Premium says payments are off until Stripe is set up', async ({ page }) => {
  await page.goto('/');
  await continueAsGuest(page);
  await giveConsent(page);
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole('button', { name: 'Меню на профила' }).click();
  await page.getByRole('menuitem', { name: 'Настройки' }).click();
  await expect(page.getByText('Месечен абонамент')).toBeVisible();
  await expect(page.getByText('Плащанията все още не са включени.')).toBeVisible();
});

test('the privacy policy and terms are public', async ({ page }) => {
  await page.goto('/privacy');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page).toHaveURL(/\/privacy$/);

  await page.goto('/terms');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expect(page).toHaveURL(/\/terms$/);
});

test('a student who hits the sign-in limit is told so in Bulgarian', async ({ page }, testInfo) => {
  const headers = { 'X-Forwarded-For': addressFor(`${testInfo.testId}-limited`) };
  await page.setExtraHTTPHeaders(headers);
  for (let i = 0; i < 5; i += 1) {
    expect((await page.request.post('/_/backend/auth/guest', { headers })).ok()).toBe(true);
  }

  await page.goto('/');
  await page.getByRole('button', { name: 'Продължи като гост' }).click();
  await expect(page.getByRole('alert')).toHaveText(/Прекалено много заявки/);
  await expect(page).toHaveURL(/\/$/);
});
