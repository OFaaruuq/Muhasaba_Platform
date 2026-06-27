"""Helpers for secure file uploads (use when upload handlers are added)."""

import os

from werkzeug.utils import secure_filename

ALLOWED_UPLOAD_EXTENSIONS = frozenset({
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "doc", "docx", "xls", "xlsx", "csv",
})
ALLOWED_UPLOAD_MIME_PREFIXES = (
    "image/",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument",
    "application/msword",
    "application/vnd.ms-excel",
    "text/csv",
)


def safe_upload_filename(original_name):
    """Return a sanitized filename or None if extension is not allowed."""
    if not original_name:
        return None
    name = secure_filename(original_name)
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return None
    return name


def is_allowed_upload_mime(content_type):
    if not content_type:
        return False
    return any(content_type.startswith(prefix) for prefix in ALLOWED_UPLOAD_MIME_PREFIXES)


def upload_destination(upload_root, subfolder, filename):
    """Build path under upload_root; caller must ensure upload_root is outside web static."""
    safe_name = safe_upload_filename(filename)
    if not safe_name:
        raise ValueError("نوع الملف غير مسموح.")
    folder = os.path.join(upload_root, secure_filename(subfolder or "misc"))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, safe_name)
