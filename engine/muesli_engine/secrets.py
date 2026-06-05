from __future__ import annotations

import keyring

_SERVICE = "muesli"


def get_api_key(provider: str) -> str | None:
    """Return the stored API key for a provider, or None if not set."""
    return keyring.get_password(_SERVICE, provider)


def set_api_key(provider: str, key: str) -> None:
    """Store the API key for a provider in the OS keyring."""
    keyring.set_password(_SERVICE, provider, key)


def delete_api_key(provider: str) -> None:
    """Remove the stored API key for a provider, if present."""
    try:
        keyring.delete_password(_SERVICE, provider)
    except Exception:
        pass
