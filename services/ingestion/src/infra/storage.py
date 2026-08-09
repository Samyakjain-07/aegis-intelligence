"""Local-disk file resolution for `services/ingestion` -- the read-side
counterpart to `services/api/src/infra/storage.py`'s `save_uploaded_pdf`.

`Document.source_url` (written by `POST /documents`, Phase 4) is a path
relative to the repo root, e.g. `data/uploads/<document_id>.pdf`. This
module resolves that string back into an absolute `Path` the ingestion
worker can actually open -- symmetric with the API side's own
repo-root-relative path handling, and subject to the exact same Phase-9
caveat: this only works because both services run on the same machine and
share a filesystem in local dev. A real deployment needs a shared object
store instead (see the API-side module's docstring; the same reasoning
applies unchanged here).
"""
from __future__ import annotations

import os
from pathlib import Path

# infra/ -> src/ -> ingestion/ -> services/ -> repo root -- same depth as
# services/api/src/infra/storage.py's _REPO_ROOT, since the two files sit
# at the same relative depth in their respective service trees.
_REPO_ROOT = Path(__file__).resolve().parents[4]

UPLOAD_DIR: Path = Path(os.environ.get("UPLOAD_DIR", str(_REPO_ROOT / "data" / "uploads")))


def resolve_source_path(source_url: str) -> Path:
    """Resolves `Document.source_url` into an absolute, openable `Path`.

    Handles both forms `source_url` can take (see
    `services/api/src/infra/storage.py::save_uploaded_pdf`): a path
    relative to the repo root (the common case), or an absolute path
    (the fallback used when `UPLOAD_DIR` was overridden to somewhere
    outside the repo). Raises `FileNotFoundError` immediately with a clear
    message rather than letting `pymupdf.open()` fail later with a less
    obvious error -- ingestion failing on a missing source file is exactly
    the kind of thing `docs/architecture.md` §3's "corrupt or unparseable
    PDF" failure path expects to happen and retry/dead-letter cleanly, and
    that starts with a clear signal here.
    """
    candidate = Path(source_url)
    resolved = candidate if candidate.is_absolute() else (_REPO_ROOT / candidate)
    if not resolved.is_file():
        raise FileNotFoundError(
            f"Source PDF not found at {resolved} (from Document.source_url={source_url!r})."
        )
    return resolved
