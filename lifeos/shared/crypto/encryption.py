import base64
import os
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class TokenEncryption:
    """AES-256-GCM Token Encryption Engine."""

    def __init__(self, key: bytes | str | None = None):
        if key is None:
            raw_env_key = os.getenv("LIFEOS_ENCRYPTION_KEY")
            if not raw_env_key:
                # Generate a temporary key if none configured
                self._key = secrets.token_bytes(32)
            else:
                self._key = base64.b64decode(raw_env_key)
        elif isinstance(key, str):
            self._key = base64.b64decode(key)
        else:
            self._key = key

        if len(self._key) != 32:
            raise ValueError(
                f"Encryption key must be exactly 32 bytes for AES-256 (got {len(self._key)})"
            )

        self._aesgcm = AESGCM(self._key)

    @staticmethod
    def generate_key_b64() -> str:
        """Generate a random 32-byte key formatted as base64."""
        return base64.b64encode(secrets.token_bytes(32)).decode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        """Encrypts a plaintext string, returning base64(nonce + ciphertext + tag)."""
        if not plaintext:
            return ""
        nonce = secrets.token_bytes(12)  # Standard 96-bit nonce for AES-GCM
        data = plaintext.encode("utf-8")
        ciphertext = self._aesgcm.encrypt(nonce, data, None)
        # Prepend nonce to ciphertext
        payload = nonce + ciphertext
        return base64.b64encode(payload).decode("utf-8")

    def decrypt(self, encrypted_b64: str) -> str:
        """Decrypts a base64 string formatted as base64(nonce + ciphertext + tag)."""
        if not encrypted_b64:
            return ""
        payload = base64.b64decode(encrypted_b64)
        if len(payload) < 28:  # 12-byte nonce + 16-byte tag minimum
            raise ValueError("Invalid encrypted payload size")
        nonce = payload[:12]
        ciphertext = payload[12:]
        decrypted_bytes = self._aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted_bytes.decode("utf-8")
