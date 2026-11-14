// Run against the integrated app: npm install --prefix .local/browser --no-save playwright
// BASE_URL=http://localhost:5173 node scripts/browser-smoke.cjs
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('../.local/browser/node_modules/playwright')

async function main() {
  let executablePath = process.env.CHROMIUM_PATH || chromium.executablePath()
  if (!fs.existsSync(executablePath) && process.env.LOCALAPPDATA) {
    const root = path.join(process.env.LOCALAPPDATA, 'ms-playwright')
    const versions = fs.readdirSync(root).filter((v) => /^chromium-\d+$/.test(v)).sort().reverse()
    executablePath = path.join(root, versions[0], 'chrome-win64', 'chrome.exe')
  }
  const browser = await chromium.launch({ headless: true, executablePath })
  try {
    const context = await browser.newContext()
    const page = await context.newPage()
    const base = process.env.BASE_URL || 'http://localhost:5173'
    const email = `browser-${Date.now()}@example.test`
    const password = 'browser-check-password-2026'
    const errors = []
    page.on('pageerror', (e) => errors.push(e.message))
    await page.goto(`${base}/login`)
    await page.getByRole('button', { name: 'Создать аккаунт', exact: true }).click()
    await page.getByLabel('Имя и фамилия').fill('Анна Проверка')
    await page.getByLabel('Email', { exact: true }).fill(email)
    await page.getByLabel('Пароль', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Зарегистрироваться' }).click()
    await page.getByText('Привет, Анна', { exact: false }).waitFor()
    assert.equal(await page.evaluate(() => localStorage.getItem('ai-buddy-auth')), null)
    assert.equal(await page.evaluate(() => navigator.serviceWorker.controller), null)
    const cookie = (await context.cookies()).find((c) => c.name === 'buddy_session')
    assert(cookie?.httpOnly && cookie.sameSite === 'Strict')
    for (const route of ['/timeline', '/contacts', '/kb', '/metrics', '/requests']) {
      await page.goto(base + route)
      await page.locator('.page h1').waitFor()
      await page.waitForLoadState('networkidle')
      assert(!await page.getByText('Сервис вернул данные в неожиданном формате').count(), route)
    }
    await page.goto(`${base}/requests/new/access`)
    await page.getByLabel('Система', { exact: true }).selectOption('confluence')
    await page.getByLabel('Для какой задачи нужен доступ').fill('Для чтения документации команды')
    await page.getByRole('button', { name: 'Предпросмотр и отправка' }).click()
    await page.getByRole('button', { name: 'Сохранить черновик' }).click()
    await page.waitForURL('**/requests')
    await page.getByText('Доступ: confluence', { exact: true }).waitFor()
    await page.reload()
    await page.getByText('Доступ: confluence', { exact: true }).waitFor()
    await page.getByRole('button', { name: 'Отправить', exact: true }).click()
    await page.getByText('Отправлен', { exact: true }).first().waitFor()
    await page.goto(`${base}/chat`)
    const chatInput = page.locator('textarea, input').filter({ visible: true }).first()
    await chatInput.fill('Что дальше по плану?')
    await chatInput.press('Enter')
    await page.getByText('Следующий шаг:', { exact: false }).waitFor()
    await page.goto(`${base}/team`)
    await page.getByText('Нет доступа', { exact: true }).waitFor()
    await page.goto(`${base}/`)
    await page.getByRole('button', { name: 'Выйти', exact: true }).click()
    await page.waitForURL('**/login')
    assert.equal((await context.request.get(base + '/api/auth/session')).status(), 401)
    await page.getByLabel('Email', { exact: true }).fill(email)
    await page.getByLabel('Пароль', { exact: true }).fill('incorrect-password')
    await page.getByRole('button', { name: 'Войти', exact: true }).click()
    await page.getByRole('alert').filter({ hasText: 'Неверный email или пароль' }).waitFor()
    await page.getByLabel('Пароль', { exact: true }).fill(password)
    await page.getByRole('button', { name: 'Войти', exact: true }).click()
    await page.getByText('Привет, Анна', { exact: false }).waitFor()
    await page.reload()
    await page.getByText('Привет, Анна', { exact: false }).waitFor()
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`${base}/requests`)
    await page.getByText('Доступ: confluence', { exact: true }).waitFor()
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false)
    assert.deepEqual(errors, [])
    console.log('Browser smoke: registration, login, logout, reload, pages, access request, chat, RBAC and mobile passed')
    await context.close()
  } finally {
    await browser.close()
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1 })
