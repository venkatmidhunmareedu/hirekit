"""The session table holds the hash of the cookie value, never the value."""

import hashlib

from app.db.repositories.sessions import hash_token


def test_hash_token_is_the_32_byte_sha256_of_the_value() -> None:
    digest = hash_token("abc")

    assert digest == hashlib.sha256(b"abc").digest()
    assert len(digest) == 32
    assert b"abc" not in digest
