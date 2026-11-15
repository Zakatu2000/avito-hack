# AI-buddy «Первый PR» · Hack&Change 2026

Помощник стажёра Авито. Отвечает на вопросы об адаптации со ссылками на материалы, подсказывает следующий шаг и помогает оформить заявки. Стажёр видит статусы и историю, а наставник обрабатывает заявки и подтверждает этапы в разделе «Команда».

Версия для проверки находится в ветке [`integration/ai-buddy`](https://github.com/Zakatu2000/avito-hack/tree/integration/ai-buddy).

## Запуск

1. Установите Python 3.12, Node.js 20+ и PostgreSQL для Windows.
2. Дважды щёлкните [`start.cmd`](start.cmd) в папке проекта. При первом запуске установятся зависимости. Когда приложение будет готово, браузер откроет [http://localhost:5177](http://localhost:5177).
3. Чтобы остановить стенд, нажмите `Ctrl+C` в открытом окне запуска. Данные PostgreSQL и логи сохраняются в `.local/`.

Повторный запуск открывает уже работающий стенд. Чат запускается в деморежиме без ключа AI.

## Тестовые аккаунты

На чистой базе создайте два аккаунта по инструкции ниже. Адреса и пароли приведены для локального демостенда.

| Роль | Email | Пароль для демо | Где создать |
| --- | --- | --- | --- |
| Стажёр | `intern@example.test` | `DemoIntern-2026` | Кнопка «Создать аккаунт» на странице входа |
| Наставник | `mentor@example.test` | `DemoMentor-2026` | Команда ниже, пароль вводится дважды |

Для создания наставника после запуска стенда выполните в отдельном PowerShell из корня проекта:

```powershell
$env:PGPASSWORD = (Get-Content .local/preview-db-password -Raw).Trim()
$env:DATABASE_URL = 'postgresql://buddy@127.0.0.1:55441/avito_buddy_demo'
Push-Location backend
try {
    .\.venv\Scripts\python.exe -m server.accounts --email mentor@example.test --name "Demo Mentor" --role mentor
} finally {
    Pop-Location
    Remove-Item Env:PGPASSWORD, Env:DATABASE_URL
}
```

## Порядок проверки

1. Войдите как стажёр. Откройте «Кому обратиться» и введите «Не работает VPN». Рекомендация откроет форму техпомощи с категорией «VPN и сеть». Заполните и отправьте обращение.
2. Перейдите в чат и спросите «Нужен доступ к репозиторию». Откройте форму по кнопке в ответе, укажите обоснование и отправьте заявку. Обновите страницу «Запросы» и убедитесь, что заявка осталась в списке.
3. Войдите как наставник в другом профиле браузера или в приватном окне. В разделе «Команда» найдите очередь, возьмите техобращение в работу и предложите решение. В заявке на доступ нажмите «Согласовать», затем «Вынести решение».
4. Вернитесь в сессию стажёра. В «Запросах» проверьте статус «Выдан» и историю согласования, закройте техобращение после проверки. В чате снова спросите о доступе к репозиторию. Откройте «Путь адаптации», чтобы увидеть следующий шаг и оставшиеся блокировки.
5. Дополнительные сценарии доступны в «Запросах»: отгул, консультация с наставником и запрос учебного материала. Для консультации наставник согласует время и сохраняет итог. Для учебного запроса сначала выполните поиск по теме, затем отправьте заявку, по которой наставник может дать рекомендацию.

В деморежиме выдача доступа, консультации и учебные назначения имитируются внутри портала. Согласованные слоты хранятся в PostgreSQL.

## Тесты и покрытие

- **Фронтенд** — Node.js 20+, React 18.3.1, TypeScript 5.6.3, Vite 5.4.21 и Vitest 2.1.9. Версии фиксирует [package-lock.json](frontend/package-lock.json).
- **Backend** — Python 3.12, Flask 3.1.2, psycopg 3.2.10, Waitress 3.0.2, PostgreSQL. Последний замер выполнен на PostgreSQL 18.6. Зависимости записаны в [requirements.txt](backend/server/requirements.txt) и [pyproject.toml](backend/ai/pyproject.toml).

Из папки `frontend/`:

```sh
npm ci
npm run typecheck
npm run lint
npm run build
npm run test:coverage
```

Vitest записывает отчёты в `frontend/coverage/index.html` и `frontend/coverage/lcov.info`.

Из папки `backend/` установите зависимости для проверок в виртуальное окружение Python. Укажите `TEST_ADMIN_DATABASE_URL` для отдельного тестового PostgreSQL с правом создавать базы. Тесты создают временные базы и удаляют их после прогона.

```sh
python -m pip install -r server/requirements-test.txt -r contracts/requirements.txt -e "./ai[dev]"
python scripts/check.py
```

Скрипт проверяет API, Python, AI и демодиалоги. Отчёт Python записывается в `backend/reports/python-coverage.json`. Текущий замер опубликован в [отчёте о покрытии](COVERAGE.md). Результаты предыдущих прогонов описаны в [VALIDATION.md](VALIDATION.md).

Для проверки в Chromium откройте приложение через `start.cmd`, затем выполните из корня:

```powershell
npm install --prefix .local/browser --no-save playwright
node .local/browser/node_modules/playwright/cli.js install chromium
$env:BASE_URL = 'http://localhost:5177'
node scripts/browser-smoke.cjs
```

Расширенный проход включается через `BROWSER_EXTENDED=1`. Для шагов наставника передайте `BROWSER_MENTOR_EMAIL` и `BROWSER_MENTOR_PASSWORD` созданной учётной записи. Для отдельного сценария есть [проверка сохранности после перезапуска](docs/qa/restart.md).

## Спецификации и тестовые данные

- [SDD портала](backend/docs/sdd/portal.md) и [SDD агента](backend/docs/sdd/agent.md)
- [Контракт API](backend/contracts/openapi.yaml) и [примеры ответов](backend/contracts/examples)
- [Синтетические данные портала](backend/server/portal_fixtures) и [материалы базы знаний](backend/server/fixtures/knowledge_base.json)
- [Чек-лист адаптации](backend/server/fixtures/checklist_catalog.json) и [источники кейса](docs/avito-case-knowledge.md)
