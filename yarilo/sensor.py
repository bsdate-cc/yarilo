"""Reads lux from a light sensor over HTTP (for example ESPHome), never through a proxy."""
import json
import math
import urllib.parse
import urllib.request

_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def parse(body: bytes, field: str = "value") -> float:
    value = json.loads(body).get(field)
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"no number in {field!r}: {body[:80]!r}") from None
    if math.isnan(value):
        raise ValueError(f"no number in {field!r}: {body[:80]!r}")
    return value


def http_fetch(url: str, field: str = "value", timeout: float = 2.0) -> float:
    with _OPENER.open(url, timeout=timeout) as r:
        return parse(r.read(), field)


class SensorClient:
    """Tries the addresses in order; the one that answered goes first next time."""

    def __init__(self, urls, fetch=None, field: str = "value"):
        self.urls = list(urls)
        self._fetch = fetch or (lambda url: http_fetch(url, field))
        self.last_error: str | None = None

    def read(self) -> float | None:
        for url in list(self.urls):
            try:
                lux = self._fetch(url)
            except (OSError, ValueError) as e:
                self.last_error = f"{url}: {e}"
                continue
            if self.urls[0] != url:
                self.urls.remove(url)
                self.urls.insert(0, url)
            self.last_error = None
            return lux
        return None

    def page(self) -> str | None:
        """The sensor's own web page: the first address without its path."""
        if not self.urls:
            return None
        u = urllib.parse.urlsplit(self.urls[0])
        return f"{u.scheme}://{u.netloc}/"
