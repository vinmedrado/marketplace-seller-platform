"""Criptografia de tokens sensíveis com Fernet."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from config.settings import FERNET_KEY


class TokenCryptoError(ValueError):
    pass


def _fernet() -> Fernet:
    if not FERNET_KEY:
        raise TokenCryptoError("FERNET_KEY não configurada. Gere com: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
    try:
        return Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)
    except Exception as exc:
        raise TokenCryptoError("FERNET_KEY inválida para Fernet.") from exc


def encrypt_token(token: str | None) -> str | None:
    if token is None:
        return None
    return _fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(token_encrypted: str | None) -> str | None:
    if token_encrypted is None:
        return None
    try:
        return _fernet().decrypt(token_encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise TokenCryptoError("Token criptografado inválido ou FERNET_KEY divergente.") from exc
