"""Read-only agent port. All mutations remain in the authenticated HTTP layer."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import BoundedSemaphore


class AgentUnavailable(Exception):
    pass


class ScopedReadTools:
    def __init__(self, workspace):
        self._workspace = deepcopy(workspace)

    def current_task(self):
        return deepcopy(self._workspace["task"])

    def instruction(self):
        return deepcopy(self._workspace["source"])

    def effective_access(self):
        return self._workspace["effectiveAccess"]

    def current_request(self):
        return deepcopy(self._workspace["request"])


class DemoAgent:
    def respond(self, text, tools):
        task = tools.current_task()
        ticket = tools.current_request()
        source = tools.instruction()
        kind = "answer"
        if not task:
            kind, reply = "handoff", "Попросите наставника назначить первую задачу."
        elif tools.effective_access() == "granted":
            reply = f"Доступ подтверждён. Следующий шаг: {task['title']}. Если ссылка не открывается, уточните ошибку."
        elif ticket:
            steps = {"pending": "ожидает согласования", "approved": "одобрена, ожидаем выдачу права",
                     "rejected": "отклонена, уточните причину у наставника"}
            reply = f"Заявка {ticket['requestId']}: {steps[ticket['requestStatus']]}."
        elif tools.effective_access() == "missing" and any(
            word in text.casefold() for word in ("начать", "задач", "доступ", "откры", "репозит", "открыть")
        ):
            kind, reply = "propose_access", f"Для задачи «{task['title']}» нет доступа. Подготовить заявку на чтение?"
        else:
            kind, reply = "clarify", "Что именно не получается сделать в первой задаче?"
        return {"kind": kind, "text": reply, "sourceId": source["sourceId"] if source else None,
                "aiMode": "demo"}


class AgentRunner:
    """Bound both response time and outstanding calls; a provider must also set its own IO timeout."""
    def __init__(self, agent, timeout, mode):
        self.agent = agent
        self.timeout = timeout
        self.mode = mode
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="buddy-agent")
        self.slots = BoundedSemaphore(4)

    def respond(self, text, workspace):
        if not self.slots.acquire(blocking=False):
            raise AgentUnavailable("Agent busy")
        future = self.pool.submit(self.agent.respond, text, ScopedReadTools(workspace))
        future.add_done_callback(lambda _: self.slots.release())
        try:
            decision = future.result(timeout=self.timeout)
        except Exception as exc:
            raise AgentUnavailable("Agent did not respond") from exc
        source = workspace["source"]
        if (not isinstance(decision, dict)
                or set(decision) != {"kind", "text", "sourceId", "aiMode"}
                or decision["kind"] not in ("answer", "clarify", "handoff", "propose_access")
                or not isinstance(decision["text"], str) or not decision["text"].strip()
                or decision["aiMode"] != self.mode
                or decision["sourceId"] not in (None, source["sourceId"] if source else None)):
            raise AgentUnavailable("Invalid agent decision")
        return decision
