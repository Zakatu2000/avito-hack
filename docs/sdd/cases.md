# Связь спецификаций и проверок

| Требование | Случаи / тесты | Наблюдаемое доказательство |
| --- | --- | --- |
| Разобрать обычный вопрос о первой задаче | start, repo, forbidden-link | propose_access, разрешённый источник, записи заявки нет |
| Уточнить неопределённость | unclear, technical | clarify с вопросом о шаге или симптоме |
| Отвечать по разрешённым материалам | process; test_source_is_copy_of_permitted_instruction_and_tools_are_read_only | Разрешённый фрагмент и sourceId |
| Передать человеку и ограничить область | human, foreign, role-injection | handoff, чужой объект не подтверждается |
| Восстановить состояние | pending, false-approval, approved, granted, rejected | Сохранённый ID, фактический статус и право |
| Фильтровать контекст до LLM | test_real_http_contract_does_not_send_ticket_id_or_secret_in_body | Внешний JSON содержит только разрешённые факты |
| Обрабатывать ошибки провайдера | test_provider_failures_are_safe_and_redirect_is_not_followed, test_socket_timeout_is_provider_failure | ProviderError, отсутствие утечки ключа |
| Валидировать модель | test_malformed_or_incomplete_output_never_becomes_an_action | Отклонение невалидного JSON, лишних полей и неизвестной категории |
| Пройти обычный маршрут API | server/tests/test_ai_integration.py | Вопрос → предложение → подтверждение → сохранённая заявка |
| Учесть эффект для пилота | test_grant_event_is_unique_and_separate_from_approval | Одобрение без события права, затем одно событие фактической выдачи |

Основной набор — ai/evals/cases.json. Выполняется отдельно в demo и, по явной команде, в live. Реальные внешние smoke-запросы 10 ноября выполнены только для трёх синтетических ситуаций с отдельным разрешением пользователя. Они не устанавливают точность на всех возможных вопросах.
