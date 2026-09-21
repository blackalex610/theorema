"""Tests for signed media URLs.

`/media` serves children's homework photos. Access is gated by an HMAC token
bound to the filename and an expiry, so these properties are load-bearing.
"""
import time

import pytest

from app.services import media_tokens
from app.services.media_tokens import (
    build_media_url,
    sign_media_token,
    verify_media_token,
)


def test_a_freshly_signed_token_verifies():
    assert verify_media_token("abc123.jpg", sign_media_token("abc123.jpg")) is True


@pytest.mark.parametrize("token", [None, "", "garbage", "no-dot", "abc.def", "0."])
def test_malformed_tokens_are_rejected(token):
    assert verify_media_token("abc123.jpg", token) is False


def test_a_token_is_bound_to_its_filename():
    """Holding a link to your own upload must not unlock someone else's."""
    token = sign_media_token("mine.jpg")
    assert verify_media_token("someone-elses.jpg", token) is False


def test_an_expired_token_is_rejected():
    expired = sign_media_token("abc123.jpg", ttl_seconds=-1)
    assert verify_media_token("abc123.jpg", expired) is False


def test_the_expiry_cannot_be_extended_without_the_secret():
    """Rewriting the expiry half invalidates the signature."""
    token = sign_media_token("abc123.jpg")
    _, _, signature = token.partition(".")
    forged = f"{int(time.time()) + 10_000_000}.{signature}"
    assert verify_media_token("abc123.jpg", forged) is False


def test_a_token_signed_with_another_secret_is_rejected(monkeypatch):
    forged = sign_media_token("abc123.jpg")
    monkeypatch.setattr(media_tokens.settings, "SECRET_KEY", "a-different-secret")
    assert verify_media_token("abc123.jpg", forged) is False


def test_build_media_url_shapes():
    relative = build_media_url("abc123.jpg")
    assert relative.startswith("/media/abc123.jpg?token=")

    absolute = build_media_url("abc123.jpg", "https://api.example.test/")
    assert absolute.startswith("https://api.example.test/media/abc123.jpg?token=")

    token = absolute.split("token=", 1)[1]
    assert verify_media_token("abc123.jpg", token) is True
