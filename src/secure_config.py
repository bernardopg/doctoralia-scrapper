"""
Secure configuration management with encryption for sensitive data.
"""

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ENCRYPTED_PREFIX = "encrypted:"


class SecureConfig:
    """
    Secure configuration manager that encrypts sensitive data.
    """

    def __init__(self, config_file: Path, password: Optional[str] = None) -> None:
        self.config_file = config_file
        self.password = password or self._get_or_create_password()
        self.fernet = self._create_fernet()

    def _get_or_create_password(self) -> str:
        """Get existing password or create a new one."""
        password_file = self.config_file.parent / ".config_password"

        if password_file.exists():
            with open(password_file, "r", encoding="utf-8") as f:
                return f.read().strip()

        # Generate a new password
        password = base64.urlsafe_b64encode(os.urandom(32)).decode()
        with open(password_file, "w", encoding="utf-8") as f:
            f.write(password)

        # Make password file readable only by owner
        os.chmod(password_file, 0o600)

        return password

    def _create_fernet(self) -> Fernet:
        """Create Fernet cipher from password with deterministic salt."""
        password_bytes = self.password.encode()
        # Use a deterministic salt derived from the password so the same
        # password always produces the same key (required for decryption).
        salt = hashlib.sha256(password_bytes).digest()[:16]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
        return Fernet(key)

    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive fields in configuration data."""
        sensitive_fields = ["token", "chat_id", "api_key", "password", "secret"]
        encrypted_data = data.copy()

        for key, value in data.items():
            if isinstance(value, dict):
                encrypted_data[key] = self.encrypt_sensitive_data(value)
            elif isinstance(value, str) and any(
                field in key.lower() for field in sensitive_fields
            ):
                if value:  # Only encrypt non-empty values
                    encrypted_data[key] = (
                        f"{ENCRYPTED_PREFIX}{self.fernet.encrypt(value.encode()).decode()}"
                    )

        return encrypted_data

    def decrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive fields in configuration data."""
        decrypted_data = data.copy()

        for key, value in data.items():
            if isinstance(value, dict):
                decrypted_data[key] = self.decrypt_sensitive_data(value)
            elif isinstance(value, str) and value.startswith(ENCRYPTED_PREFIX):
                try:
                    encrypted_value = value[len(ENCRYPTED_PREFIX) :]  # Remove prefix
                    decrypted_data[key] = self.fernet.decrypt(
                        encrypted_value.encode()
                    ).decode()
                except Exception:
                    # If decryption fails, keep the encrypted value
                    pass

        return decrypted_data

    def save_secure_config(self, config_data: Dict[str, Any]) -> None:
        """Save configuration with sensitive data encrypted."""
        encrypted_data = self.encrypt_sensitive_data(config_data)

        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(encrypted_data, f, indent=2, ensure_ascii=False)

    def load_secure_config(self) -> Dict[str, Any]:
        """Load configuration with sensitive data decrypted."""
        if not self.config_file.exists():
            return {}

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                encrypted_data = json.load(f)

            return self.decrypt_sensitive_data(encrypted_data)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}


class ConfigValidator:
    """
    Configuration validation and security checks.
    """

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate that URL is from allowed domains."""
        allowed_domains = [
            "doctoralia.com.br",
            "doctoralia.com",
            "doctoralia.es",
            "doctoralia.mx",
            "doctoralia.cl",
            "doctoralia.ar",
            "doctoralia.co",
        ]

        if not url.startswith("https://"):
            return False

        return any(domain in url for domain in allowed_domains)

    @staticmethod
    def sanitize_input(text: str, max_length: int = 1000) -> str:
        """Sanitize user input to prevent injection attacks."""
        if not text:
            return ""

        # Remove potentially dangerous characters
        sanitized = "".join(c for c in text if c.isalnum() or c in " .,-_@")

        return sanitized[:max_length]

    @staticmethod
    def validate_telegram_config(token: Optional[str], chat_id: Optional[str]) -> bool:
        """Validate Telegram configuration."""
        if not token or not chat_id:
            return False

        # Skip validation for encrypted values
        if token.startswith(ENCRYPTED_PREFIX):
            return True

        # Telegram bot tokens have format: <bot_id>:<hash> (e.g., 123456:ABC-DEF...)
        if ":" not in token:
            return False

        # Basic validation for chat ID (numeric, possibly negative for groups, or @username)
        if chat_id.startswith(ENCRYPTED_PREFIX):
            return True
        if not (
            chat_id.lstrip("-").isdigit()
            or chat_id.startswith("@")
        ):
            return False

        return True
