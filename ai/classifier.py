"""Intent classification is read-only. A model cannot name an executable tool."""
import json
import math
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

INTENTS = frozenset(("access_help", "process_question", "technical_issue", "next_step",
                     "handoff", "out_of_scope", "unknown"))
PROMPT = (Path(__file__).parent / "intent_prompt.txt").read_text()


class ProviderError(Exception):
    """Safe public failure without provider payloads, credentials or raw user text."""


class RuleClassifier:
    """Reproducible demo behavior, deliberately limited to recognized phrases."""
    def classify(self, text, context):
        value = text.casefold()
        if any(word in value for word in ("чуж", "админ", "зарплат", "персональ", "ignore instructions")):
            return "out_of_scope"
        if any(word in value for word in ("наставник", "человек", "руководител")):
            return "handoff"
        if any(word in value for word in ("инструкци", "процедур", "порядок")):
            return "process_question"
        if any(word in value for word in ("тесты", "сборк", "компиля", "build")):
            return "technical_issue"
        if any(word in value for word in ("дальше", "следующ", "теперь", "одобр", "выдали")):
            return "next_step"
        if any(word in value for word in ("доступ", "репозит", "откры", "начать", "задач", "403", "разрешени", "запрет")):
            return "access_help"
        return "unknown"


def parse_intent(payload):
    try:
        choice = payload["choices"][0]
        if choice["finish_reason"] != "stop":
            raise ValueError("Incomplete result")
        decision = json.loads(choice["message"]["content"])
        if not isinstance(decision, dict) or set(decision) != {"intent"}:
            raise ValueError("Invalid decision")
        intent = decision["intent"]
        if not isinstance(intent, str) or intent not in INTENTS:
            raise ValueError("Unsupported intent")
        return intent
    except (KeyError, IndexError, TypeError, ValueError):
        raise ProviderError("Некорректный ответ AI-сервиса") from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenAIClassifier:
    def __init__(self, base_url, model, key, timeout=8, max_tokens=1024):
        parsed = urllib.parse.urlsplit(base_url)
        local = parsed.hostname in ("127.0.0.1", "localhost", "::1")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
            raise ValueError("AI_BASE_URL must use HTTPS or a loopback HTTP test service")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Invalid AI_BASE_URL")
        if not key or not model:
            raise ValueError("Set AI_API_KEY and AI_MODEL for live mode")
        if not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError("AI_TIMEOUT_SECONDS must be in (0, 60]")
        if not 64 <= max_tokens <= 4096:
            raise ValueError("AI_MAX_TOKENS must be between 64 and 4096")
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model, self.key = model, key
        self.timeout, self.max_tokens = timeout, max_tokens
        self.opener = urllib.request.build_opener(NoRedirect())

    def classify(self, text, context):
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps({
                    "question": text, "authorized_context": context.model_data(),
                }, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_tokens,
            "reasoning_effort": "low",
            "stream": False,
        }
        request = urllib.request.Request(self.url, data=json.dumps(data).encode(),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Provider response too large")
            return parse_intent(json.loads(raw))
        except (OSError, ValueError, urllib.error.URLError):
            raise ProviderError("AI-сервис временно недоступен") from None


def classifier_from_env():
    mode = os.environ.get("AI_MODE", "demo")
    if mode == "demo":
        return RuleClassifier(), mode
    if mode != "live":
        raise ValueError("AI_MODE must be demo or live")
    return OpenAIClassifier(
        os.environ.get("AI_BASE_URL", "https://api.z.ai/api/paas/v4"),
        os.environ.get("AI_MODEL", ""),
        os.environ.get("AI_API_KEY", ""),
        float(os.environ.get("AI_TIMEOUT_SECONDS", "8")),
        int(os.environ.get("AI_MAX_TOKENS", "1024")),
    ), mode
