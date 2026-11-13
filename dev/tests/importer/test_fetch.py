import socket
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

import app.importer.fetch as fetch_module
from app.importer.fetch import FetchError, fetch_html

FIXTURES = Path(__file__).parents[2] / "fixtures" / "import"


class Handler(BaseHTTPRequestHandler):
    seen: list[tuple[str, dict[str, str]]] = []

    def do_GET(self):  # noqa: N802 - stdlib callback name
        headers = {key: value for key, value in self.headers.items()}
        self.seen.append((self.path, headers))
        if self.path == "/ok":
            body = b"<html><body>recipe</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/json":
            body = b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/large":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(1_000_001))
            self.end_headers()
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.end_headers()
        elif self.path == "/redirect-http":
            self.send_response(302)
            self.send_header("Location", "http://recipe.example.test/ok")
            self.end_headers()
        elif self.path == "/redirect1":
            self.send_response(302)
            self.send_header("Location", "/redirect2")
            self.end_headers()
        elif self.path == "/redirect2":
            self.send_response(302)
            self.send_header("Location", "/redirect3")
            self.end_headers()
        elif self.path == "/redirect3":
            self.send_response(302)
            self.send_header("Location", "/redirect4")
            self.end_headers()
        elif self.path == "/redirect4":
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.end_headers()
        elif self.path == "/missing":
            self.send_response(404)
            self.end_headers()
        elif self.path == "/slow":
            time.sleep(0.2)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html></html>")
        elif self.path == "/drip":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", "20")
            self.end_headers()
            for _ in range(20):
                self.wfile.write(b"x")
                self.wfile.flush()
                time.sleep(0.03)
        elif self.path == "/location200":
            body = b"<html><body>location header is metadata</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Location", "/redirect")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        return


def _url(server: tuple[str, fetch_module._ResolvedAddress], path: str) -> str:
    return server[0] + path


@pytest.fixture
def local_server(monkeypatch, tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Handler.seen = []
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=recipe.example.test",
            "-addext",
            "subjectAltName=DNS:recipe.example.test",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(certfile=cert, keyfile=key)
    server.socket = server_context.wrap_socket(server.socket, server_side=True)
    address = fetch_module._ResolvedAddress(fetch_module.socket.AF_INET, ("127.0.0.1", server.server_port))
    # The tests use a local certificate and a fictional hostname. Production
    # still creates a normal verifying context and pins the resolver result.
    monkeypatch.setattr(fetch_module, "_public_host", lambda _host, _port: (address,))
    monkeypatch.setattr(fetch_module.ssl, "create_default_context", lambda: ssl._create_unverified_context())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "https://recipe.example.test", address
    server.shutdown()
    thread.join(timeout=1)
    server.server_close()


def test_local_fetch_follows_one_redirect_and_sends_no_cookie(local_server):
    result = fetch_html(_url(local_server, "/redirect"))
    assert result.body == "<html><body>recipe</body></html>"
    assert result.redirects == 1
    assert all("Cookie" not in headers for _, headers in Handler.seen)


def test_local_fetch_rejects_non_html_and_too_many_redirects(local_server):
    with pytest.raises(FetchError) as non_html:
        fetch_html(_url(local_server, "/json"))
    assert non_html.value.code == "not_html"
    with pytest.raises(FetchError) as redirects:
        fetch_html(_url(local_server, "/redirect1"))
    assert redirects.value.code == "http_error"
    with pytest.raises(FetchError) as large:
        fetch_html(_url(local_server, "/large"))
    assert large.value.code == "too_large"


def test_local_fetch_maps_http_and_timeout_errors(local_server):
    with pytest.raises(FetchError) as missing:
        fetch_html(_url(local_server, "/missing"))
    assert missing.value.code == "http_error"
    with pytest.raises(FetchError) as timed_out:
        fetch_html(_url(local_server, "/slow"), timeout=0.01)
    assert timed_out.value.code == "timeout"


def test_total_deadline_stops_slow_drip(local_server):
    started = time.monotonic()
    with pytest.raises(FetchError) as timed_out:
        fetch_html(_url(local_server, "/drip"), timeout=0.1)
    assert timed_out.value.code == "timeout"
    assert time.monotonic() - started < 0.5


def test_location_header_on_success_is_not_a_redirect(local_server):
    result = fetch_html(_url(local_server, "/location200"))
    assert result.redirects == 0
    assert "location header is metadata" in result.body


def test_redirect_to_http_is_rejected(local_server):
    with pytest.raises(FetchError) as rejected:
        fetch_html(_url(local_server, "/redirect-http"))
    assert rejected.value.code == "invalid_url"


def test_content_type_and_meta_charset_decode_latin1_fixture(local_server, monkeypatch):
    body = (FIXTURES / "14-non-english-latin1.html").read_bytes()
    original = Handler.do_GET

    def serve_latin1(self):
        if self.path in {"/latin1", "/latin1-header"}:
            self.send_response(200)
            content_type = "text/html; charset=iso-8859-1" if self.path == "/latin1-header" else "text/html"
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        original(self)

    monkeypatch.setattr(Handler, "do_GET", serve_latin1)
    meta_result = fetch_html(_url(local_server, "/latin1"))
    header_result = fetch_html(_url(local_server, "/latin1-header"))
    assert "Crème brûlée" in meta_result.body
    assert "Crème brûlée" in header_result.body


def test_validated_address_is_used_without_a_second_dns_lookup(local_server, monkeypatch):
    address = local_server[1]
    calls: list[tuple[str, int | None]] = []

    def resolver(host: str, port: int | None):
        calls.append((host, port))
        return (address,)

    monkeypatch.setattr(fetch_module, "_public_host", resolver)

    def rebinding_resolution(*_args, **_kwargs):
        # A second lookup would return a private address. The pinned request
        # must never call the resolver again after validation.
        return [(fetch_module.socket.AF_INET, fetch_module.socket.SOCK_STREAM, 0, "", ("127.0.0.1", address.sockaddr[1]))]

    monkeypatch.setattr(fetch_module.socket, "getaddrinfo", rebinding_resolution)
    result = fetch_html(_url(local_server, "/ok"))
    assert result.body == "<html><body>recipe</body></html>"
    assert calls == [("recipe.example.test", None)]


def test_public_urls_allow_only_default_https_port():
    with pytest.raises(FetchError) as wrong_port:
        fetch_html("https://recipes.example.test:8443/recipe")
    assert wrong_port.value.code == "invalid_url"


def test_public_https_validation_rejects_insecure_and_private_urls():
    with pytest.raises(FetchError) as insecure:
        fetch_html("http://example.test/recipe")
    assert insecure.value.code == "invalid_url"
    with pytest.raises(FetchError) as private:
        fetch_html("https://127.0.0.1/recipe")
    assert private.value.code == "blocked_address"
