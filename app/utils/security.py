"""Security helpers: safe redirects, response headers."""

from urllib.parse import urljoin, urlparse

from flask import request


def is_safe_url(target):
    """Return True if *target* is a same-host relative or absolute path."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (
        test_url.scheme in ("http", "https")
        and ref_url.netloc == test_url.netloc
        and test_url.path.startswith("/")
    )


def safe_redirect_target(target, fallback_endpoint, **fallback_kwargs):
    """Validated redirect target or url_for fallback."""
    from flask import url_for

    if target and is_safe_url(target):
        return target
    return url_for(fallback_endpoint, **fallback_kwargs)
