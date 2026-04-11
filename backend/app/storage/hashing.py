"""Chunked SHA-256 hashing for uploaded files with size enforcement.

Uses :class:`tempfile.SpooledTemporaryFile` so that small files stay
in memory while large uploads spill to disk automatically.
"""

from __future__ import annotations

import hashlib
import tempfile
from typing import BinaryIO

from fastapi import UploadFile

_CHUNK_SIZE = 64 * 1024  # 64 KB

# Defaults used when settings are not injected (e.g., in tests).
DEFAULT_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB
DEFAULT_SPOOL_THRESHOLD = 10 * 1024 * 1024  # 10 MB — most files stay in RAM


class FileTooLargeError(Exception):
    """Raised when an uploaded file exceeds the size limit."""


async def read_and_hash(
    upload_file: UploadFile,
    *,
    max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    spool_threshold: int = DEFAULT_SPOOL_THRESHOLD,
) -> tuple[BinaryIO, str, int]:
    """Read an ``UploadFile`` in chunks, compute its SHA-256, and enforce a size limit.

    Files smaller than *spool_threshold* are kept entirely in memory.
    Larger uploads are spooled to a temporary file on disk so the server
    never holds the full payload in RAM.

    Args:
        upload_file: The incoming file.
        max_bytes: Maximum allowed file size.  Configurable via
            ``GIDEON_S3_MAX_UPLOAD_BYTES``.
        spool_threshold: In-memory buffer limit before spilling to disk.
            Configurable via ``GIDEON_S3_SPOOL_THRESHOLD_BYTES``.

    Returns:
        A tuple of ``(data, hex_digest, size_bytes)`` where *data* is a
        file-like object seeked to position 0.  The caller **must**
        close *data* when finished.

    Raises:
        FileTooLargeError: If the file exceeds *max_bytes*.
    """
    hasher = hashlib.sha256()
    buf: BinaryIO = tempfile.SpooledTemporaryFile(  # type: ignore[assignment]  # noqa: SIM115
        max_size=spool_threshold,
    )
    total = 0

    try:
        while chunk := await upload_file.read(_CHUNK_SIZE):
            total += len(chunk)
            if total > max_bytes:
                buf.close()
                raise FileTooLargeError(
                    f"File exceeds maximum allowed size of {max_bytes} bytes"
                )
            hasher.update(chunk)
            buf.write(chunk)
    except FileTooLargeError:
        raise
    except Exception:
        buf.close()
        raise

    buf.seek(0)
    return buf, hasher.hexdigest(), total
