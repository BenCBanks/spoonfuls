"""Protected fetching for public recipe pages.

This module deliberately uses the standard library. Redirects are handled
manually so each destination is checked for private/reserved DNS addresses.
The validated address is then used for the connection itself, which prevents
DNS rebinding between validation and the request. No cookies, credentials, or
environment proxy settings are carried into a recipe fetch.
"""

from __future__ import annotations

import codecs
import http.client
import ipaddress
import re
import socket
import ssl
import time
from dataclasses import dataclass
from http.client import HTTPResponse
from typing import Any
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 1_000_000
MAX_REDIRECTS = 3
DEFAULT_TIMEOUT = 10.0
_HTML_TYPES = ("text/html", "application/xhtml+xml")
_META_CHARSET = re.compile(rb"<meta\b[^>]*\bcharset\s*=\s*[\"']?\s*([A-Za-z0-9._:-]+)", re.I)
_META_CONTENT_TYPE = re.compile(
    rb"<meta\b[^>]*\bhttp-equiv\s*=\s*[\"']?content-type[\"']?[^>]*\bcontent\s*=\s*[\"'][^\"']*?charset\s*=\s*([A-Za-z0-9._:-]+)",
    re.I,
)


class FetchError(Exception):
    """An expected fetch failure with a stable, user-facing error code."""

    def __init__(self, code: str, message: str, *, url: str | None = None, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.url = url
        self.status = status

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class FetchedPage:
    url: str
    body: str
    content_type: str
    redirects: int = 0


@dataclass(frozen=True)
class _ResolvedAddress:
    family: int
    sockaddr: tuple[Any, ...]


def _public_host(host: str, port: int | None) -> tuple[_ResolvedAddress, ...]:
    """Resolve a host once and return only globally routable addresses."""
    try:
        infos = socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror) as exc:
        raise FetchError("blocked_address", "The recipe host could not be resolved safely.") from exc
    addresses: list[_ResolvedAddress] = []
    seen: set[tuple[int, tuple[Any, ...]]] = set()
    for family, _socktype, _proto, _canonname, sockaddr in infos:
        address = sockaddr[0]
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as exc:
            raise FetchError("blocked_address", "The recipe host resolved to an invalid address.") from exc
        # is_global is false for loopback, link-local, private, multicast,
        # documentation, unspecified and other non-public ranges. Check
        # mapped IPv4 values explicitly because their IPv6 wrapper is global.
        mapped = parsed.ipv4_mapped if isinstance(parsed, ipaddress.IPv6Address) else None
        if not parsed.is_global or (mapped is not None and not mapped.is_global):
            raise FetchError("blocked_address", "The recipe host resolves to a private or reserved address.")
        resolved = _ResolvedAddress(family, tuple(sockaddr))
        if (family, resolved.sockaddr) not in seen:
            seen.add((family, resolved.sockaddr))
            addresses.append(resolved)
    if not addresses:
        raise FetchError("blocked_address", "The recipe host did not resolve to a public address.")
    return tuple(addresses)


def _validate_url(url: str) -> tuple[_ResolvedAddress, ...]:
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise FetchError("invalid_url", "The recipe URL is not valid.", url=url) from exc
    if parts.scheme.lower() != "https" or not parts.hostname or parts.username or parts.password:
        raise FetchError("invalid_url", "Recipe imports require a public HTTPS URL without credentials.", url=url)
    try:
        port = parts.port
    except ValueError as exc:
        raise FetchError("invalid_url", "The recipe URL has an invalid port.", url=url) from exc
    if port not in (None, 443):
        raise FetchError("invalid_url", "Recipe imports use HTTPS on port 443 only.", url=url)
    if parts.fragment:
        # Fragments are never sent to the server and can make cache keys
        # surprising. Treating them as invalid also keeps source URLs stable.
        raise FetchError("invalid_url", "The recipe URL must not contain a fragment.", url=url)
    try:
        return _public_host(parts.hostname, port)
    except FetchError as exc:
        exc.url = url
        raise


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: _ResolvedAddress, timeout: float):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._address = address

    def connect(self) -> None:
        sock = socket.socket(self._address.family, socket.SOCK_STREAM)
        try:
            sock.settimeout(self.timeout if self.timeout is not None else DEFAULT_TIMEOUT)
            sock.connect(self._address.sockaddr)
            # ``self.host`` remains the original hostname, so certificate
            # verification and SNI use it while the TCP socket is pinned.
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def _remaining(deadline: float, url: str) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise FetchError("timeout", "The recipe site took too long to respond.", url=url)
    return remaining


def _connection(url: str, address: _ResolvedAddress, timeout: float) -> http.client.HTTPConnection:
    parts = urlsplit(url)
    host = parts.hostname
    if parts.scheme.lower() != "https" or not host:
        raise FetchError("invalid_url", "Recipe imports require a public HTTPS URL.", url=url)
    return _PinnedHTTPSConnection(host, 443, address, timeout)


def _set_response_timeout(response: HTTPResponse, timeout: float) -> None:
    raw = getattr(getattr(response, "fp", None), "raw", None)
    sock = getattr(raw, "_sock", None)
    if sock is not None:
        sock.settimeout(timeout)


def _read_limited(response: HTTPResponse, max_bytes: int, deadline: float, url: str) -> bytes:
    length = response.headers.get("Content-Length")
    if length:
        try:
            if int(length) > max_bytes:
                raise FetchError("too_large", "The recipe page is larger than 1 MB.", url=url)
        except ValueError:
            pass
    body = bytearray()
    reader = getattr(response, "read1", None)
    while len(body) <= max_bytes:
        timeout = _remaining(deadline, url)
        _set_response_timeout(response, timeout)
        # read1 performs one buffered socket read, allowing us to refresh the
        # socket timeout before every chunk and enforce one total deadline.
        chunk = reader(min(64 * 1024, max_bytes + 1 - len(body))) if reader else response.read(1)
        if not chunk:
            break
        body.extend(chunk)
    if len(body) > max_bytes:
        raise FetchError("too_large", "The recipe page is larger than 1 MB.", url=url)
    return bytes(body)


def _request(
    url: str,
    addresses: tuple[_ResolvedAddress, ...],
    deadline: float,
    max_bytes: int,
) -> tuple[bytes, str, str | None, str | None]:
    parts = urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    headers = {
        "Accept": "text/html, application/xhtml+xml",
        "User-Agent": "Spoonfuls/0.1 recipe importer",
        "Accept-Encoding": "identity",
    }
    last_error: BaseException | None = None
    for address in addresses:
        conn: http.client.HTTPConnection | None = None
        try:
            conn = _connection(url, address, _remaining(deadline, url))
            conn.request("GET", path, headers=headers)
            response = conn.getresponse()
            if 300 <= response.status < 400:
                location = response.getheader("Location")
                response.close()
                conn.close()
                if location:
                    return b"", "", location, None
                raise FetchError("http_error", "The recipe site returned a redirect without a destination.", url=url, status=response.status)
            if response.status < 200 or response.status >= 400:
                status = response.status
                response.close()
                conn.close()
                raise FetchError("http_error", f"Recipe site returned HTTP {status}.", url=url, status=status)
            content_type = response.headers.get_content_type().lower()
            charset = response.headers.get_content_charset()
            body = _read_limited(response, max_bytes, deadline, url)
            response.close()
            conn.close()
            return body, content_type, None, charset
        except FetchError:
            if conn is not None:
                conn.close()
            raise
        except (TimeoutError, socket.timeout) as exc:
            if conn is not None:
                conn.close()
            raise FetchError("timeout", "The recipe site took too long to respond.", url=url) from exc
        except (http.client.HTTPException, OSError, ssl.SSLError) as exc:
            if conn is not None:
                conn.close()
            last_error = exc
            continue
    if isinstance(last_error, (TimeoutError, socket.timeout)):
        raise FetchError("timeout", "The recipe site took too long to respond.", url=url) from last_error
    raise FetchError("http_error", "The recipe site could not be fetched.", url=url) from last_error


def _meta_charset(body: bytes) -> str | None:
    head = body[:65536]
    match = _META_CHARSET.search(head) or _META_CONTENT_TYPE.search(head)
    if not match:
        return None
    candidate = match.group(1).decode("ascii", errors="ignore").strip()
    try:
        return codecs.lookup(candidate).name
    except LookupError:
        return None


def _decode_html(body: bytes, content_type: str, charset: str | None) -> str:
    selected = charset or _meta_charset(body) or "utf-8"
    try:
        codecs.lookup(selected)
    except LookupError:
        selected = "utf-8"
    return body.decode(selected, errors="replace")


def fetch_html(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = MAX_BYTES,
    max_redirects: int = MAX_REDIRECTS,
) -> FetchedPage:
    """Fetch one public HTML page, following at most ``max_redirects``."""
    if timeout <= 0:
        raise FetchError("timeout", "The recipe site took too long to respond.", url=url)
    deadline = time.monotonic() + timeout
    current = url
    for redirects in range(max_redirects + 1):
        parts = urlsplit(current)
        if parts.scheme.lower() != "https":
            raise FetchError("invalid_url", "Recipe imports require a public HTTPS URL.", url=current)
        addresses = _validate_url(current)
        body, content_type, location, charset = _request(current, addresses, deadline, max_bytes)
        if location is not None:
            if redirects >= max_redirects:
                raise FetchError("http_error", "The recipe site redirected too many times.", url=current)
            current = urljoin(current, location)
            continue
        if content_type not in _HTML_TYPES:
            raise FetchError("not_html", "The recipe URL did not return an HTML page.", url=current)
        return FetchedPage(current, _decode_html(body, content_type, charset), content_type, redirects)
    raise FetchError("http_error", "The recipe site redirected too many times.", url=current)
