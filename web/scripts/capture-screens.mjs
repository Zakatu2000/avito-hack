// Captures the five delivery screenshots against a REAL stand
// (Flask API + PostgreSQL, demo mode).
// Usage: BASE_URL=http://127.0.0.1:5051 node scripts/capture-screens.mjs
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(here, '../../delivery/screens');
mkdirSync(outDir, { recursive: true });

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:5051';

const browser = await chromium.launch({ channel: 'chrome' });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 });
page.setDefaultTimeout(20000);

async function shot(name) {
  await page.waitForTimeout(400);
  await page.screenshot({ path: resolve(outDir, name), fullPage: false });
  console.log('saved', name);
}

async function loginIntern() {
  await page.getByRole('button', { name: /Войти как intern-demo/ }).click();
  await page.getByTestId('aimode-badge').waitFor();
}

async function loginOperator() {
  await page.getByRole('button', { name: /Войти как operator-demo/ }).click();
  await page.getByLabel('Номер заявки').waitFor();
}

async function logout() {
  await page.getByRole('button', { name: 'Выйти' }).click();
  await page.getByRole('button', { name: /Войти как intern-demo/ }).waitFor();
}

await page.goto(BASE + '/');
await page.evaluate(() => window.localStorage.clear());
await page.reload();

await loginIntern();
await shot('01-start-no-access.png');

await page.getByLabel('Текст вопроса').fill('Не могу начать первую задачу. Что делать?');
await page.getByRole('button', { name: 'Спросить', exact: true }).click();
await page.getByRole('button', { name: 'Подтвердить', exact: true }).click();
await page.getByTestId('progress-request-id').waitFor();
const requestId = (await page.getByTestId('progress-request-id').innerText()).trim();
await shot('02-request-created.png');

await page.reload();
await page.getByTestId('progress-request-id').waitFor();
await shot('03-restored-after-reload.png');

await logout();
await loginOperator();
await page.getByLabel('Номер заявки').fill(requestId);
await page.getByRole('button', { name: 'Одобрить заявку' }).click();
await page.getByRole('status').getByText(/approved/i).waitFor();
await logout();
await loginIntern();
await page.getByTestId('progress-card').getByRole('button', { name: 'Обновить состояние' }).click();
await page.getByTestId('wait-access-note').waitFor();
await shot('04-approved-waiting-access.png');

await logout();
await loginOperator();
await page.getByLabel('Номер заявки').fill(requestId);
await page.getByRole('button', { name: 'Выдать право' }).click();
await page.getByRole('status').getByText(/granted/i).waitFor();
await logout();
await loginIntern();
await page.getByTestId('progress-card').getByRole('button', { name: 'Обновить состояние' }).click();
await page.getByTestId('return-to-task').waitFor();
await shot('05-access-granted-next-step.png');

await browser.close();
console.log('DONE, request id:', requestId);
