import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(here, '../../delivery/screens');
mkdirSync(outDir, { recursive: true });

const BASE = process.env.BASE_URL ?? 'http://127.0.0.1:5173';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2 });

async function clean() {
  await page.goto(BASE);
  await page.evaluate(() => window.localStorage.clear());
  await page.reload();
}

async function shot(name) {
  await page.waitForTimeout(300);
  await page.screenshot({ path: resolve(outDir, name), fullPage: false });
  console.log('saved', name);
}

await clean();

await page.getByRole('button', { name: 'Войти как Вася Стажёр' }).click();
await page.getByText('Настроить CI для учебного сервиса').waitFor();
await shot('01-start-no-access.png');

await page.getByLabel('Текст вопроса').fill('Не могу начать первую задачу. Что делать?');
await page.getByRole('button', { name: 'Спросить' }).click();
await page.getByText(/Уточню, чтобы помочь точно/).waitFor();
await page.getByLabel('Текст вопроса').fill('Про репозиторий, он не открывается');
await page.getByRole('button', { name: 'Спросить' }).click();
await page.getByTestId('proposal-PRP-77').waitFor();
await page.getByRole('button', { name: 'Подтвердить' }).click();
await page.getByText(/Заявка создана: REQ-2026-0142/).waitFor();
await shot('02-request-created.png');

await page.reload();
await page.getByTestId('progress-request-id').waitFor();
await shot('03-restored-after-reload.png');

await page.getByRole('button', { name: 'Выйти' }).click();
await page.getByRole('button', { name: 'Войти как Демооператор' }).click();
await page.getByTestId('demo-panel').getByRole('button', { name: 'Одобрить заявку' }).click();
await page.getByRole('button', { name: 'Выйти' }).click();
await page.getByRole('button', { name: 'Войти как Вася Стажёр' }).click();
await page.getByTestId('wait-access-note').waitFor();
await shot('04-approved-waiting-access.png');

await page.getByRole('button', { name: 'Выйти' }).click();
await page.getByRole('button', { name: 'Войти как Демооператор' }).click();
await page.getByTestId('demo-panel').getByRole('button', { name: 'Выдать право' }).click();
await page.getByRole('button', { name: 'Выйти' }).click();
await page.getByRole('button', { name: 'Войти как Вася Стажёр' }).click();
await page.getByRole('button', { name: 'Обновить состояние' }).first().click();
await page.getByTestId('return-to-task').waitFor();
await shot('05-access-granted-next-step.png');

await browser.close();
console.log('DONE');
