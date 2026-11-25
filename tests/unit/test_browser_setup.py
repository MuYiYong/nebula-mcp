from __future__ import annotations

import asyncio
import http.client
import json
import socket
from urllib.parse import urlsplit

import pytest

from nebula_mcp import browser_setup
from nebula_mcp.browser_setup import BrowserSetup

_Reply = tuple[int, dict[str, str], bytes]


def _request(
    url: str,
    method: str = "GET",
    suffix: str = "",
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> _Reply:
    parts = urlsplit(url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=3)
    try:
        conn.request(method, parts.path + suffix, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def _raw(url: str, data: bytes) -> _Reply:
    parts = urlsplit(url)
    assert parts.hostname and parts.port
    with socket.create_connection((parts.hostname, parts.port), timeout=3) as conn:
        conn.sendall(data)
        with http.client.HTTPResponse(conn) as response:
            response.begin()
            return response.status, dict(response.getheaders()), response.read()


def _save_headers(url: str) -> dict[str, str]:
    return {
        "Origin": _origin(url),
        "Content-Type": "application/json",
        "Sec-Fetch-Site": "same-origin",
    }


def _origin(url: str) -> str:
    return f"http://{urlsplit(url).netloc}"


async def _wait_closed(url: str) -> None:
    parts = urlsplit(url)
    assert parts.hostname and parts.port
    async with _timeout(3):
        while True:
            try:
                _, writer = await asyncio.open_connection(parts.hostname, parts.port)
            except ConnectionRefusedError:
                return
            writer.close()
            await writer.wait_closed()
            await asyncio.sleep(0.01)


async def _state() -> dict[str, object]:
    return {"addresses": "example.invalid:9669", "has_password": True}


async def _accept(_: dict[str, object]) -> tuple[int, dict[str, object]]:
    return 200, {"ok": True}


class _timeout:
    """Tiny wait guard for Python 3.10 suites; no asyncio.timeout dependency."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    async def __aenter__(self) -> None:
        task = asyncio.current_task()
        assert task is not None
        self.handle = asyncio.get_running_loop().call_later(self.seconds, task.cancel)

    async def __aexit__(self, *_: object) -> None:
        self.handle.cancel()


@pytest.fixture
def urls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    captured: list[str] = []
    monkeypatch.setattr(browser_setup, "_open_browser", captured.append)
    # Mock data loading to isolate transport tests from another component's assets.
    monkeypatch.setattr(
        browser_setup,
        "_load_assets",
        lambda: {
            "": ("text/html; charset=utf-8", b"<h1>Connection setup</h1>"),
            "connection-setup.css": ("text/css; charset=utf-8", b"h1 { color: black }"),
            "connection-setup.js": ("text/javascript; charset=utf-8", b"'use strict';"),
        },
    )
    return captured


def test_assets_state_and_successful_save(urls: list[str]) -> None:
    async def run() -> None:
        loop = asyncio.get_running_loop()
        saved: list[dict[str, object]] = []

        async def read_state() -> dict[str, object]:
            assert asyncio.get_running_loop() is loop
            return await _state()

        async def save(body: dict[str, object]) -> tuple[int, dict[str, object]]:
            assert asyncio.get_running_loop() is loop
            saved.append(body)
            if len(saved) == 1:
                return 422, {
                    "ok": False,
                    "code": "INVALID",
                    "message": "Invalid input",
                    "field": "addresses",
                    "unexpected": "must not be returned",
                }
            return 200, {"ok": True, "password": "must not be returned"}

        setup = BrowserSetup()
        assert await setup.open(read_state, save) is None
        try:
            url = urls[0]
            parts = urlsplit(url)
            assert parts.hostname == "127.0.0.1" and parts.port
            assert parts.path.startswith("/setup/") and len(parts.path.split("/")[2]) >= 40
            assert parts.path.endswith("/") and not (parts.query or parts.fragment)
            for name, content_type in (
                ("", "text/html"),
                ("connection-setup.css", "text/css"),
                ("connection-setup.js", "text/javascript"),
                ("state", "application/json"),
            ):
                status, headers, body = await asyncio.to_thread(_request, url, "GET", name)
                assert status == 200 and body
                assert headers["Content-Type"].startswith(content_type)
                assert headers["Cache-Control"] == "no-store"
                assert headers["Referrer-Policy"] == "no-referrer"
                assert headers["X-Frame-Options"] == "DENY"
                assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
                assert "connect-src 'self'" in headers["Content-Security-Policy"]
                assert "Access-Control-Allow-Origin" not in headers
                assert "Location" not in headers
            assert json.loads(body) == await _state()

            data = {"addresses": "localhost:9669", "password": "fake-credential"}
            post_body = json.dumps(data).encode()
            status, _, body = await asyncio.to_thread(
                _request,
                url,
                "POST",
                "save",
                body=post_body,
                headers=_save_headers(url),
            )
            assert status == 422
            assert json.loads(body) == {
                "ok": False,
                "code": "INVALID",
                "message": "Invalid input",
                "field": "addresses",
            }
            status, _, body = await asyncio.to_thread(
                _request,
                url,
                "POST",
                "save",
                body=post_body,
                headers=_save_headers(url),
            )
            assert status == 200 and json.loads(body) == {"ok": True}
            assert saved == [data, data]
            await _wait_closed(url)
        finally:
            await setup.close()

    asyncio.run(run())


def test_exact_routes_hosts_methods_origins_and_header_framing(urls: list[str]) -> None:
    async def run() -> None:
        called = False

        async def save(body: dict[str, object]) -> tuple[int, dict[str, object]]:
            nonlocal called
            called = True
            return await _accept(body)

        setup = BrowserSetup()
        await setup.open(_state, save)
        try:
            url = urls[0]
            parts = urlsplit(url)
            for method, suffix, headers, status in (
                ("GET", "state?extra=1", {}, 404),
                ("GET", "state/", {}, 404),
                ("GET", "%73tate", {}, 404),
                ("GET", "../state", {}, 404),
                ("GET", "state", {"Host": f"localhost:{parts.port}"}, 403),
                ("GET", "state", {"Origin": "https://example.invalid"}, 403),
                ("GET", "state", {"Sec-Fetch-Site": "cross-site"}, 403),
                ("OPTIONS", "save", _save_headers(url), 405),
                ("GET", "save", {}, 404),
                ("POST", "state", _save_headers(url), 404),
                ("POST", "save", {"Content-Type": "application/json"}, 403),
                ("POST", "save", {**_save_headers(url), "Origin": "null"}, 403),
                ("POST", "save", {**_save_headers(url), "Origin": _origin(url) + "/"}, 403),
                ("POST", "save", {**_save_headers(url), "Origin": "https://example.invalid"}, 403),
                ("POST", "save", {**_save_headers(url), "Host": "example.invalid"}, 403),
                ("POST", "save", {**_save_headers(url), "Content-Type": "text/plain"}, 415),
                ("POST", "save", {**_save_headers(url), "Transfer-Encoding": "chunked"}, 400),
                ("POST", "save", {**_save_headers(url), "Content-Encoding": "gzip"}, 400),
                ("POST", "save", {**_save_headers(url), "Expect": "100-continue"}, 400),
            ):
                result, response_headers, body = await asyncio.to_thread(
                    _request,
                    url,
                    method,
                    suffix,
                    headers=headers,
                    body=b"{}" if method == "POST" else None,
                )
                assert result == status, (method, suffix, headers, body)
                assert json.loads(body)["ok"] is False
                assert "Access-Control-Allow-Origin" not in response_headers
                assert "Location" not in response_headers

            tail = (
                f"Host: {parts.netloc}\r\nOrigin: {_origin(url)}\r\n"
                "Content-Type: application/json\r\nContent-Length: 2\r\n"
            )
            for target, headers, status in (
                ("/" + parts.path + "save", tail, 400),
                (url + "save", tail, 404),
                ("/setup/wrong-secret/save", tail, 404),
                (parts.path + "save", tail + f"hOst: {parts.netloc}\r\n", 400),
                (parts.path + "save", tail + f"origin: {_origin(url)}\r\n", 400),
                (parts.path + "save", tail + "content-length: 2\r\n", 400),
                (parts.path + "save", tail + "content-type: application/json\r\n", 400),
                (parts.path + "save", tail + "X-Test: one\r\n two\r\n", 400),
                (parts.path + "save", tail[tail.find("\r\n") + 2 :], 403),
                (parts.path + "save", tail[: tail.rfind("Content-Length:")], 411),
            ):
                raw = f"POST {target} HTTP/1.1\r\n{headers}\r\n{{}}".encode()
                status_actual, _, body = await asyncio.to_thread(_raw, url, raw)
                assert status_actual == status
                assert json.loads(body)["ok"] is False
            assert not called
        finally:
            await setup.close()

    asyncio.run(run())


@pytest.mark.parametrize(
    ("data", "status"),
    [
        (b"[]", 400),
        (b"null", 400),
        (b"{", 400),
        (b'{"x":1,"x":2}', 400),
        (b'{"x":NaN}', 400),
        (b"{\xff}", 400),
        (b"[" * 3000, 400),
        (b" " * (16 * 1024 + 1), 413),
    ],
)
def test_rejects_invalid_or_oversize_json(urls: list[str], data: bytes, status: int) -> None:
    async def run() -> None:
        called = False

        async def save(_: dict[str, object]) -> tuple[int, dict[str, object]]:
            nonlocal called
            called = True
            return 200, {}

        setup = BrowserSetup()
        await setup.open(_state, save)
        try:
            url = urls[0]
            result, _, body = await asyncio.to_thread(
                _request,
                url,
                "POST",
                "save",
                body=data,
                headers=_save_headers(url),
            )
            assert result == status and json.loads(body)["ok"] is False
            assert not called
        finally:
            await setup.close()

    asyncio.run(run())


def test_reopening_revokes_previous_listener_and_teardown_is_idempotent(urls: list[str]) -> None:
    async def run() -> None:
        setup = BrowserSetup()
        try:
            await setup.close()
            await setup.open(_state, _accept)
            await setup.open(_state, _accept)
            assert urlsplit(urls[0]).path != urlsplit(urls[1]).path
            await _wait_closed(urls[0])
            assert (await asyncio.to_thread(_request, urls[1]))[0] == 200
            await setup.close()
            await setup.close()
            await _wait_closed(urls[1])
        finally:
            await setup.close()

    asyncio.run(run())


def test_ttl_stops_listener_without_requests(
    urls: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(browser_setup, "_TTL", 0.2)

    async def run() -> None:
        setup = BrowserSetup()
        await setup.open(_state, _accept)
        try:
            await _wait_closed(urls[0])
        finally:
            await setup.close()

    asyncio.run(run())


def test_active_save_rejects_duplicates_and_reopen_and_survives_close(urls: list[str]) -> None:
    async def run() -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def save(body: dict[str, object]) -> tuple[int, dict[str, object]]:
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return await _accept(body)

        setup = BrowserSetup()
        await setup.open(_state, save)
        url = urls[0]
        request = asyncio.create_task(
            asyncio.to_thread(
                _request,
                url,
                "POST",
                "save",
                body=b"{}",
                headers=_save_headers(url),
            )
        )
        try:
            await asyncio.wait_for(started.wait(), 2)
            with pytest.raises(OSError, match="already in progress"):
                await setup.open(_state, save)
            status, _, body = await asyncio.to_thread(
                _request,
                url,
                "POST",
                "save",
                body=b"{}",
                headers=_save_headers(url),
            )
            assert status == 409 and json.loads(body)["code"] == "SAVE_IN_PROGRESS"
            close = asyncio.create_task(setup.close())
            await _wait_closed(url)
            assert not close.done()
            with pytest.raises(OSError, match="already in progress"):
                await asyncio.wait_for(setup.open(_state, save), 1)
            release.set()
            await close
            assert (await request)[0] == 200
            assert calls == 1 and len(urls) == 1
        finally:
            release.set()
            await setup.close()
            await request

    asyncio.run(run())


def test_timed_out_save_may_still_finish(
    urls: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(browser_setup, "_SAVE_WAIT_SECONDS", 0.1)

    async def run() -> None:
        release = asyncio.Event()
        committed = asyncio.Event()

        async def save(body: dict[str, object]) -> tuple[int, dict[str, object]]:
            await release.wait()
            committed.set()
            return await _accept(body)

        setup = BrowserSetup()
        await setup.open(_state, save)
        try:
            status, _, body = await asyncio.to_thread(
                _request,
                urls[0],
                "POST",
                "save",
                body=b"{}",
                headers=_save_headers(urls[0]),
            )
            assert status == 504 and json.loads(body)["code"] == "SAVE_STATUS_UNKNOWN"
            with pytest.raises(OSError, match="already in progress"):
                await setup.open(_state, save)
            release.set()
            await asyncio.wait_for(committed.wait(), 2)
            await _wait_closed(urls[0])
        finally:
            release.set()
            await setup.close()

    asyncio.run(run())


def test_input_deadline_and_number_of_http_workers(
    urls: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(browser_setup, "_SOCKET_SECONDS", 0.4)
    monkeypatch.setattr(browser_setup, "_MAX_WORKERS", 1)

    async def run() -> None:
        in_read_state = asyncio.Event()
        release = asyncio.Event()

        async def hold() -> dict[str, object]:
            in_read_state.set()
            await release.wait()
            return {}

        setup = BrowserSetup()
        await setup.open(hold, _accept)
        url = urls[0]
        parts = urlsplit(url)
        request = asyncio.create_task(asyncio.to_thread(_request, url, "GET", "state"))
        try:
            await asyncio.wait_for(in_read_state.wait(), 2)
            with pytest.raises((http.client.RemoteDisconnected, ConnectionResetError)):
                await asyncio.to_thread(_request, url, "GET")
            release.set()
            assert (await request)[0] == 200
            deadline_reply = b""
            # A just-finished worker may be releasing the only slot; retry until
            # this partially supplied body was admitted by the HTTP server.
            async with _timeout(2):
                while not deadline_reply:
                    data = (
                        f"POST {parts.path}save HTTP/1.1\r\nHost: {parts.netloc}\r\n"
                        f"Origin: {_origin(url)}\r\nContent-Type: application/json\r\n"
                        "Content-Length: 20\r\n\r\n{"
                    ).encode()
                    try:
                        status, _, deadline_reply = await asyncio.to_thread(_raw, url, data)
                    except (http.client.RemoteDisconnected, ConnectionResetError):
                        continue
                    assert status == 408 and json.loads(deadline_reply)["code"] == "REQUEST_TIMEOUT"
        finally:
            release.set()
            await setup.close()
            await request

    asyncio.run(run())


def test_exceptions_do_not_leak_and_opener_failure_closes_listener(
    urls: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def secret_error(*_: object) -> dict[str, object]:
        raise OSError("sensitive payload")

    async def failing_save(_: dict[str, object]) -> tuple[int, dict[str, object]]:
        await secret_error()
        raise AssertionError

    def broken_open(url: str) -> None:
        urls.append(url)
        raise OSError(url)

    async def run() -> None:
        setup = BrowserSetup()
        await setup.open(secret_error, failing_save)
        try:
            for call in (
                asyncio.to_thread(_request, urls[0], "GET", "state"),
                asyncio.to_thread(
                    _request, urls[0], "POST", "save", body=b"{}", headers=_save_headers(urls[0])
                ),
            ):
                result, _, body = await call
                assert result == 500 and json.loads(body)["code"] == "SETUP_UNAVAILABLE"
                assert b"sensitive payload" not in body
            monkeypatch.setattr(browser_setup, "_open_browser", broken_open)
            with pytest.raises(
                OSError, match=r"^Could not open the local connection setup page\.$"
            ):
                await setup.open(_state, _accept)
            assert len(urls) == 2
            for url in urls:
                await _wait_closed(url)
        finally:
            await setup.close()

    asyncio.run(run())
    capture = capsys.readouterr()
    assert capture.out == capture.err == ""


def test_posix_browser_launcher_detaches_all_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    monkeypatch.setattr(browser_setup.sys, "platform", "darwin")
    monkeypatch.setattr(
        browser_setup.subprocess,
        "run",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )
    url = "http://127.0.0.1:12345/setup/fake-secret/"
    browser_setup._open_browser(url)
    assert calls == [
        (
            ["/usr/bin/open", url],
            {
                "stdin": browser_setup.subprocess.DEVNULL,
                "stdout": browser_setup.subprocess.DEVNULL,
                "stderr": browser_setup.subprocess.DEVNULL,
                "timeout": browser_setup._LAUNCH_SECONDS,
                "check": True,
            },
        )
    ]
