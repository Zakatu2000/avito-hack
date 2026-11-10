// Records the demo video against a REAL stand (Flask API + PostgreSQL).
// Usage: BASE_URL=http://127.0.0.1:5051 BUDDY_DEMO_OPERATOR=1 on the stand.
//   node scripts/record-demo-video.mjs
// Steps are paced (1-3 s holds) so key frames are readable: AI-mode badge,
// request id before/after reload, "approved, waiting for the right",
// next step after grant, return-to-task confirmation. Target length >= 60 s.
import { chromium } from '@playwright/test';
import { mkdirSync, readdirSync, copyFileSync, unlinkSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(here, '../../delivery/video');
mkdirSync(outDir, { recursive: true });

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:5051';

const startedAt = Date.now();
const browser = await chromium.launch({ channel: 'chrome' });
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  recordVideo: { dir: outDir, size: { width: 1280, height: 800 } },
});
const page = await context.newPage();
page.setDefaultTimeout(20000);

const pause = (ms) => page.waitForTimeout(ms);

async function type(text) {
  await page.getByLabel('Текст вопроса').click();
  await page.getByLabel('Текст вопроса').pressSequentially(text, { delay: 55 });
}

async function loginAsOperator() {
  await page.getByRole('button', { name: /Войти как operator-demo/ }).click();
  await page.getByLabel('Номер заявки').waitFor();
}

async function logout() {
  await page.getByRole('button', { name: 'Выйти' }).click();
  await page.getByRole('button', { name: /Войти как intern-demo/ }).waitFor();
  await pause(1200);
}

// 1. Start screen.
await page.goto(BASE + '/');
await page.evaluate(() => window.localStorage.clear());
await page.reload();
await pause(5000);

// 2. Intern logs in - AI mode badge is visible in the header.
await page.getByRole('button', { name: /Войти как intern-demo/ }).click();
await page.getByTestId('aimode-badge').waitFor();
await pause(4000);

// 3. Ask the first question (typed slowly, readable).
await type('Не могу начать первую задачу. Что делать?');
await pause(1500);
await page.getByRole('button', { name: 'Спросить', exact: true }).click();
await page.getByText(/нет доступа/i).first().waitFor();
await pause(4000);

// 4. Confirm the proposal -> request id appears.
await page.getByRole('button', { name: 'Подтвердить', exact: true }).click();
await page.getByTestId('progress-request-id').waitFor();
const requestId = (await page.getByTestId('progress-request-id').innerText()).trim();
await page.getByTestId('progress-card').scrollIntoViewIfNeeded();
await pause(4000);

// 5. Reload - the SAME request id is restored (server-persisted state).
await page.reload();
await page.getByTestId('progress-request-id').waitFor();
await page.getByTestId('progress-request-id').scrollIntoViewIfNeeded();
await pause(4000);

// 6. Operator approves (separate session).
await logout();
await loginAsOperator();
await page.getByLabel('Номер заявки').fill(requestId);
await pause(1200);
await page.getByRole('button', { name: 'Одобрить заявку' }).click();
await page.getByRole('status').getByText(/approved/i).waitFor();
await pause(3000);

// 7. Intern sees "approved, waiting for the right" - decision != access.
await logout();
await page.getByRole('button', { name: /Войти как intern-demo/ }).click();
await page.getByTestId('aimode-badge').waitFor();
await page.getByTestId('progress-card').getByRole('button', { name: 'Обновить состояние' }).click();
await page.getByTestId('wait-access-note').waitFor();
await page.getByTestId('progress-card').scrollIntoViewIfNeeded();
await pause(4500);

// 8. Operator grants the actual right.
await logout();
await loginAsOperator();
await page.getByLabel('Номер заявки').fill(requestId);
await pause(1000);
await page.getByRole('button', { name: 'Выдать право' }).click();
await page.getByRole('status').getByText(/granted/i).waitFor();
await pause(3000);

// 9. Intern refreshes - access confirmed, next step shown, return to task.
await logout();
await page.getByRole('button', { name: /Войти как intern-demo/ }).click();
await page.getByTestId('aimode-badge').waitFor();
await page.getByTestId('progress-card').getByRole('button', { name: 'Обновить состояние' }).click();
await page.getByTestId('return-to-task').waitFor();
await page.getByTestId('progress-card').scrollIntoViewIfNeeded();
await pause(4000);
await page.getByTestId('return-to-task').click();
await page.getByTestId('return-recorded').waitFor();
await pause(7000);

await context.close();
await browser.close();

const files = readdirSync(outDir).filter((f) => f.endsWith('.webm'));
if (files.length === 0) {
  console.error('NO VIDEO FILE');
  process.exit(1);
}
const latest = files
  .map((f) => ({ f, m: new Date(f.replace('.webm', '')) }))
  .sort((a, b) => b.m - a.m)[0].f;
const finalPath = resolve(outDir, 'demo.webm');
for (const f of files) {
  if (f === latest) copyFileSync(resolve(outDir, f), finalPath);
  else unlinkSync(resolve(outDir, f));
}
console.log('VIDEO SAVED:', finalPath);
console.log('REQUEST ID SHOWN:', requestId);
console.log('RECORDING ELAPSED (s):', Math.round((Date.now() - startedAt) / 1000));
