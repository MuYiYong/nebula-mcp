"""One-shot browser setup for a local MCP process.

A bounded stdlib ThreadingHTTPServer serves fixed assets on IPv4 loopback. HTTP
workers use asyncio.run_coroutine_threadsafe to run callbacks on the owning MCP
asyncio loop; neither HTTP I/O nor the OS browser launcher shares MCP stdio.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Awaitable, Callable, Coroutine
from concurrent.futures import TimeoutError as WorkerTimeout
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from socketserver import TCPServer

_Payload = dict[str, object]
_Reply = tuple[int, _Payload]
_ReadState = Callable[[], Awaitable[_Payload]]
_Save = Callable[[_Payload], Awaitable[_Reply]]
_Request = socket.socket | tuple[bytes, socket.socket]

_LOOPBACK = "127.0.0.1"
_TTL = 600.0
_SOCKET_SECONDS = 5.0
_STATE_SECONDS = 10.0
_SAVE_WAIT_SECONDS = 420.0
_LAUNCH_SECONDS = 10.0
_MAX_WORKERS = 8
_MAX_BODY = 16 * 1024
_JSON = "application/json; charset=utf-8"
_JSON_TYPE = re.compile(
    r"application/json(?:[ \t]*;[ \t]*charset[ \t]*=[ \t]*(?:utf-8|\"utf-8\"))?", re.IGNORECASE
)
_DECIMAL = re.compile(r"[0-9]+")
_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
_ASSETS = {
    "": ("connection-setup.html", "text/html; charset=utf-8"),
    "connection-setup.css": ("connection-setup.css", "text/css; charset=utf-8"),
    "connection-setup.js": ("connection-setup.js", "text/javascript; charset=utf-8"),
}
_AssetMap = dict[str, tuple[str, bytes]]


def _error(status: int, code: str, message: str) -> _Reply:
    return status, {"ok": False, "code": code, "message": message}


def _expired() -> _Reply:
    return _error(410, "SETUP_EXPIRED", "设置页面已失效，请回到 Codex 重新打开连接设置。")


def _internal() -> _Reply:
    return _error(500, "SETUP_UNAVAILABLE", "无法完成设置请求，请回到 Codex 重新打开连接设置。")


def _load_assets() -> _AssetMap:
    root = files("nebula_mcp").joinpath("ui")
    assets = {
        route: (mime, root.joinpath(name).read_bytes()) for route, (name, mime) in _ASSETS.items()
    }
    if not all(body for _, body in assets.values()):
        raise OSError("Missing setup assets")
    return assets


def _open_browser(url: str) -> None:
    # A shell or Python's webbrowser fallback may inherit the MCP stdout pipe.
    if sys.platform == "win32":
        os.startfile(url)  # Windows ShellExecute opens the registered URL handler.
        return
    launcher = "/usr/bin/open" if sys.platform == "darwin" else "xdg-open"
    subprocess.run(
        [launcher, url],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=_LAUNCH_SECONDS,
        check=True,
    )


def _unique_object(pairs: list[tuple[str, object]]) -> _Payload:
    result: _Payload = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(_: str) -> object:
    raise ValueError("Invalid JSON constant")


class BrowserSetup:
    """Manage a single browser setup invocation for one MCP asyncio process.

    The state callback must return a redacted, JSON-serializable snapshot. The
    save callback must supply sanitized error messages and enforce its own I/O
    deadlines. A submitted save can finish after its browser disconnects; close
    stops accepting requests and waits for any already-running save to settle.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._session: _Session | None = None

    async def open(self, read_state: _ReadState, save: _Save) -> None:
        """Revoke the previous form and open a fresh one. Never return its URL."""
        # Also check before taking the lock: a concurrent close may hold it
        # while waiting for the active save, and reopen must decline promptly.
        self._check_not_saving()
        async with self._lock:
            self._check_not_saving()
            if self._session is not None:
                await self._session.close()
                self._session = None
            try:
                assets = await asyncio.to_thread(_load_assets)
                session = self._session = _Session(read_state, save, assets)
                await asyncio.to_thread(_open_browser, session.origin + session.path)
            except (Exception, asyncio.CancelledError) as exc:
                if self._session is not None:
                    await self._session.close()
                    self._session = None
                if isinstance(exc, asyncio.CancelledError):
                    raise
                raise OSError("Could not open the local connection setup page.") from None

    def _check_not_saving(self) -> None:
        if self._session is not None and self._session.saving:
            raise OSError("A connection save is already in progress.")

    async def close(self) -> None:
        """Revoke the URL and close the listening socket without blocking asyncio."""
        async with self._lock:
            if self._session is not None:
                await self._session.close()
                self._session = None


class _Session:
    def __init__(self, read_state: _ReadState, save: _Save, assets: _AssetMap) -> None:
        self.loop = asyncio.get_running_loop()
        self.read_state = read_state
        self.save = save
        self.assets = assets
        self.path = f"/setup/{secrets.token_urlsafe(32)}/"
        self._expires_at = time.monotonic() + _TTL
        self._revoked = threading.Event()
        self._save_idle = asyncio.Event()
        self._save_idle.set()
        self._stopping: asyncio.Task[None] | None = None
        self._server = _Server(self)
        self.host = f"{_LOOPBACK}:{self._server.server_port}"
        self.origin = f"http://{self.host}"
        self._thread = threading.Thread(
            target=self._server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        try:
            self._thread.start()
        except Exception:
            self._server.server_close()
            raise
        self._expiry = self.loop.call_later(_TTL, self.revoke)

    @property
    def active(self) -> bool:
        # Read from HTTP threads as well as the asyncio loop.
        return not self._revoked.is_set() and time.monotonic() < self._expires_at

    @property
    def saving(self) -> bool:
        return not self._save_idle.is_set()

    def revoke(self) -> None:
        # Called on the asyncio loop. Already accepted response sockets remain
        # open so the successful POST can deliver its response after revocation.
        if self._stopping is None:
            self._revoked.set()
            self._expiry.cancel()
            self._stopping = self.loop.create_task(asyncio.to_thread(self._stop_server))

    def _stop_server(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()

    async def close(self) -> None:
        self.revoke()
        assert self._stopping is not None
        await asyncio.shield(self._stopping)
        await self._save_idle.wait()

    async def state(self) -> _Reply:
        if not self.active:
            return _expired()
        try:
            snapshot = await self.read_state()
        except Exception:  # noqa: BLE001 - never expose callback errors in HTTP or logs
            return _internal()
        return (200, snapshot) if self.active else _expired()

    async def submit(self, body: _Payload) -> _Reply:
        # This gate and the open/revoke checks run on the same asyncio loop;
        # there is no await between checking and making the save in-flight.
        if not self.active:
            return _expired()
        if self.saving:
            return _error(409, "SAVE_IN_PROGRESS", "正在测试和保存连接，请等待当前操作完成。")
        self._save_idle.clear()
        try:
            status, result = await self.save(body)
            if status == 200:
                self.revoke()
                return 200, {"ok": True}
            if (
                type(status) is int
                and 400 <= status <= 599
                and isinstance(result.get("code"), str)
                and isinstance(result.get("message"), str)
            ):
                payload = {
                    key: result[key]
                    for key in ("code", "message", "field")
                    if isinstance(result.get(key), str)
                }
                payload["ok"] = False
                return status, payload
            return _internal()
        except Exception:  # noqa: BLE001 - never expose callback errors in HTTP or logs
            return _internal()
        finally:
            self._save_idle.set()


class _Server(ThreadingHTTPServer):
    block_on_close = False  # active handlers finish independently of the listener
    request_queue_size = 16

    def __init__(self, session: _Session) -> None:
        self.session = session
        self._slots = threading.BoundedSemaphore(_MAX_WORKERS)
        super().__init__((_LOOPBACK, 0), _Handler)

    def server_bind(self) -> None:
        # The default HTTPServer implementation also performs a DNS lookup.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = _LOOPBACK, int(self.server_address[1])

    def process_request(self, request: _Request, client_address: tuple[str, int]) -> None:
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise

    def process_request_thread(self, request: _Request, client_address: tuple[str, int]) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request: _Request, client_address: tuple[str, int]) -> None:
        # The stdlib default prints a traceback, potentially including input.
        pass


class _Handler(BaseHTTPRequestHandler):
    server: _Server
    default_request_version = "HTTP/1.0"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(_SOCKET_SECONDS)
        self._receive_deadline = time.monotonic() + _SOCKET_SECONDS
        self._receive_timer = threading.Timer(_SOCKET_SECONDS, self._end_receiving)
        self._receive_timer.daemon = True
        self._receive_timer.start()

    def finish(self) -> None:
        self._receive_timer.cancel()
        super().finish()

    def _end_receiving(self) -> None:
        # An absolute read deadline, even for a client that dribbles bytes more
        # often than the socket timeout. Keep the write half for error replies.
        with suppress(OSError):
            self.connection.shutdown(socket.SHUT_RD)

    def parse_request(self) -> bool:
        if not super().parse_request():
            return False
        self.close_connection = True
        # BaseHTTPRequestHandler normalizes leading slashes for redirect safety.
        # Our token route must match the raw request-target, without normalization.
        words = self.requestline.split()
        if (
            len(words) != 3
            or words[1] != self.path
            or self.request_version
            not in {
                "HTTP/1.0",
                "HTTP/1.1",
            }
        ):
            self.send_error(400)
            return False
        headers = list(self.headers.raw_items())
        if (
            self.headers.defects
            or len(headers) != len({key.lower() for key, _ in headers})
            or any("\r" in value or "\n" in value for _, value in headers)
        ):
            self._json(_error(400, "INVALID_HEADERS", "请求头格式不正确。"))
            return False
        return True

    def log_message(self, format: str, *args: object) -> None:
        # Neither a capability-bearing route nor client data belongs in logs.
        pass

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        # BaseHTTPRequestHandler may pass the request line or method as a reason.
        self.request_version = self.default_request_version
        if code == 501:
            self._json(_error(405, "METHOD_NOT_ALLOWED", "不支持此请求方法。"))
        else:
            self._json(_error(code, "INVALID_REQUEST", "请求格式不正确。"))

    def _write(self, status: int, mime: str, body: bytes) -> None:
        self._receive_timer.cancel()
        self.send_response_only(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", _CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, reply: _Reply) -> None:
        status, payload = reply
        try:
            body = json.dumps(payload, allow_nan=False).encode("ascii")
        except (TypeError, ValueError, RecursionError):
            status, payload = _internal()
            body = json.dumps(payload).encode("ascii")
        self._write(status, _JSON, body)

    def _route(self, *, post: bool = False) -> str | None:
        session = self.server.session
        origin = self.headers.get("Origin")
        if (
            self.headers.get("Host") != session.host
            or (origin != session.origin and (post or origin is not None))
            or self.headers.get("Sec-Fetch-Site") not in {None, "none", "same-origin"}
        ):
            self._json(_error(403, "FORBIDDEN_ORIGIN", "此请求不来自本机设置页面。"))
            return None
        if not self.path.isascii() or not hmac.compare_digest(
            self.path[: len(session.path)], session.path
        ):
            self._json(_error(404, "NOT_FOUND", "未找到设置页面，请回到 Codex 重新打开连接设置。"))
            return None
        route = self.path[len(session.path) :]
        if route not in ({"save"} if post else {*_ASSETS, "state"}):
            self._json(_error(404, "NOT_FOUND", "未找到设置页面，请回到 Codex 重新打开连接设置。"))
            return None
        if not session.active:
            self._json(_expired())
            return None
        if any(
            name in self.headers for name in ("Transfer-Encoding", "Content-Encoding", "Expect")
        ):
            self._json(_error(400, "INVALID_HEADERS", "不支持此请求编码。"))
            return None
        if time.monotonic() >= self._receive_deadline:
            self._json(_error(408, "REQUEST_TIMEOUT", "请求超时，请重新打开连接设置。"))
            return None
        return route

    def _dispatch(
        self, operation: Coroutine[object, object, _Reply], seconds: float, *, save: bool = False
    ) -> _Reply:
        try:
            future = asyncio.run_coroutine_threadsafe(operation, self.server.session.loop)
        except RuntimeError:
            operation.close()
            return _internal()
        try:
            return future.result(seconds)
        except WorkerTimeout:
            if save:
                # The callback may have passed its commit point. Don't cancel it
                # or imply the old config was retained; the busy gate stays set.
                return _error(
                    504, "SAVE_STATUS_UNKNOWN", "未等到保存结果。请稍后重新打开连接设置确认。"
                )
            future.cancel()
            return _error(504, "STATE_TIMEOUT", "读取连接设置超时，请稍后重试。")
        except Exception:  # noqa: BLE001 - future failures must not echo credentials
            return _internal()

    def do_GET(self) -> None:
        route = self._route()
        if route is None:
            return
        if self.headers.get("Content-Length") not in {None, "0"}:
            self._json(_error(400, "INVALID_LENGTH", "此请求不接受请求体。"))
            return
        self._receive_timer.cancel()
        if route == "state":
            self._json(self._dispatch(self.server.session.state(), _STATE_SECONDS))
        else:
            mime, data = self.server.session.assets[route]
            self._write(200, mime, data)

    def do_POST(self) -> None:
        if self._route(post=True) is None:
            return
        if not _JSON_TYPE.fullmatch(self.headers.get("Content-Type", "")):
            self._json(_error(415, "UNSUPPORTED_MEDIA_TYPE", "保存请求必须使用 JSON。"))
            return
        length = self.headers.get("Content-Length", "")
        if not _DECIMAL.fullmatch(length):
            self._json(_error(411, "INVALID_LENGTH", "保存请求必须声明请求体长度。"))
            return
        if len(length) > len(str(_MAX_BODY)) or (size := int(length)) > _MAX_BODY:
            self._json(_error(413, "BODY_TOO_LARGE", "连接参数超出大小限制。"))
            return
        try:
            raw = self.rfile.read(size)
        except TimeoutError:
            raw = b""
        if time.monotonic() >= self._receive_deadline:
            self._json(_error(408, "REQUEST_TIMEOUT", "请求超时，请重新打开连接设置。"))
            return
        self._receive_timer.cancel()
        try:
            if len(raw) != size:
                raise ValueError("Incomplete request")
            body = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_invalid_constant,
            )
            if not isinstance(body, dict):
                raise TypeError("Expected object")
        except (TypeError, ValueError, RecursionError):
            self._json(_error(400, "INVALID_JSON", "无法读取连接参数，请检查后重试。"))
            return
        self._json(self._dispatch(self.server.session.submit(body), _SAVE_WAIT_SECONDS, save=True))
