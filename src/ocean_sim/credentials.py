"""Copernicus Marine credentials, read from ``.env``.

The credentials can arrive three ways, and they are tried in this order:

  1. **already in the environment** -- for CI, or an explicit override
  2. **``.env`` in the project root** -- the default this module exists to enable
  3. **``~/.copernicusmarine/``** -- written by ``copernicusmarine login``

Precedence matters: a variable that is *already set* is never overwritten, so an explicit
``COPERNICUSMARINE_SERVICE_PASSWORD=... uv run python ...`` on the command line beats
the file, and CI can inject secrets without touching the working tree.

Why ``.env`` rather than calling ``copernicusmarine login``: the login is interactive,
which cannot be scripted, cannot run in CI, and fails silently in a room if somebody has
to type a password in front of thirty people. The ``copernicusmarine`` CLI reads exactly
these two variable names itself, so this module does not implement any authentication --
it only decides what the child process should inherit.

    COPERNICUSMARINE_SERVICE_USERNAME
    COPERNICUSMARINE_SERVICE_PASSWORD

Those names are not guessable. ``COPERNICUS_USERNAME`` and ``COPERNICUS_PASSWORD`` are
**silently ignored** -- no warning, no error, the variables are simply never read. That
mistake sat in this repository's ``.env`` and cost an afternoon.

Nothing here prints a value. :func:`status` returns booleans only, so it is safe to
display.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

# The names the CLI actually reads, per `copernicusmarine login --help`.
USERNAME_VAR = "COPERNICUSMARINE_SERVICE_USERNAME"
PASSWORD_VAR = "COPERNICUSMARINE_SERVICE_PASSWORD"
REQUIRED = (USERNAME_VAR, PASSWORD_VAR)

ROOT = Path(__file__).resolve().parents[2]
DOTENV = ROOT / ".env"
LOGIN_DIR = Path.home() / ".copernicusmarine"


def load(*, env_path: Path | None = None, quiet: bool = True) -> dict:
    """Put credentials into ``os.environ`` from ``.env`` if they are not already set.

    Returns a status dict. Never includes a credential value.
    """
    path = Path(env_path) if env_path else DOTENV
    from_env = False

    if path.exists():
        from_env = _parse_into(path, only_if_absent=True)
    else:
        quiet or print(f"  no .env at {path}")

    have_env = all(os.environ.get(v) for v in REQUIRED)
    login_blob = LOGIN_DIR / ".copernicusmarine-credentials"

    return {
        "source": ("environment" if not from_env and have_env else
                   ".env" if from_env else
                   "copernicusmarine login" if login_blob.exists() else
                   "none"),
        "from_dotenv": from_env,
        "dotenv_path": str(path),
        "dotenv_exists": path.exists(),
        "login_blob_exists": login_blob.exists(),
        "username_set": bool(os.environ.get(USERNAME_VAR)),
        "password_set": bool(os.environ.get(PASSWORD_VAR)),
        "complete": have_env,
        "loose_permissions": _is_world_readable(path) if path.exists() else False,
    }


def _parse_into(path: Path, *, only_if_absent: bool) -> bool:
    """Read KEY=VALUE pairs into os.environ, without requiring python-dotenv.

    Deliberately not `load_dotenv`: that exports *every* variable in the file, and this
    module's job is to put two specific names into the environment for a child process.
    A hand-rolled parser that touches only REQUIRED is a smaller blast radius, and it
    keeps working if python-dotenv is ever dropped.

    Handles `export KEY=VALUE`, `#` comments, blank lines, and `KEY=value` with no
    surrounding quotes assumed (values are taken literally, as the CLI expects).
    """
    found = False
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key in REQUIRED and value:
            found = True
            if only_if_absent and os.environ.get(key):
                continue          # an explicit environment variable wins
            os.environ[key] = value
    return found


def _is_world_readable(path: Path) -> bool:
    try:
        return bool(path.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH))
    except OSError:
        return False


def check_permissions() -> str | None:
    """Return a warning string if ``.env`` is readable by others. None if it is fine."""
    if not DOTENV.exists() or not _is_world_readable(DOTENV):
        return None
    return (
        f"{DOTENV} holds a password but is world-readable. Tighten it:\n"
        f"    chmod 600 {DOTENV}"
    )


def describe() -> str:
    """A short human-readable summary. Safe to print -- no values."""
    s = load()
    if s["complete"]:
        via = {"environment": "the environment", ".env": str(s["dotenv_path"])}[
            s["source"] if s["source"] in ("environment", ".env") else "environment"
        ]
        line = f"  credentials: present, from {via}"
    elif s["login_blob_exists"]:
        line = ("  credentials: using ~/.copernicusmarine/ (written by "
                "`copernicusmarine login`)")
    else:
        line = "  credentials: NONE. Everything else still works."
    warn = check_permissions()
    return line + (f"\n  !! {warn}" if warn else "")
