# Avito Start: frontend + backend

Рабочая ветка `merge-backend-into-frontend` создана от `frontend`
(`84a4d9498ce10562fb7082bfe47a1977ed090455`). Сервер перенесён из `main`
(`431b9bfbfa3ef3063eb66d607817c87f49bfa852`) в `backend/`.
Старый `main/web` не включён. Исходный интерфейс находится в `frontend/`.

## Запуск через Docker

Из корня репозитория, при запущенном Docker Desktop:

```powershell
Copy-Item .env.example .env
# Укажите собственный POSTGRES_PASSWORD в .env (буквы и цифры для URL подключения).
docker compose up --build
```

Откройте **http://localhost:8080**. Зарегистрируйте аккаунт на странице входа.
API и PostgreSQL доступны контейнерам, их порты не публикуются наружу.
Состояние сохраняется в volume `buddy_pg`. Миграции и демо-каталог применяются
автоматически; повторный запуск не сбрасывает созданные аккаунты и заявки.

Создание наставника или руководителя (пароль запрашивается интерактивно):

```powershell
docker compose exec api python -m server.accounts --email mentor@example.com --name "Марина Ким" --role mentor
docker compose exec api python -m server.accounts --email lead@example.com --name "Олег Ветров" --role lead
```

Публичная регистрация всегда создаёт роль `intern`. Паролей по умолчанию для
новых аккаунтов нет. Подтверждение email и восстановление пароля пока не реализованы.
Для HTTPS задайте `SESSION_COOKIE_SECURE=1` и фактический `PUBLIC_ORIGIN`.

## Локальная разработка без Docker

Нужны Node.js 20+, Python 3.12 и отдельная PostgreSQL-база `avito_buddy_demo`.
Не используйте существующую базу другого приложения.

Первый терминал, из корня репозитория (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server/requirements-test.txt -r contracts/requirements.txt -e "./ai[dev]"
$env:DATABASE_URL='postgresql://buddy:YOUR_PASSWORD@127.0.0.1:5432/avito_buddy_demo'
$env:PUBLIC_ORIGIN='http://localhost:5173'
$env:PORTAL_PROTECT_LEGACY='1'
$env:PYTHONPATH=(Join-Path (Get-Location) 'ai')
.\.venv\Scripts\python.exe -m server.store migrate
.\.venv\Scripts\python.exe -m server.store seed
.\.venv\Scripts\python.exe -m waitress --listen=127.0.0.1:5050 --call server.app:create_app
```

Второй терминал, из корня:

```powershell
cd frontend
npm ci
$env:VITE_ENABLE_MSW='false'
node node_modules/vite/bin/vite.js --config vite.integrated.config.ts --port 5173 --strictPort
```

Откройте **http://localhost:5173**. Vite проксирует `/api/*` в `127.0.0.1:5050`.
`VITE_API_URL` оставьте пустым. Для другого порта поменяйте и `PUBLIC_ORIGIN`.
Сервер читает переменные процесса; корневой `.env` автоматически читает только Compose.

Создание наставника без Docker — из `backend/` с тем же `DATABASE_URL`:

```powershell
.\.venv\Scripts\python.exe -m server.accounts --email mentor@example.com --name "Марина Ким" --role mentor
```

Оригинальный автономный mock-режим сохранён: `VITE_ENABLE_MSW=true` и `npm run dev`
из `frontend/`. Он использует MSW/localStorage и тестовый выбор пользователя;
серверная авторизация при этом не используется. В интегрированной сборке mocks выключены.

## Проверки

```powershell
git status --short --branch
git diff --check frontend --
git diff --stat frontend --
git diff frontend -- frontend/
python scripts/verify_transfer.py

cd frontend
npm run build
npm run lint
npm run typecheck
npm run test

cd ../backend
$env:TEST_ADMIN_DATABASE_URL='postgresql://buddy:YOUR_PASSWORD@127.0.0.1:5432/postgres'
# Выделенный тестовый кластер: тесты создают и удаляют собственную временную БД.
.\.venv\Scripts\python.exe scripts/check.py
.\.venv\Scripts\python.exe -m pip check
```

Для браузерной проверки запустите полное приложение, затем из корня:

```powershell
npm install --prefix .local/browser --no-save playwright
# Если Chromium ещё не установлен:
node .local/browser/node_modules/playwright/cli.js install chromium
$env:BASE_URL='http://localhost:5173'
node scripts/browser-smoke.cjs
```

Тест создаёт отдельный аккаунт и заявку в выбранной локальной базе. Пользователей
наставника и руководителя он не создаёт. Дополнительные ручные сценарии и решения
по совместимости — в [INTEGRATION.md](INTEGRATION.md).

Полный список файлов — [TRANSFER_FILES.md](TRANSFER_FILES.md), результаты
проверок и ограничения окружения — [VALIDATION.md](VALIDATION.md).

## Сценарии портала

После `migrate` и `seed` стажёр может открыть план быстрого старта, искать материалы,
создавать пять типов заявок и видеть историю решений. Для демо учебной задачи
создайте наставника командой выше. В разделе «Команда» наставник назначает задачу
и подтверждает отметку начала. Доступы, слоты консультаций и учебные задачи
хранятся в PostgreSQL портала и обозначены как демо.

Для расширенного браузерного теста укажите `BROWSER_EXTENDED=1`. Укажите
`BROWSER_MENTOR_EMAIL` и `BROWSER_MENTOR_PASSWORD` локального тестового аккаунта,
чтобы включить браузерные шаги наставника. Используйте выделенную демобазу.
Контракты находятся в `backend/contracts/openapi.yaml`, правила чата и измерений —
в `backend/docs/sdd/portal.md`.
