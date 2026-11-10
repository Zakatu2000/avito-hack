import { defineConfig } from '@playwright/test';

if (!process.env.BUDDY_LIVE_URL) throw new Error('Set BUDDY_LIVE_URL to the local integration build');
export default defineConfig({
  testDir: './e2e',
  testMatch: 'live-path.spec.ts',
  workers: 1,
  timeout: 45000,
  use: { baseURL: process.env.BUDDY_LIVE_URL, channel: 'chrome' },
});
