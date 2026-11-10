// Record the integrated application against a fresh, dedicated demo database.
import { chromium } from '@playwright/test';
import { mkdir, copyFile } from 'node:fs/promises';
import { resolve } from 'node:path';

if (!process.env.BASE_URL) throw new Error('Set BASE_URL to the integrated app with fresh demo data');
const out = resolve('../delivery');
await mkdir(resolve(out, 'screens'), { recursive: true });
await mkdir(resolve(out, 'video'), { recursive: true });
const browser = await chromium.launch({ channel: 'chrome' });
const context = await browser.newContext({
  viewport: { width: 1280, height: 1000 },
  recordVideo: { dir: resolve('test-results/live-recording'), size: { width: 1280, height: 1000 } },
});
const page = await context.newPage();
const video = page.video();
async function hold(ms = 2000) { await page.waitForTimeout(ms); }
async function login(user) {
  await page.getByRole('button', { name: new RegExp('Войти как ' + user) }).click();
  await page.getByText(user, { exact: true }).first().waitFor();
}
async function screenshot(name) {
  await hold(1000);
  await page.screenshot({ path: resolve(out, 'screens', name), fullPage: true });
}
try {
  await page.goto(process.env.BASE_URL);
  await hold();
  await login('intern-demo');
  await screenshot('01-start-no-access.png');
  await page.getByLabel('Текст вопроса').fill('Не могу начать первую задачу. Что делать?');
  await hold();
  await page.getByRole('button', { name: 'Спросить', exact: true }).click();
  await page.getByRole('button', { name: 'Подтвердить', exact: true }).waitFor();
  await hold();
  await page.getByRole('button', { name: 'Подтвердить', exact: true }).click();
  const card = page.getByTestId('progress-request-id');
  await card.waitFor();
  const id = (await card.innerText()).trim();
  await screenshot('02-request-created.png');
  await hold();
  await page.reload();
  await page.getByTestId('progress-request-id').filter({ hasText: id }).waitFor();
  await screenshot('03-restored-after-reload.png');
  await page.getByRole('button', { name: 'Выйти' }).click();
  await login('operator-demo');
  await page.getByLabel('Номер заявки').fill(id);
  await hold();
  await page.getByRole('button', { name: 'Одобрить заявку' }).click();
  await page.getByRole('status').filter({ hasText: 'approved' }).waitFor();
  await hold();
  await page.getByRole('button', { name: 'Выйти' }).click();
  await login('intern-demo');
  await page.getByTestId('decision-badge').filter({ hasText: 'Одобрена' }).waitFor();
  await screenshot('04-approved-waiting-access.png');
  await hold();
  await page.getByRole('button', { name: 'Выйти' }).click();
  await login('operator-demo');
  await page.getByLabel('Номер заявки').fill(id);
  await page.getByRole('button', { name: 'Выдать право' }).click();
  await page.getByRole('status').filter({ hasText: 'granted' }).waitFor();
  await hold();
  await page.getByRole('button', { name: 'Выйти' }).click();
  await login('intern-demo');
  await page.getByTestId('return-to-task').click();
  await page.getByTestId('return-recorded').waitFor();
  await screenshot('05-access-granted-next-step.png');
  await hold(3500);
  console.log('Recorded request', id);
} finally {
  await context.close();
  await browser.close();
}
await copyFile(await video.path(), resolve(out, 'video/demo.webm'));
console.log('Live recording saved');
