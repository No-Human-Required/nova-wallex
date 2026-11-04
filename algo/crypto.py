"""Server-side encryption of user exchange keys and provider secrets."""
import hashlib
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken


class Secrets:
    def __init__(self, key=None):
        key = key or os.getenv('ALGO_VAULT_KEY') or os.getenv('SW_VAULT_KEY')
        if not key:
            raise RuntimeError('ALGO_VAULT_KEY (Fernet key) is required')
        self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        # Separate HMAC key for OTP hashes, derived so one env var is enough.
        self.mac_key = hashlib.sha256(b'algorithmic-otp:'+(key.encode() if isinstance(key, str) else key)).digest()

    def encrypt(self, text):
        return self.cipher.encrypt(text.encode())

    def decrypt(self, blob):
        try:
            return self.cipher.decrypt(bytes(blob)).decode()
        except InvalidToken:
            raise ValueError('Secret cannot be decrypted with this server key') from None

    def mac(self, *parts):
        return hmac.new(self.mac_key, '|'.join(map(str, parts)).encode(), hashlib.sha256).hexdigest()


def fingerprint(text):
    return hashlib.sha256(text.encode()).hexdigest()
