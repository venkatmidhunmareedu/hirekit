"""Password hashing: argon2id, and an unknown account costs the same verify."""

from app.core.passwords import DUMMY_HASH, hash_password, verify_password


def test_hash_is_argon2id_and_not_the_password() -> None:
    hashed = hash_password("correct horse battery")

    assert hashed.startswith("$argon2id$")
    assert "correct horse" not in hashed


def test_verify_accepts_the_right_password() -> None:
    assert verify_password(hash_password("s3cret-pass-phrase"), "s3cret-pass-phrase")


def test_verify_rejects_a_wrong_password() -> None:
    assert not verify_password(hash_password("s3cret-pass-phrase"), "other")


def test_verify_rejects_a_malformed_hash() -> None:
    assert not verify_password("not-a-hash", "anything")


def test_dummy_hash_never_matches() -> None:
    assert not verify_password(DUMMY_HASH, "")
