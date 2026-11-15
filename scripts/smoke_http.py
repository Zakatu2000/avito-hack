"""Verify persisted portal state around an API restart on a local demo."""
import argparse
import http.cookiejar
import json
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener
from uuid import uuid4


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def verify(base_url, restart):
    client = build_opener(ProxyHandler({}), HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(path, data=None, *, csrf=None, expected=200):
        headers = {"Origin": base_url}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-CSRF-Token"] = csrf
        request = Request(base_url + path, headers=headers,
                          data=json.dumps(data).encode() if data is not None else None)
        try:
            response = client.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            check(response.status == expected, f"{path}: got HTTP {response.status}, expected {expected}")
            return json.load(response)

    check(call("/health") == {"status": "ok"}, "API is not ready")
    session = call("/api/auth/register", {
        "name": "Restart smoke", "email": f"restart-{uuid4().hex}@example.test",
        "password": uuid4().hex,
    }, expected=201)
    request = call("/api/requests/access", {
        "system": "confluence", "justification": "Synthetic acceptance test for API restart",
        "durationDays": 7, "saveDraft": True,
    }, csrf=session["csrfToken"], expected=201)
    request_id = request["id"]
    call(f"/api/requests/{request_id}/send", {}, csrf=session["csrfToken"])

    def saved_request():
        for ticket in call("/api/requests"):
            if ticket["id"] == request_id:
                return ticket
        raise AssertionError("Saved request was not found")

    before = saved_request()
    check(before["status"] == "sent", "Expected a sent request before restart")
    restart()
    check(call("/api/auth/session")["user"] == session["user"], "Session changed after restart")
    check(saved_request() == before, "Saved request changed after restart")
    print("API restart check passed: same session and sent access request")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:5177")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    url = urlsplit(base_url)
    if (url.scheme != "http" or url.hostname not in ("localhost", "127.0.0.1")
            or not url.port or url.path or url.query or url.fragment or url.username):
        parser.error("Supply an explicit local HTTP origin, such as http://localhost:5177")

    def restart():
        input("Stop the preview with Ctrl+C, double-click start.cmd, then press Enter when the app is ready. ")

    verify(base_url, restart)


if __name__ == "__main__":
    main()
