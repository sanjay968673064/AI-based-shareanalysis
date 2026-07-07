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
