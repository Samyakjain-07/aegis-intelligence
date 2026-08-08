"""Local-disk storage for uploaded source PDFs.

Phase 4 (`PROJECT_HANDBOOK.md`) stores uploaded files on the local
filesystem, under a shared `data/uploads/` directory at the repo root --
deliberately not S3/blob storage, since no object-storage client is in the
agreed stack yet (`CLAUDE.md` §3). This only works because `services/api`
and `services/ingestion` run on the same machine during local dev
(`PROJECT_HANDBOOK.md` §5); a real deployment needs a shared object store
instead, since the two services scale independently and won't share a
filesystem in production -- that's Phase 9's job (see
`docs/architecture.md` §4's "Qdrant and Postgres are both managed
services" principle, which the same reasoning extends to file storage).
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

# infra/ -> src/ -> api/ -> services/ -> repo root.
_REPO_ROOT = Path(__file__).resolve().parents[4]

UPLOAD_DIR: Path = Path(os.environ.get("UPLOAD_DIR", str(_REPO_ROOT / "data" / "uploads")))


def save_uploaded_pdf(document_id: uuid.UUID, original_filename: str, content: bytes) -> str:
    """Writes `content` to `UPLOAD_DIR/<document_id><ext>` and returns the
    path to store as `Document.source_url`.

    The `document_id` prefix (rather than the original filename) is what
    guarantees no collision even when two uploads share a filename --
    `document_id` is already the primary key, so it's free uniqueness
    rather than a second scheme to invent. The returned path is relative
    to the repo root when possible (matches how this project already
    treats the repo root as the shared reference point for `.env`,
    `docker-compose.yml`, etc.), falling back to an absolute path if
    `UPLOAD_DIR` was overridden to somewhere outside the repo.
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_filename).suffix or ".pdf"
    dest = UPLOAD_DIR / f"{document_id}{suffix}"
    dest.write_bytes(content)
    try:
        return str(dest.relative_to(_REPO_ROOT))
    except ValueError:
        return str(dest)
