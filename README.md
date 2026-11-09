# AI-buddy «Первый PR»

B1 · Контракт v1.0.1 для разработки веб-клиента и AI-модуля.

- [Публичный OpenAPI](contracts/openapi.yaml)
- [Синтетические JSON для макетов](contracts/examples)
- [Порт агента, права и переходы](contracts/agent.md)

Проверка спецификации и всех примеров из корня репозитория (Python 3.9+):

    python3 -m venv .venv
    .venv/bin/pip install -r contracts/requirements.txt
    .venv/bin/python contracts/tests/check_examples.py

Для первого демопрохода последовательно загрузите initial → proposal → pending → approved → granted. В approved решение уже принято, но фактического доступа ещё нет. Вариант rejected показывает отказ. Эти примеры подходят для F2/A2. Сервер B2 уже реализует вход и восстановление состояния. Создание заявок и диалог появятся в B3–B4.

## Сервер B2 · локальный запуск

Проверено с Python 3.12 и PostgreSQL 16. Из корня репозитория установите зависимости:

    python3.12 -m venv .venv
    .venv/bin/python -m pip install -r server/requirements-test.txt

Создайте отдельную PostgreSQL-базу `avito_buddy_demo`, доступную вашему локальному пользователю. Если PostgreSQL уже установлен: `createdb avito_buddy_demo`, затем `export DATABASE_URL='postgresql:///avito_buddy_demo'`. Альтернатива при установленном Docker — новый контейнер с синтетическими реквизитами для локального демо:

    docker run -d --name first-pr-b2-db -e POSTGRES_DB=avito_buddy_demo -e POSTGRES_USER=buddy -e POSTGRES_PASSWORD=local-demo-only -p 127.0.0.1:55432:5432 postgres:16
    export DATABASE_URL='postgresql://buddy:local-demo-only@127.0.0.1:55432/avito_buddy_demo'

После готовности базы выполните:

    .venv/bin/python -m server.store migrate
    .venv/bin/python -m server.store seed
    .venv/bin/python -m waitress --listen=127.0.0.1:5050 --call server.app:create_app

### Учебные аккаунты

Общий тестовый пароль — `training-only`. Все имена, команды, права и инструкции синтетические.

| Логин | Состояние при первом входе |
| --- | --- |
| intern-demo | task-01, repo-intro: доступ отсутствует, заявок нет |
| intern-ready | task-02, repo-private: право выдано, своя одобренная заявка req-02 |
| intern-new | Назначение отсутствует, доступ неизвестен |
| operator-demo | Отдельная роль демооператора, без рабочего пространства стажёра |

Сессия привязана к записи пользователя в БД и действует восемь часов. Запрос в другом терминале:

    curl -sS -c /tmp/first-pr-demo.cookies -H 'Content-Type: application/json' --data @contracts/examples/login.json http://127.0.0.1:5050/api/session
    curl -sS -b /tmp/first-pr-demo.cookies http://127.0.0.1:5050/api/workspace

Перезапустите API с той же базой и повторите второй запрос. Для intern-demo результат соответствует contracts/examples/initial.json. Повторный seed сохраняет текущее состояние. Для возврата демоаккаунтов к исходным данным выполните `.venv/bin/python -m server.store reset-demo --confirm`. Сброс завершает их активные сессии.

### Проверка изоляции

Укажите подключение к отдельному локальному тестовому кластеру PostgreSQL с правом CREATEDB (например, для контейнера выше):

    export TEST_ADMIN_DATABASE_URL='postgresql://buddy:local-demo-only@127.0.0.1:55432/postgres'
    .venv/bin/python -m pytest -q server/tests

Тесты создают временные базы со случайными именами и удаляют только их. Проверяются границы доступа, состояние после перезапуска, повторный seed и сброс демоданных. Хранилище для предложений и заявок создано; операции создания и согласования будут реализованы в следующих задачах.
