"""One place that knows how to reach the database.

The DSN default was previously copy-pasted into three scripts. That works right up until
the port becomes configurable, at which point the copies drift and the override works in
one place and silently does nothing in the others.

Both ``OCEAN_SIM_DSN`` (a full URL) and ``OCEAN_SIM_PORT`` (just the port) are honoured.
The full URL wins, because a DSN that disagrees with the port is the more specific
statement of intent.

Run:  from ocean_sim.dsn import dsn
"""

from __future__ import annotations

import os

DEFAULT_PORT = 5432
DEFAULT_DSN = "postgresql://postgres:ocean@localhost:5432/ocean_sim"


def dsn() -> str:
    """The DSN to connect with, honouring OCN_SIM_DSN or OCN_SIM_PORT."""
    explicit = os.environ.get("OCEAN_SIM_DSN")
    if explicit:
        return explicit
    port = os.environ.get("OCEAN_SIM_PORT", str(DEFAULT_PORT))
    return f"postgresql://postgres:ocean@localhost:{port}/ocean_sim"


def port() -> int:
    """The port the database is expected on. Used for pre-flight checks."""
    url = dsn()
    # Take the last colon-separated field before the path; simple but adequate for a
    # postgres URL, and better than a regex that would itself need a test.
    try:
        authority = url.split("//", 1)[1].split("/", 1)[0]
        return int(authority.rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return int(os.environ.get("OCEAN_SIM_PORT", DEFAULT_PORT))
