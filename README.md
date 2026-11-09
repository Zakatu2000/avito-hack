# AI-buddy «Первый PR»

B1 · Контракт v1.0.0 для разработки веб-клиента и AI-модуля.

- [Публичный OpenAPI](contracts/openapi.yaml)
- [Синтетические JSON для макетов](contracts/examples)
- [Порт агента, права и переходы](contracts/agent.md)

Проверка спецификации и всех примеров из корня репозитория (Python 3.9+):

    python3 -m venv .venv
    .venv/bin/pip install -r contracts/requirements.txt
    .venv/bin/python contracts/tests/check_examples.py

Для первого демопрохода последовательно загрузите initial → proposal → pending → approved → granted. В approved решение уже принято, но фактического доступа ещё нет. Вариант rejected показывает отказ. Это контракт для F2/A2; запуск самого сервера появится при реализации B2–B4.
