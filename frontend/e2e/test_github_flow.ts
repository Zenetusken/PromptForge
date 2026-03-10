// frontend/e2e/test_github_flow.ts
import { test, expect } from '@playwright/test';
import { seedAuth, clearAuth, reloadWithAuth } from './helpers';

// Store the access token so tests can re-seed auth after page.reload().
// seedAuth() unroutes the refresh intercept once the page has loaded, so any
// subsequent reload() would hit the real backend (→ 401 → auth cleared).
let authToken = '';

test.beforeEach(async ({ page }) => {
  authToken = await seedAuth(page);
  await expect(page.locator('nav[aria-label="Activity Bar"]')).toBeVisible({ timeout: 15_000 });
});

test.afterEach(async ({ page }) => {
  await clearAuth(page);
});

test('GitHub section shows Not connected when no token', async ({ page }) => {
  // Intercept health to enable GitHub OAuth (needed for "Not connected" branch)
  await page.route('**/api/health', async (route) => {
    const resp = await route.fetch();
    const body = await resp.json();
    await route.fulfill({ json: { ...body, github_oauth_enabled: true } });
  });

  // Intercept /auth/github/me to return connected=false
  await page.route('**/auth/github/me', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ connected: false, login: null, avatar_url: null }),
    });
  });

  // Re-seed auth before reload so the layout's silent-refresh gets the token
  // rather than hitting the real backend (which would return 401 and clear auth).
  await reloadWithAuth(page, authToken);
  await expect(page.locator('nav[aria-label="Activity Bar"]')).toBeVisible({ timeout: 15_000 });

  // Wait for the health check to complete — it sets githubOAuthEnabled which
  // controls whether the "Not connected" branch renders in NavigatorSettings.
  await page.waitForResponse((resp) => resp.url().includes('/api/health') && resp.status() === 200);

  // Open Settings panel by clicking the settings icon in the Activity Bar.
  await page.locator('button[aria-label="Settings"]').click();

  // Should show "Not connected" (not "GitHub App not configured")
  await expect(page.getByText(/not connected/i)).toBeVisible({ timeout: 10_000 });
});

test('simulated GitHub connected state shows username', async ({ page }) => {
  // Intercept health to enable GitHub OAuth
  await page.route('**/api/health', async (route) => {
    const resp = await route.fetch();
    const body = await resp.json();
    await route.fulfill({ json: { ...body, github_oauth_enabled: true } });
  });

  // Intercept the GitHub status endpoint to simulate connected state.
  // The layout calls fetchGitHubAuthStatus() which hits /auth/github/me.
  await page.route('**/auth/github/me', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        connected: true,
        login: 'mock-github-user',
        avatar_url: null,
      }),
    });
  });
  // Intercept the repos endpoint (layout fetches repos when connected)
  await page.route('**/api/github/repos', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
  // Intercept the linked-repo endpoint (layout calls fetchLinkedRepo after repos)
  await page.route('**/api/github/repos/linked', (route) => {
    route.fulfill({ status: 404, body: '' });
  });

  // Re-seed auth before reload — see comment in previous test.
  await reloadWithAuth(page, authToken);
  await expect(page.locator('nav[aria-label="Activity Bar"]')).toBeVisible({ timeout: 15_000 });

  // Open Settings panel by clicking the activity bar icon directly.
  // The github.username is populated by a $effect that runs when auth becomes true,
  // which triggers fetchGitHubAuthStatus(). The assertion timeout handles the race.
  await page.locator('button[aria-label="Settings"]').click();

  // NavigatorSettings shows github.username when connected
  await expect(page.getByText('mock-github-user')).toBeVisible({ timeout: 10_000 });
});
