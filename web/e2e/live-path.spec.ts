import { expect, test } from '@playwright/test';

test.skip(!process.env.BUDDY_LIVE_URL, 'Use playwright.live.config.ts with a dedicated demo database');

test('real API keeps one request across reload, approval and access issuance', async ({ page, browser }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Войти как intern-demo/ }).click();
  await page.getByLabel('Текст вопроса').fill('Не могу начать первую задачу. Что делать?');
  await page.getByRole('button', { name: 'Спросить', exact: true }).click();
  await page.getByRole('button', { name: 'Подтвердить', exact: true }).click();
  const request = page.getByTestId('progress-request-id');
  await expect(request).toBeVisible();
  const id = (await request.innerText()).trim();
  await page.reload();
  await expect(page.getByTestId('progress-request-id')).toHaveText(id);

  const operator = await browser.newContext({ baseURL: process.env.BUDDY_LIVE_URL });
  const control = await operator.newPage();
  await control.goto('/');
  await control.getByRole('button', { name: /Войти как operator-demo/ }).click();
  await control.getByLabel('Номер заявки').fill(id);
  await control.getByRole('button', { name: 'Одобрить заявку' }).click();
  await expect(control.getByRole('status')).toContainText('approved');
  await page.getByTestId('progress-card').getByRole('button', { name: 'Обновить состояние' }).click();
  await expect(page.getByTestId('decision-badge')).toHaveText('Одобрена');
  await expect(page.getByTestId('progress-access-badge')).toHaveText('Отсутствует');

  await control.getByRole('button', { name: 'Выдать право' }).click();
  await expect(control.getByRole('status')).toContainText('granted');
  await page.getByTestId('progress-card').getByRole('button', { name: 'Обновить состояние' }).click();
  await expect(page.getByTestId('progress-access-badge')).toHaveText('Подтверждён сервером');
  await page.getByTestId('return-to-task').click();
  await expect(page.getByTestId('return-recorded')).toBeVisible();
  await page.screenshot({ path: 'test-results/live-granted.png', fullPage: true });
  await operator.close();
});
