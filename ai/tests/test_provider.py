from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from socketserver import TCPServer
from threading import Thread
import time

import pytest

from ai.classifier import OpenAIClassifier, ProviderError, parse_intent, classifier_from_env
from ai.context import Context


def payload(content='{"intent":"access_help"}', finish="stop"):
    return {"choices":[{"finish_reason":finish,"message":{"content":content}}]}


@pytest.mark.parametrize("data", [
    {}, {"choices":[]}, payload("not JSON"), payload('{"intent":"grant"}'),
    payload('{"intent":"access_help","tool":"grant"}'), payload('{"intent":null}'),
    payload(finish="length"), payload('[]'),
])
def test_malformed_or_incomplete_output_never_becomes_an_action(data):
    with pytest.raises(ProviderError):
        parse_intent(data)


@pytest.mark.parametrize("url", ["http://external.example/v1","file:///secret","https://user:pw@example.com/v1","https://example.com/v1?q=secret"])
def test_endpoint_validation(url):
    with pytest.raises(ValueError):
        OpenAIClassifier(url,"test","dummy")


@pytest.mark.parametrize("timeout,max_tokens", [(0,128),(float("nan"),128),(61,128),(8,1),(8,5000)])
def test_provider_limits(timeout,max_tokens):
    with pytest.raises(ValueError):
        OpenAIClassifier("https://example.com/v1","test","dummy",timeout,max_tokens)


@contextmanager
def provider(status=200, response=None, delay=0):
    seen = []
    class Server(HTTPServer):
        def server_bind(self):
            TCPServer.server_bind(self)
            self.server_name = "localhost"
            self.server_port = self.server_address[1]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
            time.sleep(delay)
            self.send_response(status)
            if status == 302:
                self.send_header("Location", "/should-not-receive-key")
            self.end_headers()
            try:
                self.wfile.write(response if response is not None else json.dumps(payload()).encode())
            except OSError:
                pass
        def log_message(self, *args):
            pass
    server = Server(("127.0.0.1",0),Handler)
    thread = Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1",seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def context():
    return Context({"taskId":"task-01","resourceId":"repo-intro","title":"Учебная задача"},
                   {"sourceId":"demo","excerpt":"Учебный порядок"}, "missing",
                   {"requestId":"private-ticket-id","requestStatus":"pending"})


def test_real_http_contract_does_not_send_ticket_id_or_secret_in_body():
    with provider() as (url,seen):
        intent = OpenAIClassifier(url,"test","dummy").classify("Не могу открыть",context())
    assert intent == "access_help"
    assert seen[0][0] == "/v1/chat/completions"
    body = seen[0][1]
    assert body["response_format"] == {"type":"json_object"}
    assert "private-ticket-id" not in json.dumps(body)
    assert "dummy" not in json.dumps(body)


@pytest.mark.parametrize("status", [401,429,500,302])
def test_provider_failures_are_safe_and_redirect_is_not_followed(status):
    with provider(status=status) as (url,seen):
        with pytest.raises(ProviderError) as error:
            OpenAIClassifier(url,"test","dummy").classify("Вопрос",context())
    assert "dummy" not in str(error.value)
    assert len(seen) == 1


@pytest.mark.parametrize("response", [b'bad JSON',b'x'*65537])
def test_invalid_response_body(response):
    with provider(response=response) as (url,_):
        with pytest.raises(ProviderError):
            OpenAIClassifier(url,"test","dummy").classify("Вопрос",context())


def test_socket_timeout_is_provider_failure():
    with provider(delay=.1) as (url,_):
        with pytest.raises(ProviderError):
            OpenAIClassifier(url,"test","dummy",timeout=.01).classify("Вопрос",context())


def test_live_factory_uses_only_explicit_environment(monkeypatch):
    monkeypatch.setenv("AI_MODE","live")
    monkeypatch.setenv("AI_MODEL","test-model")
    monkeypatch.setenv("AI_API_KEY","dummy")
    classifier,mode = classifier_from_env()
    assert mode == "live" and classifier.model == "test-model"
