"""Protected fetching for public recipe pages.

This module deliberately uses the standard library.  Redirects are handled
manually so each destination is checked for private/reserved DNS addresses.
No cookies, credentials, or environment proxy settings are carried into a
recipe fetch.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 1_000_000
MAX_REDIRECTS = 3
DEFAULT_TIMEOUT = 10.0
_HTML_TYPES = ("text/html", "application/xhtml+xml")


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


def _public_host(host: str, port: int | None) -> None:
    """Reject a host unless every resolved address is globally routable."""
    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
        }
    except (OSError, socket.gaierror) as exc:
        raise FetchError("blocked_address", "The recipe host could not be resolved safely.") from exc
    if not addresses:
        raise FetchError("blocked_address", "The recipe host did not resolve to a public address.")
    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as exc:
            raise FetchError("blocked_address", "The recipe host resolved to an invalid address.") from exc
        # is_global is false for loopback, link-local, private, multicast,
        # documentation, unspecified and other non-public ranges.  Check
        # mapped IPv4 values explicitly because their IPv6 wrapper is global.
        mapped = parsed.ipv4_mapped if isinstance(parsed, ipaddress.IPv6Address) else None
        if not parsed.is_global or (mapped is not None and not mapped.is_global):
            raise FetchError("blocked_address", "The recipe host resolves to a private or reserved address.")


def _validate_url(url: str) -> None:
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
    if parts.fragment:
        # Fragments are never sent to the server and can make cache keys
        # surprising.  Treating them as invalid also keeps source URLs stable.
        raise FetchError("invalid_url", "The recipe URL must not contain a fragment.", url=url)
    try:
        _public_host(parts.hostname, port)
    except FetchError as exc:
        exc.url = url
        raise


def _open_without_redirects() -> object:
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    # An empty ProxyHandler prevents HTTP(S)_PROXY from routing a request to
    # an unexpected service.  No CookieProcessor is installed.
    from urllib.request import ProxyHandler

    return build_opener(ProxyHandler({}), NoRedirect())


def _read_limited(response: HTTPResponse, max_bytes: int) -> bytes:
    length = response.headers.get("Content-Length")
    if length:
        try:
            if int(length) > max_bytes:
                raise FetchError("too_large", "The recipe page is larger than 1 MB.")
        except ValueError:
            pass
    body = bytearray()
    while len(body) <= max_bytes:
        chunk = response.read(min(64 * 1024, max_bytes + 1 - len(body)))
        if not chunk:
            break
        body.extend(chunk)
    if len(body) > max_bytes:
        raise FetchError("too_large", "The recipe page is larger than 1 MB.")
    return bytes(body)


def _request(opener: object, url: str, timeout: float, max_bytes: int) -> tuple[bytes, str, str | None]:
    request = Request(
        url,
        headers={
            "Accept": "text/html, application/xhtml+xml",
            "User-Agent": "Spoonfuls/0.1 recipe importer",
            "Accept-Encoding": "identity",
        },
        method="GET",
    )
    try:
        response = opener.open(request, timeout=timeout)  # type: ignore[attr-defined]
    except HTTPError as exc:
        if 300 <= exc.code < 400:
            location = exc.headers.get("Location")
            exc.close()
            if location:
                return b"", "", location
            raise FetchError("http_error", "Recipe site returned a redirect without a destination.", url=url, status=exc.code) from exc
        raise FetchError("http_error", f"Recipe site returned HTTP {exc.code}.", url=url, status=exc.code) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise FetchError("timeout", "The recipe site took too long to respond.", url=url) from exc
    except (URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise FetchError("timeout", "The recipe site took too long to respond.", url=url) from exc
        raise FetchError("http_error", "The recipe site could not be fetched.", url=url) from exc

    try:
        content_type = response.headers.get_content_type().lower()
        location = response.headers.get("Location")
        body = _read_limited(response, max_bytes)
    finally:
        response.close()
    return body, content_type, location


def fetch_html(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = MAX_BYTES,
    max_redirects: int = MAX_REDIRECTS,
) -> FetchedPage:
    """Fetch one public HTML page, following at most ``max_redirects``."""
    current = url
    opener = _open_without_redirects()
    for redirects in range(max_redirects + 1):
        _validate_url(current)
        body, content_type, location = _request(opener, current, timeout, max_bytes)
        if location:
            if redirects >= max_redirects:
                raise FetchError("http_error", "The recipe site redirected too many times.", url=current)
            current = urljoin(current, location)
            continue
        if content_type not in _HTML_TYPES:
            raise FetchError("not_html", "The recipe URL did not return an HTML page.", url=current)
        try:
            text = body.decode("utf-8", errors="replace")
        except UnicodeDecodeError as exc:  # defensive; replace should avoid this
            raise FetchError("not_html", "The recipe page was not readable HTML.", url=current) from exc
        return FetchedPage(current, text, content_type, redirects)
    raise FetchError("http_error", "The recipe site redirected too many times.", url=current)
