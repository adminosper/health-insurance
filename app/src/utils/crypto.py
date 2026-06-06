"""Utility for Field-Level Encryption (FLE) of sensitive PHI data."""

import json
from typing import List

from cryptography.fernet import Fernet

from src.config import settings


class DataCipher:
    """Handles symmetric encryption and decryption of data payloads."""

    def __init__(self):
        # We ensure the key is padded correctly for Fernet if needed,
        # but Fernet expects a URL-safe base64-encoded 32-byte key.
        self._cipher = Fernet(settings.ENCRYPTION_KEY.encode("utf-8"))

    def encrypt_list(self, data: List[str]) -> str:
        """Serialize a list of strings to JSON and encrypt it."""
        json_data = json.dumps(data)
        encrypted_bytes = self._cipher.encrypt(json_data.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def decrypt_to_list(self, token: str) -> List[str]:
        """Decrypt a token and deserialize it back to a list of strings."""
        decrypted_bytes = self._cipher.decrypt(token.encode("utf-8"))
        json_data = decrypted_bytes.decode("utf-8")
        return json.loads(json_data)


# Global singleton instance for use across the application
cipher = DataCipher()
