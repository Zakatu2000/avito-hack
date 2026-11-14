"""Persistent portal conversations: list/create/delete, history, grounding."""
from uuid import uuid4

PASSWORD = "test-password-very-long"


def register(client, name="Новый Стажёр"):
    response = client.post("/api/auth/register", json=dict(
        email=f"{uuid4().hex}@example.test", password=PASSWORD, name=name))
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    return data["user"], {"X-CSRF-Token": data["csrfToken"]}


def send(client, headers, text, conversation_id=None):
    payload = {"message": text}
    if conversation_id:
        payload["conversationId"] = conversation_id
    response = client.post("/api/chat", json=payload, headers=headers)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_conversation_crud_history_and_isolation(app, db):
    client, other = app.test_client(), app.test_client()
    _, headers = register(client, "Первый Стажёр")
    _, other_headers = register(other, "Второй Стажёр")

    reply = send(client, headers, "Как оформить отгул?")
    chat_id = reply["conversationId"]
    send(client, headers, "А если на две недели?", conversation_id=chat_id)

    chats = client.get("/api/chats").get_json()
    assert [c["id"] for c in chats] == [chat_id]
    assert chats[0]["title"] == "Как оформить отгул?"

    messages = client.get(f"/api/chats/{chat_id}/messages").get_json()
    assert [m["role"] for m in messages] == ["user", "bot", "user", "bot"]
    assert messages[0]["text"] == "Как оформить отгул?"

    # Чужой чат недоступен и не виден.
    assert other.get("/api/chats").get_json() == []
    assert other.get(f"/api/chats/{chat_id}/messages").status_code == 404
    assert other.post("/api/chat", json={"message": "привет", "conversationId": chat_id},
                      headers=other_headers).status_code == 404
    assert other.delete(f"/api/chats/{chat_id}", headers=other_headers).status_code == 404

    assert client.delete(f"/api/chats/{chat_id}", headers=headers).status_code == 204
    assert client.get("/api/chats").get_json() == []
    assert client.get(f"/api/chats/{chat_id}/messages").status_code == 404

    created = client.post("/api/chats", json={"title": "Вопросы про доступы"},
                          headers=headers)
    assert created.status_code == 201
    assert created.get_json()["title"] == "Вопросы про доступы"
    assert client.post("/api/chats", json={"title": "x" * 200}, headers=headers).status_code == 400


def test_greeting_is_adaptive_not_templated(app):
    client = app.test_client()
    _, headers = register(client, "Анна Тест")
    reply = send(client, headers, "Привет")
    assert reply["intentId"] == "greeting"
    assert "Анна" in reply["text"]
    assert "Не нашёл" not in reply["text"]


def test_irrelevant_query_abstains_without_random_sources(app):
    client = app.test_client()
    _, headers = register(client, "Анна Тест")
    reply = send(client, headers, "как приготовить борщ на кухне")
    assert "«как приготовить борщ на кухне»" in reply["text"]
    assert "Источник:" not in reply["text"]


def test_secret_message_is_not_persisted_in_chat_history(app):
    client = app.test_client()
    _, headers = register(client)
    secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
    reply = send(client, headers, f"Вот мой ключ: {secret}")
    messages = client.get(
        f"/api/chats/{reply['conversationId']}/messages").get_json()

    assert secret not in str(messages)
    assert messages[0]["text"] == "[сообщение скрыто проверкой безопасности]"


def test_download_troubleshooting_asks_for_relevant_details(app):
    client = app.test_client()
    _, headers = register(client)
    reply = send(client, headers, "Не могу скачать файл из системы")

    assert reply["intentId"] == "troubleshoot"
    assert "файл не скачивается" in reply["text"]
    assert "точный текст ошибки" in reply["text"]
    assert "Источник:" not in reply["text"]


def test_unfinished_step_is_reported_when_asking_next(app):
    client = app.test_client()
    user, headers = register(client, "Анна Тест")
    stages = client.get("/api/checklist").get_json()
    item = stages[0]["items"][0]
    client.post(f"/api/checklist/items/{item['id']}/status",
                json={"status": "in_progress"}, headers=headers)
    reply = send(client, headers, "Можно начать другую задачу, если эта не завершена?")
    assert item["title"] in reply["text"]
    assert "перейти к другой задаче" in reply["text"]


def test_chat_validation(app):
    client = app.test_client()
    _, headers = register(client)
    assert client.post("/api/chat", json={"message": "ok", "conversationId": "../etc"},
                       headers=headers).status_code == 400
    assert client.post("/api/chat", json={"message": "  "}, headers=headers).status_code == 400
    assert client.post("/api/chat", json={"message": "nul\x00byte"},
                       headers=headers).status_code == 400
    assert client.post("/api/chats", json={"title": 5}, headers=headers).status_code == 400
    assert client.post("/api/chats", json=[{"title": "not an object"}],
                       headers=headers).status_code == 400
