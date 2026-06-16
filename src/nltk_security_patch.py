"""
Monkey-patch for nltk < 3.10.0 to fix CVE-2024-53889:
URL-Encoded Path Traversal in nltk.data.load() Allows Arbitrary Local File Read.

This patch adds the `_assert_no_encoded_bypass` function and integrates it into
nltk.data's path validation, matching the fix from nltk 3.10.0 (develop branch).
"""

import re
from urllib.parse import unquote

# Regex matching unsafe patterns in resource paths (from nltk 3.10.0)
_UNSAFE_NO_PROTOCOL_RE = re.compile(r"(?:\.\./|\.\.$|^/|\\|[A-Za-z]:[/\\])")


def _assert_no_encoded_bypass(name: str, error_label: str | None = None) -> None:
    """Reject *name* if its URL-decoded form contains an unsafe pattern
    that the raw form does not. Centralised check to prevent encoded bypasses
    (e.g., ``%2fetc%2fpasswd`` -> ``/etc/passwd``)."""
    decoded = unquote(name)
    if decoded != name and _UNSAFE_NO_PROTOCOL_RE.search(decoded):
        label = name if error_label is None else error_label
        raise ValueError(f"Unsafe resource path: {label!r}")


def _reject_unsafe_no_protocol(resource_url: str) -> None:
    """Reject unsafe resource strings that omit an explicit protocol."""
    if _UNSAFE_NO_PROTOCOL_RE.search(resource_url):
        raise ValueError(f"Unsafe resource path: {resource_url!r}")
    _assert_no_encoded_bypass(resource_url)


def apply_nltk_security_patch() -> None:
    """Apply the CVE-2024-53889 fix to nltk.data module.

    This monkey-patches nltk.data to decode URL-encoded paths before
    checking for directory traversal, preventing bypasses like %2e%2e -> ...
    """
    import nltk.data

    # Add the new security functions to the module
    nltk.data._assert_no_encoded_bypass = _assert_no_encoded_bypass

    # Wrap the original _reject_unsafe_no_protocol to add encoded bypass check
    original_reject_unsafe = nltk.data._reject_unsafe_no_protocol

    def patched_reject_unsafe(resource_url: str) -> None:
        original_reject_unsafe(resource_url)
        _assert_no_encoded_bypass(resource_url)

    nltk.data._reject_unsafe_no_protocol = patched_reject_unsafe

    # Also patch normalize_resource_url to ensure it validates encoded paths
    original_normalize = nltk.data.normalize_resource_url

    def patched_normalize(resource_url: str) -> str:
        result: str = original_normalize(resource_url)
        # The original normalize_resource_url calls _reject_unsafe_no_protocol
        # which we've already patched, so this is a defense-in-depth check
        _assert_no_encoded_bypass(resource_url)
        return result

    nltk.data.normalize_resource_url = patched_normalize


# Auto-apply on import
apply_nltk_security_patch()
