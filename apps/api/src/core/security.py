import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from src.core.config import settings


class TokenCipher:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode()) if key.startswith("gAAAA") else None

    def encrypt(self, value: str) -> str:
        if self._fernet is None:
            return f"dev::{value}"
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        if value.startswith("dev::"):
            return value.removeprefix("dev::")
        if self._fernet is None:
            raise InvalidToken("A valid Fernet key is required to decrypt production tokens.")
        return self._fernet.decrypt(value.encode()).decode()


token_cipher = TokenCipher(settings.encryption_key)


def hash_password(password: str, salt: str | None = None) -> str:
    password_salt = salt or secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), password_salt.encode(), 210_000)
    return f"pbkdf2_sha256$210000${password_salt}${base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
    actual = base64.b64encode(digest).decode()
    return hmac.compare_digest(actual, expected)


def create_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    return token, hash_session_token(token)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
