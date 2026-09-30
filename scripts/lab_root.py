"""Make Jupyter Lab open on the Workshop folder instead of wherever it was last left.

    uv run python scripts/lab_root.py     # then `make lab`, or run it by hand

`--notebook-dir=Workshop` sets the server's root correctly, and that is not the problem.
JupyterLab restores the file browser's last directory from a workspace file, and that
restore wins: after one session inside `workshop_3/`, every later `make lab` opened
there too, with the root setting apparently ignored.

    ~/.jupyter/lab/workspaces/default-37a8.jupyterlab-workspace
      data["file-browser-filebrowser:cwd"] == {"path": "workshop_3"}

Deleting the key is enough to send the browser back to the root on the next start. The
rest of the workspace is left alone deliberately -- the open tabs and the panel layout
still come back, so this costs the last directory and nothing else.

Note the file is keyed by URL (`default-37a8` is a plain `localhost:8888/lab`), not by
project, so one workspace is shared by every project on the machine. That is why the
key is stripped rather than the file deleted: the reset is a "start at the root" nudge,
not a way to throw away another repo's session. Each project re-picks its own root
from `--notebook-dir` on the next launch.

Writes nothing when the key is already absent, so repeated runs are no-ops.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CWD_KEY = "file-browser-filebrowser:cwd"


def workspace_dir() -> Path:
    """Where JupyterLab 4 keeps its workspace files.

    This is the *config* dir, not the data dir -- `jupyter_data_dir()` points at
    ~/Library/Jupyter on macOS, but the workspaces are in ~/.jupyter/lab/workspaces.
    """
    try:
        from jupyter_core.paths import jupyter_config_dir
    except ImportError:  # pragma: no cover - jupyter_core ships with jupyterlab
        return Path.home() / ".jupyter" / "lab" / "workspaces"
    return Path(jupyter_config_dir()) / "lab" / "workspaces"


def reset(ws: Path) -> bool:
    """Strip the restored cwd from one workspace. True if it changed anything."""
    try:
        doc = json.loads(ws.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  skipped {ws.name}: {exc}", file=sys.stderr)
        return False

    data = doc.get("data")
    if not isinstance(data, dict) or CWD_KEY not in data:
        return False

    del data[CWD_KEY]
    ws.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return True


def main() -> int:
    ws_dir = workspace_dir()
    if not ws_dir.is_dir():
        # First launch, or a machine with no Lab state yet. Nothing to undo, and the
        # browser starts at the root on its own.
        print("  no JupyterLab workspace state yet -- Lab will open at the root")
        return 0

    changed = 0
    for ws in sorted(ws_dir.glob("*.jupyterlab-workspace")):
        if reset(ws):
            changed += 1
            print(f"  reset file browser root in {ws.name}")

    print(f"  Lab will open at Workshop/ ({changed} workspace{'' if changed == 1 else 's'} reset)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
