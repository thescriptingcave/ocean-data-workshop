"""Shared HTTP session.

Moved out of ``probes/`` because the data loaders need it too, and ``src/ocean_sim`` must
not import from ``probes/``.

The IPv4 fix is not optional. This machine has AAAA records but no IPv6 route: curl races
addresses (Happy Eyeballs, RFC 8305) and looks fine, while urllib3 waits out the full
connect timeout on the dead IPv6 address before falling back. Measured against
coastwatch.pfeg.noaa.gov, every call took exactly 20.0 s -- the timeout value -- and then
succeeded. Forcing AF_INET took that to 0.20 s, a measured 100x.
"""

from __future__ import annotations


def force_ipv4() -> bool:
    """Restrict getaddrinfo to IPv4. Idempotent. Returns True if it patched."""
    import socket

    if getattr(socket.getaddrinfo, "_ocean_sim_patched", False):
        return False
    _orig = socket.getaddrinfo

    def _v4_only(host, port, *args, **kwargs):
        infos = _orig(host, port, *args, **kwargs)
        v4 = [i for i in infos if i[0] == socket.AF_INET]
        return v4 or infos  # fall back to whatever we got if there is no A record

    _v4_only._ocean_sim_patched = True  # type: ignore[attr-defined]
    socket.getaddrinfo = _v4_only  # type: ignore[assignment]
    return True


def http_session(retries: int = 3, backoff: float = 0.6):
    """A requests.Session with IPv4 preference, fail-fast timeouts, and retries.

    Retries on 429/5xx and connection resets. Public services rate-limit when hit
    repeatedly, and a probe or loader that reports failure for a 429 is reporting the
    network rather than the data.
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    force_ipv4()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
    )
    sess = requests.Session()
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.request_timeout = (6, 180)  # type: ignore[attr-defined]
    return sess
