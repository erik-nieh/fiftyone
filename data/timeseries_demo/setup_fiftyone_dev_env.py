"""Configure ``sys.path`` and env vars for local FiftyOne development.

Keep this file next to ``sdk_timeseries_demo.ipynb``. The notebook assumes the
kernel's working directory is that same folder (typical when opening the
notebook there).

Example (notebook)::

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path.cwd()))
    from setup_fiftyone_dev_env import setup
    setup()

CLI (from repo root or this directory)::

    python data/timeseries_demo/setup_fiftyone_dev_env.py

Override repo root::

    export FIFTYONE_REPO=/path/to/fiftyone
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = ["find_repo", "setup"]


def find_repo() -> Path:
    """Return the clone root (directory containing the ``fiftyone`` package)."""
    if override := os.environ.get("FIFTYONE_REPO"):
        return Path(override).resolve()

    here_file = Path(__file__).resolve()
    for parent in here_file.parents:
        if (parent / "fiftyone" / "core" / "timeseries.py").is_file():
            return parent

    here = Path.cwd().resolve()
    for p in [here, *here.parents]:
        if (p / "fiftyone" / "core" / "timeseries.py").is_file():
            return p
    raise RuntimeError(
        "Could not find repo root (looked for fiftyone/core/timeseries.py). "
        "Set FIFTYONE_REPO or run from inside the clone."
    )


def setup(*, verbose: bool = True) -> Path:
    """Prepend clone root to ``sys.path``, set plugins dir, load ``.env`` (optional)."""
    repo = find_repo()

    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    plugins = repo / "plugins"
    if plugins.is_dir():
        os.environ.setdefault("FIFTYONE_PLUGINS_DIR", str(plugins))

    env_file = repo / ".env"
    if env_file.is_file():
        for raw in env_file.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, val)

    if verbose:
        print(f"Using repo: {repo}")
    return repo


if __name__ == "__main__":
    setup()
