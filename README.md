# AI-buddy «Первый PR»

B1 · Контракт v1.2.0 для разработки веб-клиента и AI-модуля.

- [Публичный OpenAPI](contracts/openapi.yaml)
- [Синтетические JSON для макетов](contracts/examples)
- [Порт агента, права и переходы](contracts/agent.md)

Проверка спецификации и всех примеров из корня репозитория (Python 3.9+):

    python3 -m venv .venv
    .venv/bin/pip install -r contracts/requirements.txt
    .venv/bin/python contracts/tests/check_examples.py

Для первого демопрохода последовательно загрузите initial → proposal → pending → approved → granted. В approved решение уже принято, но фактического доступа ещё нет. Вариант rejected показывает отказ. Эти примеры подходят для F2/A2. Сервер поддерживает вход, чтение рабочего пространства и подтверждение предложения с сохранением заявки. Маршрут диалога подключён к тому же серверу.

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

Тесты создают временные базы со случайными именами и удаляют только их. Проверяются границы доступа, состояние после перезапуска, повторный seed и сброс демоданных. Подтверждение и защита от дублей проверяются при одновременных запросах через независимые соединения.

## B3 · подтверждение заявки

Сервер подготавливает предложение для конкретного стажёра, назначения, его версии и ресурса. Только отдельное подтверждение создаёт заявку. Действующее предложение можно подготовить через внутреннюю функцию сервера; её вызывает обработчик диалога. Для ручной проверки используйте демобазу после migrate и seed. Войдите как intern-demo по инструкции выше и получите ID предложения:

    .venv/bin/python - <<'PYTHON'
    import os
    import psycopg
    from psycopg.rows import dict_row
    from server.access import create_proposal
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        if conn.info.dbname != "avito_buddy_demo":
            raise SystemExit("Для этого примера нужна avito_buddy_demo")
        print(create_proposal(conn, "intern-01")["proposalId"])
    PYTHON

Вставьте полученный ID и дважды выполните один запрос с одинаковым ключом:

    proposal_id='ID_ИЗ_ПРЕДЫДУЩЕЙ_КОМАНДЫ'
    curl -sS -X POST -b /tmp/first-pr-demo.cookies -H 'Idempotency-Key: demo-confirm-01' "http://127.0.0.1:5050/api/proposals/$proposal_id/confirm"
    curl -sS -b /tmp/first-pr-demo.cookies http://127.0.0.1:5050/api/workspace

В обоих ответах confirm и в workspace проверьте один requestId. Повтор после утраты ответа безопасен. Сохраняйте ключ для всех попыток подтвердить это предложение; для нового предложения используйте новый ключ. Сервер также объединяет одновременные подтверждения для одного активного доступа. Повтор старого подтверждения возвращает его исходный номер и текущий статус той заявки. GET workspace возвращает актуальную заявку стажёра.

Чужое и неизвестное предложение дают одинаковый 403. Устаревшая версия назначения или повтор ключа с другим предложением дают 409. Клиент обновляет рабочее пространство. Подтверждение не выдаёт право на ресурс: заявка в статусе pending и фактический доступ missing остаются разными полями.

## B4 · диалог через HTTP

После запуска миграций и входа как intern-demo отправьте вопрос:

    curl -sS -b /tmp/first-pr-demo.cookies -H 'Content-Type: application/json' --data @contracts/examples/question.json http://127.0.0.1:5050/api/messages

Возьмите proposal.proposalId из ответа, подтвердите через маршрут B3 и задайте тот же вопрос ещё раз. Ответ покажет сохранённый requestId. Клиент отображает aiMode, состояние ожидания, при 409 обновляет workspace и предлагает повторить вопрос; при 503 показывает ошибку интеграции.

По умолчанию используется явно маркированный детерминированный режим demo. Для подключения реализации A4 задайте BUDDY_AGENT_FACTORY как путь к фабрике Python (например, your_package.agent:create_agent). Фабрика без аргументов возвращает объект с respond(text, tools), который выдаёт словарь AgentDecision по contracts/agent.md и режим live. Модуль и ключ провайдера поставляет AI-разработчик. Ограничьте сетевой тайм-аут внутри адаптера; API ждёт до 10 секунд и допускает до четырёх незавершённых вызовов на процесс. Ошибка или тайм-аут дают 503 без создания предложения. В деморежим при ошибке сервер автоматически не переключается.

В onboarding_events записываются начало блокировки (первое подготовленное предложение по назначению) и создание заявки. Это наблюдаемые события прототипа; время появления проблемы до обращения стажёра неизвестно. Событие создания фиксируется в транзакции заявки.

## B5 · согласование в отдельной сессии

Для демонстрации перед запуском API задайте `export BUDDY_DEMO_OPERATOR=1`. Маршруты /demo работают только с выделенной демобазой или временной тестовой БД. Выполните путь B4 и B3 как стажёр, скопируйте requestId. В другом терминале войдите как оператор своей команды, используя отдельный файл cookie:

    curl -sS -c /tmp/first-pr-operator.cookies -H 'Content-Type: application/json' -d '{"username":"operator-demo","password":"training-only"}' http://127.0.0.1:5050/api/session
    request_id='ID_ИЗ_ОТВЕТА_CONFIRM'
    url="http://127.0.0.1:5050/demo/requests/$request_id"
    curl -sS -b /tmp/first-pr-operator.cookies "$url"
    curl -sS -b /tmp/first-pr-operator.cookies -H 'Content-Type: application/json' -d '{"action":"approve"}' "$url"

Обновите workspace с cookie стажёра: решение approved, право missing. Затем выдайте право:

    curl -sS -b /tmp/first-pr-operator.cookies -H 'Content-Type: application/json' -d '{"action":"grant"}' "$url"

Повторите вопрос стажёра: теперь помощник покажет следующий шаг. В альтернативном прогоне для ожидающей заявки используйте action=reject. Для новой демонстрации оператор может явно сбросить синтетические учётные записи, включая обе сессии:

    curl -sS -b /tmp/first-pr-operator.cookies -H 'Content-Type: application/json' -d '{"confirm":"reset-demo"}' http://127.0.0.1:5050/demo/reset

[Схема интеграций и условия перехода к пилоту](docs/integration.md).

## B6 · запуск серверной сборки через Docker Compose

Скопируйте `.env.example` в `.env`. Это локальные демонстрационные реквизиты. Порт публикуется только на 127.0.0.1. Включите BUDDY_DEMO_OPERATOR=1 для показа согласования.

    cp .env.example .env
    docker compose up --build -d api
    docker compose ps
    curl -fsS http://127.0.0.1:5050/health

Миграции и синтетические данные устанавливаются при старте. Данные находятся в именованном томе PostgreSQL. Для штатной остановки используйте `docker compose down`. После следующего старта данные сохраняются.

Сейчас Compose запускает API и PostgreSQL. Интерфейс Web 1 и внешний AI-адаптер ещё ожидаются. Для демо текущего сервера используйте HTTP-примеры выше.

### Единая проверка

Для проверки контейнером создайте папку отчётов и передайте свой UID/GID для записи результатов на Linux:

    mkdir -p reports
    LOCAL_UID=$(id -u) LOCAL_GID=$(id -g) docker compose --profile checks run --build --rm checks

Локальная проверка с уже запущенным тестовым PostgreSQL:

    .venv/bin/pip install -r server/requirements-test.txt -r contracts/requirements.txt
    export TEST_ADMIN_DATABASE_URL='postgresql://buddy:local-demo-only@127.0.0.1:55432/postgres'
    .venv/bin/python scripts/check.py

Команда проверяет контракт, запускает тесты и измеряет строки выполняемого Python-кода. Отчёты находятся в reports/python-coverage.json и reports/summary.json. Зависимости и тесты исключены. SQL-миграции проверяются интеграционными тестами, coverage.py измеряет Python. Покрытие доступного прикладного кода должно быть строго больше 80%.

При добавлении ai/ запуск включает ai/tests и измеряет ai/ вместе с server/ одним инструментом. При добавлении web/ ожидается `npm run test:coverage` в этой папке, свежий отчёт web/coverage/lcov.info со всеми файлами web/src. Пути SF относительны web/ либо абсолютны. Определения типов *.d.ts и тесты исключены из инвентаризации. Генерируемые файлы не помещайте в эти каталоги прикладного кода.

В итоговом проценте суммируются покрытые и учитываемые строки, каждый файл включается один раз. Проверка полноты требует измерений для всех исходников. Для финальной сборки выполните `python scripts/check.py --release`: отсутствие web/ или ai/ завершит проверку ошибкой. Эти части должны быть добавлены до полной приёмки B6.
