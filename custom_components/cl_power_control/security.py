"""Installer PIN security helpers for CL Power Control."""
from __future__ import annotations

import hashlib
import hmac
import os

# CL Power Control 0.1.x used 200k PBKDF2 iterations. Some 0.2.x builds used
# 250k. Verification deliberately accepts both so upgrades never invalidate a
# previously configured installer PIN.
CURRENT_ITERATIONS = 250_000
LEGACY_ITERATIONS = (200_000,)


def _normalise_pin(pin: str) -> str:
    """Normalise user input without weakening the numeric PIN policy."""
    return str(pin or "").strip()


def create_pin_hash(pin: str) -> tuple[str, str]:
    """Return hex salt and PBKDF2-SHA256 hash for a PIN."""
    pin = _normalise_pin(pin)
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, CURRENT_ITERATIONS)
    return salt.hex(), digest.hex()


def verify_pin(pin: str, salt_hex: str, hash_hex: str) -> bool:
    """Verify a PIN against current and all known legacy work factors."""
    pin = _normalise_pin(pin)
    if not pin:
        return False
    try:
        salt = bytes.fromhex(str(salt_hex or ""))
        expected = bytes.fromhex(str(hash_hex or ""))
    except (ValueError, TypeError):
        return False
    if not salt or not expected:
        return False

    for iterations in (CURRENT_ITERATIONS, *LEGACY_ITERATIONS):
        actual = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
        if hmac.compare_digest(actual, expected):
            return True
    return False
