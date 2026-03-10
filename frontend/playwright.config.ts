// frontend/playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/test_*.ts',
  timeout: 45_000,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html', { open: 'never' }]],

  use: {
    baseURL: 'http://localhost:4173',
    viewport: { width: 1280, height: 800 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: [
    {
      // FastAPI backend with test mode on — relative path from frontend/
      command: 'bash -c "cd ../backend && source .venv/bin/activate && python -m uvicorn app.main:asgi_app --host 0.0.0.0 --port 8099"',
      url: 'http://localhost:8099/api/health',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: {
        TESTING: 'true',
        DATABASE_URL: 'sqlite+aiosqlite:///./e2e_test.db',
        SECRET_KEY: 'e2e-test-secret-32chars-minimum!!',
        GITHUB_TOKEN_ENCRYPTION_KEY: 'Zm9vYmFyYmF6cXV4cXV4cXV4cXV4cXV4cXV4cXU=',
        JWT_SECRET: 'e2e-jwt-secret-at-least-32-chars!!',
        JWT_REFRESH_SECRET: 'e2e-refresh-secret-at-least-32!!',
      },
    },
    {
      // SvelteKit production preview — proxy forwarded to E2E backend port
      command: 'npm run preview -- --port 4173',
      url: 'http://localhost:4173',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: {
        VITE_BACKEND_PORT: '8099',
      },
    },
  ],
});
