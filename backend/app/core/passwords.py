"""Password hashing with argon2id. Plain passwords are never stored or logged."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Verified when the email is unknown, so an unknown email costs the same as a wrong password.
DUMMY_HASH = _hasher.hash("hirekit-dummy-password-never-matches")


def hash_password(password: str) -> str:
    """The argon2id hash, with its salt and parameters inside the string."""
    return _hasher.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    """True when the password matches; a wrong password or a malformed hash is False."""
    try:
        return _hasher.verify(hashed, password)
    except VerificationError, InvalidHashError:
        return False
