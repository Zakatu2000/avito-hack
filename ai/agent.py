"""Use model semantics to select a branch; render all operational facts from server state."""
import re

from ai.classifier import INTENTS, ProviderError, classifier_from_env
from ai.context import Context


class Agent:
    def __init__(self, classifier, mode):
        self.classifier, self.mode = classifier, mode

    def respond(self, text, tools):
        context = Context.from_tools(tools)
        intent = self.classifier.classify(text, context)
        if intent not in INTENTS:
            raise ProviderError("Некорректное намерение")
        task, source, access, ticket = context.task, context.source, context.access, context.ticket
        # A specific resource named in the question never changes the allowed target.
        named = re.findall(r"repo-[\w-]+", text.casefold())
        foreign = task and any(name != task["resourceId"].casefold() for name in named)
        kind, source_id = "answer", None
        if intent == "out_of_scope" or foreign:
            kind, reply = "handoff", "Могу помочь с вашей назначенной задачей. Дополнительные полномочия обсудите с наставником."
        elif intent == "handoff" or not task:
            kind, reply = "handoff", "Обратитесь к наставнику или руководителю команды. Контактов в доступных материалах пока нет."
        elif intent == "technical_issue":
            kind, reply = "clarify", "На каком шаге возникает ошибка и что написано в сообщении? Укажите учебный пример без секретов."
        elif intent == "process_question":
            if source:
                reply, source_id = "В доступной учебной инструкции указано: " + source["excerpt"], source["sourceId"]
            else:
                kind, reply = "handoff", "Разрешённая инструкция пока отсутствует. Уточните порядок у наставника."
        elif intent == "unknown":
            kind, reply = "clarify", "Что именно не получается сделать в первой задаче?"
        elif access == "granted":
            reply = f"Доступ подтверждён. Следующий шаг: {task['title']}. Если ссылка не открывается, уточните ошибку."
        elif ticket:
            steps = {"pending": "ожидает согласования", "approved": "одобрена, ожидаем выдачу права",
                     "rejected": "отклонена, уточните причину у наставника"}
            reply = f"Заявка {ticket['requestId']}: {steps[ticket['requestStatus']]}."
        elif access == "missing" and source:
            kind, reply = "propose_access", f"Для задачи «{task['title']}» нет доступа. Создать заявку на чтение назначенного репозитория?"
            source_id = source["sourceId"]
        else:
            kind, reply = "handoff", "Не удалось подтвердить доступ или найти инструкцию. Повторите проверку либо обратитесь к наставнику."
        return {"kind": kind, "text": reply, "sourceId": source_id, "aiMode": self.mode}


def create_agent():
    classifier, mode = classifier_from_env()
    return Agent(classifier, mode)
