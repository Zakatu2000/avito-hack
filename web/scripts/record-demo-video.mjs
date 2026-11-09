import { chromium } from '@playwright/test';
import { mkdirSync, readdirSync, copyFileSync, unlinkSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(here, '../../delivery/video');
mkdirSync(outDir, { recursive: true });

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:5173';

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  recordVideo: { dir: outDir, size: { width: 1280, height: 800 } },
});
const page = await context.newPage();
page.setDefaultTimeout(15000);

const pause = (ms) => page.waitForTimeout(ms);

async function type(text) {
  await page.getByLabel('Текст вопроса').click();
  await page.getByLabel('Текст вопроса').pressSequentially(text, { delay: 45 });
}

await page.goto(BASE);
await page.evaluate(() => window.localStorage.clear());
await page.reload();
await pause(900);

await page.getByRole('button', { name: 'Войти как Вася Стажёр' }).click();
await page.getByText('Настроить CI для учебного сервиса').waitFor();
await pause(1200);

await type('Не могу начать первую задачу. Что делать?');
await pause(600);
await page.getByRole('button', { name: 'Спросить' }).click();
await page.getByText(/Уточню, чтобы помочь точно/).waitFor();
await pause(1200);

await type('Про репозиторий, он не открывается');
await pause(600);
await page.getByRole('button', { name: 'Спросить' }).click();
await page.getByTestId('proposal-PRP-77').waitFor();
await pause(1200);

await page.getByRole('button', { name: 'Подтвердить' }).click();
await page.getByText(/Заявка создана: REQ-2026-0142/).waitFor();
await page.getByTestId('progress-card').scrollIntoViewIfNeeded();
await pause(1600);

await page.reload();
await page.getByTestId('progress-request-id').waitFor();
await page.getByTestId('progress-card').scrollIntoViewIfNeeded();
await pause(1600);

await page.getByRole('button', { name: 'Выйти' }).click();
await page.getByRole('button', { name: 'Войти как Демооператор' }).click();
await page.getByTestId('demo-panel').waitFor();
await pause(1000);
await page.getByTestId('demo-panel').getByRole('button', { name: 'Одобрить заявку' }).click();
await pause(1000);

await page.getByRole('button', { name: 'Выйти' }).click();
await page.getByRole('button', { name: 'Войти как Вася Стажёр' }).click();
await page.getByTestId('wait-access-note').waitFor();
await page.getByTestId('progress-card').scrollIntoViewIfNeeded();
await pause(1600);

await page.getByRole('button', { name: 'Выйти' }).click();
await page.getByRole('button', { name: 'Войти как Демооператор' }).click();
await page.getByTestId('demo-panel').waitFor();
await pause(800);
await page.getByTestId('demo-panel').getByRole('button', { name: 'Выдать право' }).click();
await pause(1000);

await page.getByRole('button', { name: 'Выйти' }).click();
await page.getByRole('button', { name: 'Войти как Вася Стажёр' }).click();
await page.getByRole('button', { name: 'Обновить состояние' }).first().click();
await page.getByTestId('return-to-task').waitFor();
await page.getByTestId('return-to-task').scrollIntoViewIfNeeded();
await pause(1000);
await page.getByTestId('return-to-task').click();
await page.getByTestId('return-recorded').waitFor();
await pause(2000);

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
